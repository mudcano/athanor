from athanor.shared import LinkServiceClient, PortalOutMessageType, PortalOutMessage
from athanor.shared import ServerInMessageType, ServerInMessage
import os
import asyncio


class LinkService(LinkServiceClient):

    def on_new_link(self):
        msg = PortalOutMessage(PortalOutMessageType.HELLO, os.getpid(), None)
        self.link.outbox.put_nowait(msg)

    async def message_from_link(self, message):
        if not message:
            return
        msg: ServerInMessage = ServerInMessage.from_dict(message)
        if msg.msg_type == ServerInMessageType.SYSTEM:
            pass
        else:
            await self.app.conn.in_events.put(msg)

    async def async_run(self):
        await asyncio.gather(self.async_link(), self.handle_in_events(), self.handle_out_events())

    async def handle_in_events(self):
        pass

    async def handle_out_events(self):
        while True:
            msg = await self.out_events.get()

            while msg:
                if self.link:
                    await self.link.outbox.put(msg)
                    msg = None
                else:
                    await asyncio.sleep(0.1)
