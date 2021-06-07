import asyncio
import os

from athanor.shared import LinkServiceServer, PortalOutMessageType, PortalOutMessage
from athanor.shared import ServerInMessageType, ServerInMessage


class LinkService(LinkServiceServer):

    async def message_from_link(self, message):
        if not message:
            return
        msg: PortalOutMessage = PortalOutMessage.from_dict(message)
        if msg.msg_type == PortalOutMessageType.HELLO:
            data = [c.details.to_dict() for c in self.app.net.mudconnections.values()
                    if c.started]
            out_msg = ServerInMessage(ServerInMessageType.HELLO, os.getpid(), data)
            await self.link.outbox.put(out_msg)
        else:
            await self.app.net.out_events.put(msg)

    async def handle_in_events(self):
        while True:
            msg = await self.in_events.get()
            while msg:
                if self.link:
                    await self.link.outbox.put(msg)
                    msg = None
                else:
                    await asyncio.sleep(0.1)
