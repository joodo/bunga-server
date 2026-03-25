# PEP-8

from datetime import datetime, timedelta

from ..channel_cache import (
    ChannelCache,
    ChannelStatus,
    PlayStatus,
    UserInfo,
)
from ..multition_meta import MultitonMeta
from .state_service import ChannelStateService


class ChannelPlaybackService(metaclass=MultitonMeta):
    def __init__(self, channel_id: str) -> None:
        self.channel_id = channel_id
        self.state = ChannelStateService(channel_id)
        self.channel_cache = ChannelCache(channel_id)

    def update_client_state(self, sender: UserInfo, is_pending: bool) -> None:
        changed = self.channel_cache.set_watcher_status(sender.id, is_pending)
        if not changed:
            return

        match self.channel_cache.channel_status:
            case ChannelStatus.PLAYING | ChannelStatus.PENDING:
                self._evaluate_to_play()

    def on_play_request(self):
        if self.channel_cache.channel_status != ChannelStatus.PAUSED:
            return
        self._evaluate_to_play()

    def on_pause_request(self, position: timedelta | None):
        if position:
            self.channel_cache.set_position(position)
        self.state.translate_to(ChannelStatus.PAUSED)

    def seek_to(self, position: timedelta) -> None:
        self.channel_cache.set_position(position)

    def finish_playing(self) -> None:
        # Play finished, back to position 0, and pause
        self.channel_cache.play_status = PlayStatus()
        self.state.translate_to(ChannelStatus.PAUSED)

    def _evaluate_to_play(self) -> None:
        if self.channel_cache.is_all_watchers_ready:
            self.state.translate_to(ChannelStatus.PLAYING)
        else:
            self.state.translate_to(ChannelStatus.PENDING)
