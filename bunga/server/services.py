# PEP-8

from dataclasses import asdict, dataclass, is_dataclass
from venv import logger

from channels.layers import get_channel_layer
from dacite import Config, from_dict

from server.utils.broadcast import broadcast_message
from server.schemas import *
from server.channel_cache import (
    ChannelCache,
    ChannelStatus,
    Projection,
    SeekCountdownManager,
    UserInfo,
)
from utils.datetime import get_total_microseconds


@dataclass
class OutboundCommand:
    code: str
    sender: UserInfo = UserInfo.server
    schema_data: any = None


OutboundCommandList = list[OutboundCommand]


class ChatService:
    def __init__(self, channel_id: str):
        self.channel_id = channel_id
        self.channel_cache = ChannelCache(channel_id)
        self.channel_service = ChannelService(channel_id)

    async def dispatch(
        self,
        code: str,
        sender_id: str,
        json_data: dict,
    ) -> OutboundCommandList:
        FORWARDING_CODES = {
            "talk-status",
            "popmoji",
            "danmaku",
            "spark",
            "set-playback",
            "seek",
        }
        if code in FORWARDING_CODES:
            await self.channel_service.forward_raw_message(code, sender_id, json_data)

        METHOD_MAP = {
            "whats-on": self._handle_whats_on,
            "join-in": self._handle_join_in,
            "start-projection": self._handle_start_projection,
            "bye": self._handle_bye,
            "buffer-state-changed": self._handle_buffer_state_changed,
            "set-playback": self._handle_set_playback,
            "seek": self._handle_seek,
            "call": self._handle_call,
            "play-finished": self._handle_play_finished,
        }
        handler = METHOD_MAP.get(code)
        if handler is None:
            return []

        if code not in PROTOCOL_MAP:
            logger.warning("Unknown message received: %s", json_data)
            return []
        schema_cls = PROTOCOL_MAP.get(code)
        schema_data = (
            from_dict(schema_cls, json_data, Config(cast=[Enum]))
            if schema_cls
            else None
        )

        return await handler(sender_id, schema_data)

    async def _handle_whats_on(self, _, __) -> OutboundCommandList:
        projection = self.channel_cache.current_projection
        if projection is None:
            return []

        return [
            OutboundCommand(
                code="now-playing",
                schema_data=NowPlayingSchema(
                    record=projection.record, sharer=projection.sharer
                ),
            ),
        ]

    async def _handle_join_in(
        self,
        sender_id: str,
        schema_data: JoinInSchema,
    ) -> OutboundCommandList:
        # Send current watcher list to client
        watcher_list = self.channel_cache.watcher_list
        buffering_ids = self.channel_cache.buffering_watchers
        commands = [
            OutboundCommand(
                code="here-are",
                schema_data=HereAreSchema(
                    watchers=watcher_list,
                    buffering=buffering_ids,
                ),
            ),
        ]

        # Join user into channel, tell others
        await self.channel_service.join_user(schema_data.user)

        # Apply projection if has, or tell client what is projected
        if schema_data.my_share is not None:
            c = await self._handle_start_projection(sender_id, schema_data.my_share)
            commands.extend(c)
        else:
            commands.append(
                OutboundCommand(
                    code="start-projection",
                    sender=self.channel_cache.current_projection.sharer,
                    schema_data=StartProjectionSchema.from_channel_cache(
                        self.channel_cache
                    ),
                )
            )

        return commands

    async def _handle_start_projection(
        self,
        sender_id: str,
        schema_data: StartProjectionSchema,
    ) -> OutboundCommandList:
        sender = self.channel_cache.get_watcher_info(sender_id)
        if sender is None:
            return

        current = self.channel_cache.current_projection
        if (
            current is not None
            and current.record.record_id == schema_data.video_record.record_id
        ):
            # Playing record_id already, tell sender only
            return [
                OutboundCommand(
                    code="start-projection",
                    schema_data=StartProjectionSchema.from_channel_cache(
                        self.channel_cache
                    ),
                )
            ]

        await self.channel_service.apply_new_projection(sender, schema_data)

        return []

    async def _handle_bye(self, sender_id: str, _: None) -> OutboundCommandList:
        await self.channel_service.leave_user(sender_id)
        return []

    async def _handle_buffer_state_changed(
        self,
        sender_id: str,
        schema_data: BufferStateChangedSchema,
    ) -> OutboundCommandList:
        sender = self.channel_cache.get_watcher_info(sender_id)
        if sender is None:
            logger.warning("Unknown sender %s", sender_id)
            return []

        await self.channel_service.update_buffer_state(
            sender=sender, is_buffering=schema_data.is_buffering
        )
        return []

    async def _handle_set_playback(
        self,
        sender_id: str,
        schema_data: SetPlaybackSchema,
    ) -> OutboundCommandList:
        sender = self.channel_cache.get_watcher_info(sender_id)
        if sender is None:
            logger.warning("Unknown sender %s", sender_id)
            return []

        await self.channel_service.set_channel_playback(
            sender, is_play=schema_data.is_play
        )

        return []

    async def _handle_seek(
        self,
        sender_id: str,
        schema_data: SeekSchema,
    ) -> OutboundCommandList:
        sender = self.channel_cache.get_watcher_info(sender_id)
        if sender is not None:
            await self.channel_service.seek_to(sender, schema_data.delta)

        return []

    async def _handle_call(
        self,
        sender_id: str,
        schema_data: CallSchema,
    ) -> OutboundCommandList:
        if not self.channel_cache.is_watcher(sender_id):
            logger.warning("Unknown sender %s", sender_id)
            return []

        match schema_data.action:
            case CallAction.CALL:
                await self.channel_service.on_call(sender_id)
            case CallAction.ACCEPT:
                await self.channel_service.on_accept_call()
            case CallAction.REJECT:
                await self.channel_service.on_reject_call(sender_id)
            case CallAction.CANCEL:
                await self.channel_service.on_cancel_call(sender_id)

        return []

    async def _handle_play_finished(self, *_, **__) -> OutboundCommandList:
        await self.channel_service.finish_playing()
        return []


