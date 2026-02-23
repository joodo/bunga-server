# PEP-8

from datetime import timedelta

from ..utils import broadcast_message
from ..schemas import BufferStateChangedSchema, PlayAtSchema
from ..channel_cache import (
    ChannelCache,
    ChannelStatus,
    PlayStatus,
    SeekCountdownManager,
    UserInfo,
)
from ..multition_meta import MultitonMeta
from .state_service import ChannelStateService


class ChannelPlaybackService(metaclass=MultitonMeta):
    def __init__(self, channel_id: str) -> None:
        self.channel_id = channel_id
        self.state = ChannelStateService(channel_id)
        self.channel_cache = ChannelCache(channel_id)

    async def update_buffer_state(self, sender: UserInfo, is_buffering: bool) -> None:
        changed = self.channel_cache.set_watcher_status(sender.id, is_buffering)
        if not changed:
            return

        await broadcast_message(
            self.channel_id,
            "buffer-state-changed",
            sender=sender,
            data=BufferStateChangedSchema(is_buffering),
        )

        match self.channel_cache.channel_status:
            case ChannelStatus.PLAYING:
                if is_buffering:
                    self.state.translate_to(ChannelStatus.WAITING)
                    await self.broadcast()
            case ChannelStatus.WAITING:
                if self.channel_cache.is_all_watchers_ready:
                    self.state.translate_to(ChannelStatus.PLAYING)
                    await self.broadcast()
            case ChannelStatus.SEEKING_DURING_PLAYBACK:
                # Playback progress will be synchronized to the slowest client.
                if self.channel_cache.is_all_watchers_ready:
                    self.channel_cache.set_play(True)
                else:
                    self.channel_cache.set_play(False)

    async def on_play_request(self):
        if self.channel_cache.channel_status != ChannelStatus.PAUSED:
            return
        await self._evaluate_to_play()

    async def on_pause_request(self, sender: UserInfo, position: timedelta):
        self.channel_cache.set_position(position)
        self.state.translate_to(ChannelStatus.PAUSED)
        await self.broadcast(excludes=[sender])

    async def seek_to(self, sender: UserInfo, position: timedelta) -> None:
        match self.channel_cache.channel_status:
            case ChannelStatus.PAUSED:
                self.channel_cache.play_status = PlayStatus(
                    playing=False, position=position
                )
            case ChannelStatus.PLAYING | ChannelStatus.WAITING:
                self.channel_cache.set_position(position)
                SeekCountdownManager.reset(self.channel_id, self._evaluate_to_play())
                self.state.translate_to(ChannelStatus.SEEKING_DURING_PLAYBACK)
            case ChannelStatus.SEEKING_DURING_PLAYBACK:
                self.channel_cache.set_position(position)
                SeekCountdownManager.reset(self.channel_id, self._evaluate_to_play())
        await self.broadcast(excludes=[sender])

    async def finish_playing(self) -> None:
        # Play finished, back to position 0, and pause
        self.channel_cache.play_status = PlayStatus()
        self.state.translate_to(ChannelStatus.PAUSED)

    async def broadcast(self, *, excludes: list[UserInfo] = []) -> None:
        play_status = self.channel_cache.play_status
        await broadcast_message(
            channel_id=self.channel_id,
            code="play-at",
            data=PlayAtSchema.from_play_status(play_status),
            excludes=[u.id for u in excludes],
        )

    async def _evaluate_to_play(self) -> None:
        target_status = (
            ChannelStatus.PLAYING
            if self.channel_cache.is_all_watchers_ready
            else ChannelStatus.WAITING
        )
        self.state.translate_to(target_status)
        await self.broadcast()
