# PEP-8

from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum, auto


class WatcherStatus(Enum):
    BUFFERING = "buffering"
    READY = "ready"
    DETACHED = "detached"


@dataclass
class UserInfo:
    id: str
    name: str
    color_hue: int = 0


UserInfo.server = UserInfo(id="server", name="server")


@dataclass
class Projection:
    record_id: str
    sharer: UserInfo
