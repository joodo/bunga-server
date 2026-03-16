# PEP-8

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

from utils.datetime import get_total_microseconds
from .channel_cache import ChannelCache, ChannelStatus, UserInfo, VideoRecord


@dataclass
class NowPlayingSchema:
    record: VideoRecord
    sharer: UserInfo


@dataclass
class JoinInSchema:
    user: UserInfo
    my_share: StartProjectionSchema | None = None


@dataclass
class HereAreSchema:
    watchers: list[UserInfo]
    buffering: list[str]
    talking: list[str]


@dataclass
class StartProjectionSchema:
    video_record: VideoRecord
    position: int = 0

    @classmethod
    def from_channel_cache(cls, cache: ChannelCache) -> StartProjectionSchema | None:
        current_projection = cache.current_projection
        if not current_projection:
            return None
        return cls(
            video_record=current_projection.record,
            position=get_total_microseconds(cache.play_status.position),
        )

    @property
    def position_delta(self) -> timedelta:
        return timedelta(microseconds=float(self.position))


@dataclass
class SeekSchema:
    position: int

    @property
    def delta(self) -> timedelta:
        return timedelta(microseconds=float(self.position))

    @classmethod
    def from_delta(cls, delta: timedelta) -> SeekSchema:
        return cls(
            position=get_total_microseconds(delta),
        )


@dataclass
class PauseSchema:
    position: int

    @property
    def delta(self) -> timedelta:
        return timedelta(microseconds=float(self.position))


@dataclass
class ClientStatusSchema:
    is_pending: bool


@dataclass
class ChannelStatusSchema:
    watcher_ids: list[str]
    ready_ids: list[str]
    position: int
    play_status: ChannelStatus

    @classmethod
    def from_channel_cache(cls, cache: ChannelCache) -> ChannelStatusSchema:
        play_status = cache.play_status
        return cls(
            watcher_ids=[w.id for w in cache.watcher_list],
            ready_ids=list(cache.ready_ids),
            position=get_total_microseconds(play_status.position),
            play_status=cache.channel_status,
        )


class CallAction(str, Enum):
    CALL = "call"
    ACCEPT = "accept"
    REJECT = "reject"
    CANCEL = "cancel"


@dataclass
class CallSchema:
    action: CallAction


class TalkStatus(str, Enum):
    START = "start"
    END = "end"


@dataclass
class TalkStatusSchema:
    status: TalkStatus


PROTOCOL_MAP = {
    "whats-on": None,
    "now-playing": NowPlayingSchema,
    "join-in": JoinInSchema,
    "start-projection": StartProjectionSchema,
    "here-are": HereAreSchema,
    "client-status": ClientStatusSchema,
    "play": None,
    "pause": PauseSchema,
    "seek": SeekSchema,
    "bye": None,
    "call": CallSchema,
    "talk-status": TalkStatusSchema,
    "play-finished": None,
}
