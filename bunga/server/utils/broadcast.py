from server.channel_cache import UserInfo
from channels.layers import get_channel_layer
from dataclasses import asdict, is_dataclass


async def broadcast_message(
    channel_id: str,
    code: str,
    sender: UserInfo = UserInfo.server,
    data: any = None,
    *,
    excludes: list[str] = [],
) -> None:
    event = {
        "type": "send.event.receiver",
        "code": code,
        "sender": asdict(sender),
        "data": asdict(data) if is_dataclass(data) else None,
        "excludes": excludes,
    }
    layer = get_channel_layer()
    room_group_name = f"room_{channel_id}"
    return await layer.group_send(room_group_name, event)
