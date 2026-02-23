# PEP-8

from ..utils import broadcast_message
from ..schemas import CallAction, CallSchema
from ..multition_meta import MultitonMeta
from ..channel_cache import ChannelCache


class ChannelVoiceCallService(metaclass=MultitonMeta):
    def __init__(self, channel_id: str) -> None:
        self.channel_id = channel_id
        self.channel_cache = ChannelCache(channel_id)

    async def on_call(self, caller_id: str) -> None:
        if self.channel_cache.has_pending_call:
            await self.on_accept()
        else:
            if not self.channel_cache.init_call_pending_ids(caller_id):
                await self._all_call_rejected()
            else:
                await broadcast_message(
                    channel_id=self.channel_id,
                    code="call",
                    data=CallSchema(CallAction.CALL),
                )

    async def on_reject(self, rejector_id: str) -> None:
        self.channel_cache.remove_call_pending_id(rejector_id)
        if not self.channel_cache.has_pending_call:
            await self._all_call_rejected()

    async def on_accept(self) -> None:
        self.channel_cache.clear_call_pending_ids()
        await broadcast_message(
            channel_id=self.channel_id,
            code="call",
            data=CallSchema(CallAction.ACCEPT),
        )

    async def on_cancel(self, _: str) -> None:
        self.channel_cache.clear_call_pending_ids()
        await broadcast_message(
            channel_id=self.channel_id,
            code="call",
            data=CallSchema(CallAction.CANCEL),
        )

    async def _all_call_rejected(self) -> None:
        if self.channel_cache.has_pending_call:
            raise Exception("Cannot reject call when there is pending call.")
        await broadcast_message(
            channel_id=self.channel_id,
            code="call",
            data=CallSchema(CallAction.REJECT),
        )
