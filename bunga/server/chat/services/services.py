# PEP-8

import functools
from typing import Callable, Awaitable, Any
from dacite import Config, from_dict

from utils.log import logger
from ..utils import send_message
from ..schemas import *
from ..multition_meta import MultitonMeta
from ..channel_cache import ChannelCache, UserInfo
from .playback_service import ChannelPlaybackService
from .presence_service import ChannelPresenceService
from .voice_call_service import ChannelVoiceCallService


class ChatService(metaclass=MultitonMeta):
    def __init__(self, channel_id: str):
        self.channel_id = channel_id
        self.channel_cache = ChannelCache(channel_id)
        self.presence = ChannelPresenceService(channel_id)
        self.playback = ChannelPlaybackService(channel_id)
        self.voice_call = ChannelVoiceCallService(channel_id)

    @staticmethod
    def _require_watcher(
        func: Callable[[ChatService, UserInfo, Any], Awaitable[None]],
    ) -> Callable[[ChatService, str, Any], Awaitable[None]]:
        @functools.wraps(func)
        async def wrapper(self: ChatService, sender_id: str, data: Any):
            sender = self.channel_cache.get_watcher_info(sender_id)
            if sender is None:
                logger.warning("Unknown sender %s", sender_id)
                return None

            await func(self, sender, data)

        return wrapper

    async def dispatch(
        self,
        code: str,
        sender_id: str,
        json_data: dict,
    ) -> None:
        METHOD_MAP = {
            "whats-on": self._handle_whats_on,
            "join-in": self._handle_join_in,
            "start-projection": self._handle_start_projection,
            "bye": self._handle_bye,
            "buffer-state-changed": self._handle_buffer_state_changed,
            "play": self._handle_play,
            "pause": self._handle_pause,
            "seek": self._handle_seek,
            "call": self._handle_call,
            "play-finished": self._handle_play_finished,
        }
        handler = METHOD_MAP.get(code)
        if handler is None:
            return

        if code not in PROTOCOL_MAP:
            logger.warning("Unknown message received: %s", json_data)
            return
        schema_cls = PROTOCOL_MAP.get(code)
        schema_data = (
            from_dict(schema_cls, json_data, Config(cast=[Enum]))
            if schema_cls
            else None
        )

        return await handler(sender_id, schema_data)

    async def _handle_whats_on(
        self,
        sender_id: str,
        schema_data: None,
    ) -> None:
        projection = self.channel_cache.current_projection
        if projection is None:
            return

        await send_message(
            self.channel_id,
            "now-playing",
            receiver_id=sender_id,
            data=NowPlayingSchema(record=projection.record, sharer=projection.sharer),
        )

    async def _handle_join_in(
        self,
        sender_id: str,
        schema_data: JoinInSchema,
    ) -> None:
        # Send current watcher list to client
        watcher_list = self.channel_cache.watcher_list
        buffering_ids = self.channel_cache.buffering_watchers
        await send_message(
            self.channel_id,
            "here-are",
            receiver_id=sender_id,
            data=HereAreSchema(
                watchers=watcher_list,
                buffering=buffering_ids,
            ),
        )

        # Join user into channel, tell others
        await self.presence.join_user(schema_data.user)

        # Apply projection if has, or tell client what is projected
        if schema_data.my_share is not None:
            await self._handle_start_projection(sender_id, schema_data.my_share)
        else:
            await send_message(
                self.channel_id,
                "start-projection",
                receiver_id=sender_id,
                data=StartProjectionSchema.from_channel_cache(self.channel_cache),
            )

    @_require_watcher
    async def _handle_start_projection(
        self,
        sender: UserInfo,
        schema_data: StartProjectionSchema,
    ) -> None:
        current = self.channel_cache.current_projection
        if (
            current is not None
            and current.record.record_id == schema_data.video_record.record_id
        ):
            # Playing record_id already, tell sender only
            await send_message(
                self.channel_id,
                "start-projection",
                receiver_id=sender.id,
                data=StartProjectionSchema.from_channel_cache(self.channel_cache),
            )
        else:
            await self.presence.apply_new_projection(sender, schema_data)

    async def _handle_bye(self, sender_id: str, _: None) -> None:
        await self.presence.leave_user(sender_id)

    @_require_watcher
    async def _handle_buffer_state_changed(
        self,
        sender: UserInfo,
        schema_data: BufferStateChangedSchema,
    ) -> None:
        await self.playback.update_buffer_state(
            sender=sender, is_buffering=schema_data.is_buffering
        )

    @_require_watcher
    async def _handle_play(
        self,
        sender: UserInfo,
        schema_data: None,
    ) -> None:
        await self.playback.on_play_request()

    @_require_watcher
    async def _handle_pause(
        self,
        sender: UserInfo,
        schema_data: PauseSchema,
    ) -> None:
        await self.playback.on_pause_request(sender, schema_data.delta)

    @_require_watcher
    async def _handle_seek(
        self,
        sender: UserInfo,
        schema_data: SeekSchema,
    ) -> None:
        await self.playback.seek_to(sender, schema_data.delta)

    async def _handle_play_finished(self, *_, **__) -> None:
        await self.playback.finish_playing()

    @_require_watcher
    async def _handle_call(
        self,
        sender: UserInfo,
        schema_data: CallSchema,
    ) -> None:
        sender_id = sender.id

        match schema_data.action:
            case CallAction.CALL:
                await self.voice_call.on_call(sender_id)
            case CallAction.ACCEPT:
                await self.voice_call.on_accept()
            case CallAction.REJECT:
                await self.voice_call.on_reject(sender_id)
            case CallAction.CANCEL:
                await self.voice_call.on_cancel(sender_id)
