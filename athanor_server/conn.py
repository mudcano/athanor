from athanor.app import Service
import asyncio
from typing import Optional, Union, Dict, Set, List

from collections import OrderedDict
from athanor.shared import ConnectionDetails
from athanor.shared import ConnectionInMessageType, ConnectionOutMessage, ConnectionInMessage, ConnectionOutMessageType
from athanor.shared import PortalOutMessageType, PortalOutMessage, ServerInMessageType, ServerInMessage


class Connection:
    def __init__(self, service: "ConnectionService", details: ConnectionDetails):
        self.service = service
        self.details: ConnectionDetails = details
        self.in_events: List[ConnectionInMessage] = list()
        self.out_events: List[ConnectionOutMessage] = list()

    def update(self, details: ConnectionDetails):
        self.details = details

    def process_event(self, ev: ConnectionInMessage):
        print(f"{self} received message: {ev}")
        pass


class ConnectionService(Service):

    def __init__(self):
        self.app.conn = self
        self.next_id: int = 0
        self.connections: Dict[str, Connection] = dict()
        self.in_events: Optional[asyncio.Queue] = None
        self.out_events: Optional[asyncio.Queue] = None
        self.conn_class = self.app.classes['game']['connection']

    async def async_setup(self):
        self.in_events = asyncio.Queue()
        self.out_events = asyncio.Queue()

    async def async_run(self):
        await asyncio.gather(self.handle_out_events(), self.handle_in_events())

    async def handle_in_events(self):
        while True:
            msg = await self.in_events.get()
            if isinstance(msg, ServerInMessage):
                if msg.msg_type == ServerInMessageType.HELLO:
                    self.process_hello(msg)
                elif msg.msg_type == ServerInMessageType.EVENTS:
                    self.process_events(msg)

    async def handle_out_events(self):
        pass

    def greet_client(self, conn: Connection):
        pass

    def get_or_create_client(self, details) -> Connection:
        if (conn := self.connections.get(details.client_id, None)):
            conn.update(details)
            return conn
        else:
            conn = self.conn_class(self, details)
            self.connections[details.client_id] = conn
            self.greet_client(conn)
            return conn

    def process_hello(self, msg: ServerInMessage):
        if not msg.data:
            return
        for d in msg.data:
            details: ConnectionDetails = ConnectionDetails.from_dict(d)
            conn = self.get_or_create_client(details)

    def process_events(self, msg: ServerInMessage):
        if not msg.data:
            return
        for e in msg.data:
            ev = ConnectionInMessage.from_dict(e)
            self.process_event(ev)

    def process_event(self, ev: ConnectionInMessage):
        if ev.msg_type == ConnectionInMessageType.READY:
            details: ConnectionDetails = ConnectionDetails.from_dict(ev.data)
            conn = self.get_or_create_client(details)
            return
        if (conn := self.connections.get(ev.client_id, None)):
            if ev.msg_type == ConnectionInMessageType.DISCONNECT:
                self.remove_client(conn)
            else:
                conn.process_event(ev)
        else:
            pass

    def remove_client(self, conn: Connection):
        pass
