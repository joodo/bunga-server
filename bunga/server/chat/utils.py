# PEP-8

from typing import Any
from dataclasses import asdict

from channels.layers import get_channel_layer

from utils.log import logger
from .channel_cache import ChannelCache, UserInfo


async def broadcast_message(
    channel_id: str,
    code: str,
    *,
    sender: UserInfo = UserInfo.server,
    data: Any = None,
    excludes: list[str] | None = None,
) -> None:
    event = {
        "type": "message.received",
        "code": code,
        "sender": asdict(sender),
        "data": asdict(data) if data is not None else None,
        "excludes": excludes,
    }

    layer = get_channel_layer()
    assert layer != None

    room_group_name = f"room_{channel_id}"
    return await layer.group_send(room_group_name, event)


async def send_message(
    channel_id: str,
    code: str,
    *,
    receiver_id: str,
    sender: UserInfo = UserInfo.server,
    data: Any = None,
) -> None:
    event = {
        "type": "message.received",
        "code": code,
        "sender": asdict(sender),
        "data": asdict(data) if data is not None else None,
    }

    layer = get_channel_layer()
    assert layer != None

    channel_cache = ChannelCache(channel_id)
    client_name = channel_cache.get_client_name(receiver_id)
    if not client_name:
        logger.warning(f"No client of user id {receiver_id}")
        return
    return await layer.send(client_name, event)
