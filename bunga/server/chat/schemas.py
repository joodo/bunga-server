# PEP-8

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

from utils.datetime import get_total_microseconds
from .channel_cache import ChannelCache, PlayStatus, UserInfo, VideoRecord


@dataclass
class NowPlayingSchema:
    record: VideoRecord
    sharer: UserInfo


@dataclass
class JoinInSchema:
    user: UserInfo
    my_share: StartProjectionSchema | None = None


@dataclass
class IAmSchema:
    info: UserInfo


@dataclass
class HereAreSchema:
    watchers: list[UserInfo]
    buffering: list[str]


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
class PlayAtSchema:
    is_play: bool
    position: int

    @classmethod
    def from_play_status(cls, play_status: PlayStatus) -> PlayAtSchema:
        return cls(
            is_play=play_status.playing,
            position=get_total_microseconds(play_status.position),
        )


@dataclass
class BufferStateChangedSchema:
    is_buffering: bool


class CallAction(str, Enum):
    CALL = "call"
    ACCEPT = "accept"
    REJECT = "reject"
    CANCEL = "cancel"


@dataclass
class CallSchema:
    action: CallAction


PROTOCOL_MAP = {
    "whats-on": None,
    "now-playing": NowPlayingSchema,
    "join-in": JoinInSchema,
    "i-am": IAmSchema,
    "play-at": PlayAtSchema,
    "start-projection": StartProjectionSchema,
    "here-are": HereAreSchema,
    "buffer-state-changed": BufferStateChangedSchema,
    "play": None,
    "pause": PauseSchema,
    "seek": SeekSchema,
    "bye": None,
    "call": CallSchema,
    "play-finished": None,
}
