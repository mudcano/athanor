from athanor.shared import LinkServiceClient, PortalOutMessageType, PortalOutMessage
from athanor.shared import ServerInMessageType, ServerInMessage
import os


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
            await self.app.game.in_events.put(msg)