class ChannelService:
    def __init__(self, channel_id: str):
        self.channel_id = channel_id
        self.channel_cache = ChannelCache(channel_id)

    async def join_user(self, user: UserInfo) -> None:
        self.channel_cache.upsert_watcher(user)
        await broadcast_message(channel_id=self.channel_id, code="aloha", sender=user)

        self._status_translate(ChannelStatus.PAUSED)
        await self._broadcast_play_status()

    async def leave_user(self, user_id: str) -> None:
        info = self.channel_cache.remove_watcher(user_id)
        if info is None:
            return

        await broadcast_message(channel_id=self.channel_id, code="bye", sender=info)
        if (
            self.channel_cache.channel_status == ChannelStatus.WAITING
            and self.channel_cache.is_all_watchers_ready
        ):
            # If leaving user is the last buffering one, start playback
            self._status_translate(ChannelStatus.PLAYING)

    async def apply_new_projection(
        self, sharer: UserInfo, data: StartProjectionSchema
    ) -> None:
        # Clean old projection
        self.channel_cache.clean_projection()

        # Update projection in cache
        self.channel_cache.current_projection = Projection(
            sharer=sharer, record=data.video_record
        )

        # Load progress for new projection
        saved_progress = self.channel_cache.get_progress(data.video_record.record_id)
        if saved_progress is not None:
            data.position = get_total_microseconds(saved_progress)

        # Init Status in cache
        self.channel_cache.play_status = PlayStatus(position=data.position_delta)
        self.channel_cache.channel_status = ChannelStatus.PAUSED

        # Broadcast new projection
        await broadcast_message(
            channel_id=self.channel_id,
            code="start-projection",
            sender=sharer,
            data=data,
        )

    async def update_buffer_state(self, sender: UserInfo, is_buffering: bool) -> None:
        changed = self.channel_cache.set_watcher_status(sender.id, is_buffering)
        if not changed:
            return

        await broadcast_message(
            self.channel_id,
            "buffer-state-changed",
            sender,
            BufferStateChangedSchema(is_buffering),
        )

        match self.channel_cache.channel_status:
            case ChannelStatus.PLAYING:
                if is_buffering:
                    self._status_translate(ChannelStatus.WAITING)
                    await self._broadcast_play_status()
            case ChannelStatus.WAITING:
                if self.channel_cache.is_all_watchers_ready:
                    self._status_translate(ChannelStatus.PLAYING)
                    await self._broadcast_play_status()
            case ChannelStatus.SEEKING:
                if self.channel_cache.is_all_watchers_ready:
                    self.channel_cache.set_play(True)
                else:
                    self.channel_cache.set_play(False)

    async def set_channel_playback(self, sender: UserInfo, is_play: bool) -> None:
        if not is_play:
            # PAUSE
            self._status_translate(ChannelStatus.PAUSED)
            await self._broadcast_play_status()
        else:
            # PLAY
            if self.channel_cache.channel_status != ChannelStatus.PAUSED:
                return
            await self._evaluate_to_play()

    async def seek_to(self, sender: UserInfo, position: timedelta) -> None:
        match self.channel_cache.channel_status:
            case ChannelStatus.PAUSED:
                self.channel_cache.play_status = PlayStatus(
                    playing=False, position=position
                )
            case ChannelStatus.PLAYING | ChannelStatus.WAITING:
                self.channel_cache.set_position(position)
                SeekCountdownManager.reset(self.channel_id, self._evaluate_to_play())
                self._status_translate(ChannelStatus.SEEKING)
            case ChannelStatus.SEEKING:
                self.channel_cache.set_position(position)
                SeekCountdownManager.reset(self.channel_id, self._evaluate_to_play())
        await self._broadcast_play_status(excludes=[sender.id])

    async def finish_playing(self) -> None:
        # Play finished, back to position 0, and pause
        self.channel_cache.play_status = PlayStatus()
        self._status_translate(ChannelStatus.PAUSED)

    # Call Management
    async def on_call(self, caller_id: str) -> None:
        if self.channel_cache.has_pending_call:
            await self.on_accept_call()
        else:
            if not self.channel_cache.init_call_pending_ids(caller_id):
                await self._all_call_rejected()
            else:
                await broadcast_message(
                    channel_id=self.channel_id,
                    code="call",
                    data=CallSchema(CallAction.CALL),
                )

    async def on_reject_call(self, rejector_id: str) -> None:
        self.channel_cache.remove_call_pending_id(rejector_id)
        if not self.channel_cache.has_pending_call:
            await self._all_call_rejected()

    async def on_accept_call(self) -> None:
        self.channel_cache.clear_call_pending_ids()
        await broadcast_message(
            channel_id=self.channel_id,
            code="call",
            data=CallSchema(CallAction.ACCEPT),
        )

    async def on_cancel_call(self, _: str) -> None:
        self.channel_cache.clear_call_pending_ids()
        await broadcast_message(
            channel_id=self.channel_id,
            code="call",
            data=CallSchema(CallAction.CANCEL),
        )

    async def _all_call_rejected(self) -> None:
        if self.channel_cache.has_pending_call:
            raise Exception("Cannot reject call when there is pending call.")
        await broadcast_message(
            channel_id=self.channel_id,
            code="call",
            data=CallSchema(CallAction.REJECT),
        )

    async def _evaluate_to_play(self) -> None:
        target_status = (
            ChannelStatus.PLAYING
            if self.channel_cache.is_all_watchers_ready
            else ChannelStatus.WAITING
        )
        self._status_translate(target_status)
        await self._broadcast_play_status()

    # Channel Status Management

    def _status_translate(self, target_status: ChannelStatus) -> None:
        RULES = {
            # * -> PAUSED
            (ChannelStatus.PLAYING, ChannelStatus.PAUSED): self._on_pause_playback,
            (ChannelStatus.WAITING, ChannelStatus.PAUSED): self._on_pause_playback,
            (ChannelStatus.SEEKING, ChannelStatus.PAUSED): self._on_seek_paused,
            # WAITING <-> PLAYING
            (ChannelStatus.PLAYING, ChannelStatus.WAITING): self._on_client_buffer,
            (ChannelStatus.WAITING, ChannelStatus.PLAYING): self._on_all_clients_ready,
            # PAUSED -> WAITING / PLAYING
            (ChannelStatus.PAUSED, ChannelStatus.WAITING): None,
            (ChannelStatus.PAUSED, ChannelStatus.PLAYING): self._on_play,
            # WAITING / PLAYING -> SEEKING
            (ChannelStatus.PLAYING, ChannelStatus.SEEKING): None,
            (ChannelStatus.WAITING, ChannelStatus.SEEKING): None,
            # SEEKING -> WAITING / PLAYING
            (ChannelStatus.SEEKING, ChannelStatus.PLAYING): self._on_seek_timeout,
            (ChannelStatus.SEEKING, ChannelStatus.WAITING): self._on_seek_timeout,
        }

        current_status = self.channel_cache.channel_status
        rule_key = (current_status, target_status)
        action = RULES.get(rule_key, "not allowed")
        if action == "not allowed":
            return

        logger.info(f"Group {self.channel_id}: {current_status} -> {target_status}")
        if action is not None:
            action()
        self.channel_cache.channel_status = target_status

    def _on_pause_playback(self) -> None:
        self.channel_cache.set_play(False)

    def _on_seek_paused(self) -> None:
        SeekCountdownManager.cancel(self.channel_id)
        self._on_pause_playback()

    def _on_client_buffer(self) -> None:
        self.channel_cache.set_play(False)

    def _on_all_clients_ready(self) -> None:
        self.channel_cache.set_play(True)

    def _on_play(self) -> None:
        self.channel_cache.set_play(True)

    def _on_seek_timeout(self) -> None:
        self.channel_cache.set_play(self.channel_cache.is_all_watchers_ready)

    # Broadcast Message

    async def forward_raw_message(
        self, code: str, sender_id: str, json_data: dict
    ) -> None:
        sender = self.channel_cache.get_watcher_info(sender_id)
        if sender is None:
            logger.warning("Unknown sender %s", sender_id)
            return

        event = {
            "type": "send.event.receiver",
            "code": code,
            "sender": asdict(sender),
            "data": json_data,
        }
        layer = get_channel_layer()
        room_group_name = f"room_{self.channel_id}"
        return await layer.group_send(room_group_name, event)

    async def _broadcast_play_status(self, *, excludes: list[str] = []) -> None:
        play_status = self.channel_cache.play_status
        await broadcast_message(
            channel_id=self.channel_id,
            code="play-at",
            data=PlayAtSchema.from_play_status(play_status),
            excludes=excludes,
        )
