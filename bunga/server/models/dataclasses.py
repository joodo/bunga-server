# PEP-8

from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum, auto


class PlayStatus(Enum):
    PAUSE = auto()
    PLAY = auto()


@dataclass
class UserInfo:
    id: str
    name: str
    color_hue: int = 0


UserInfo.server = UserInfo(id='server', name='server')


@dataclass
class Projection:
    record_id: str
    sharer: UserInfo


@dataclass
class ChannelStatus:
    update_at: datetime = datetime.now()
    position: timedelta = timedelta(0)
    play_status: PlayStatus = PlayStatus.PAUSE

    @property
    def current_position(self) -> timedelta:
        if (self.play_status != PlayStatus.PLAY):
            return self.position
        return self.position + (datetime.now() - self.update_at)
