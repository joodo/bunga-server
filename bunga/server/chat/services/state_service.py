# PEP-8

from ..channel_cache import ChannelCache, ChannelStatus
from ..multition_meta import MultitonMeta
from utils.log import logger


class ChannelStateService(metaclass=MultitonMeta):
    def __init__(self, channel_id: str) -> None:
        self.channel_id = channel_id
        self.channel_cache = ChannelCache(channel_id)

    def translate_to(self, target_status: ChannelStatus) -> None:
        RULES = {
            # * -> PAUSED
            (ChannelStatus.PLAYING, ChannelStatus.PAUSED): self._on_pause_playback,
            (ChannelStatus.PENDING, ChannelStatus.PAUSED): self._on_pause_playback,
            # WAITING <-> PLAYING
            (ChannelStatus.PLAYING, ChannelStatus.PENDING): self._on_client_pending,
            (ChannelStatus.PENDING, ChannelStatus.PLAYING): self._on_all_clients_ready,
            # PAUSED -> WAITING / PLAYING
            (ChannelStatus.PAUSED, ChannelStatus.PENDING): None,
            (ChannelStatus.PAUSED, ChannelStatus.PLAYING): self._on_play,
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

    def _on_client_pending(self) -> None:
        self.channel_cache.set_play(False)

    def _on_all_clients_ready(self) -> None:
        self.channel_cache.set_play(True)

    def _on_play(self) -> None:
        self.channel_cache.set_play(True)
