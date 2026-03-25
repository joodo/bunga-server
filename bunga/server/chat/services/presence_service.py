# PEP-8

from utils.datetime import get_total_microseconds
from utils.log import logger
from ..utils import broadcast_message
from ..schemas import StartProjectionSchema
from ..multition_meta import MultitonMeta
from ..channel_cache import (
    ChannelCache,
    ChannelStatus,
    PlayStatus,
    Projection,
    UserInfo,
)
from .playback_service import ChannelPlaybackService
from .state_service import ChannelStateService


class ChannelPresenceService(metaclass=MultitonMeta):
    def __init__(self, channel_id: str) -> None:
        self.channel_id = channel_id
        self.state = ChannelStateService(channel_id)
        self.playback = ChannelPlaybackService(channel_id)
        self.channel_cache = ChannelCache(channel_id)

    async def join_user(self, user: UserInfo) -> None:
        self.channel_cache.upsert_watcher(user)
        await broadcast_message(
            channel_id=self.channel_id, code="aloha", sender=user, excludes=[user.id]
        )

        self.state.translate_to(ChannelStatus.PAUSED)

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

    async def leave_user(self, user_id: str) -> None:
        self.channel_cache.remove_watcher_active_key(user_id)

        info = self.channel_cache.remove_watcher(user_id)
        if info is None:
            return

        if self.channel_cache.has_watcher:
            await broadcast_message(channel_id=self.channel_id, code="bye", sender=info)
            if (
                self.channel_cache.channel_status == ChannelStatus.PENDING
                and self.channel_cache.is_all_watchers_ready
            ):
                # If leaving user is the last buffering one, start playback
                self.state.translate_to(ChannelStatus.PLAYING)
        else:
            # Pause playback if no watcher left
            self.state.translate_to(ChannelStatus.PAUSED)

    async def remove_stale_user(self) -> None:
        stale_ids = [
            id
            for id in self.channel_cache.watcher_ids
            if self.channel_cache.is_watcher_stale(id)
        ]
        for id in stale_ids:
            logger.info(f"Clean staled user {id}")
            await self.leave_user(id)
