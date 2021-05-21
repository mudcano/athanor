from athanor.app import Service
import asyncio
from typing import Optional, Union, Dict, Set, List
import os
from athanor.shared import ConnectionDetails
from athanor.shared import ConnectionInMessageType, ConnectionOutMessage, ConnectionInMessage, ConnectionOutMessageType
from athanor.shared import PortalOutMessageType, PortalOutMessage, ServerInMessageType, ServerInMessage


class Connection:
    def __init__(self, service: "ConnectionService", details: ConnectionDetails):
        self.service = service
        self.details: ConnectionDetails = details
        self.in_events: List[ConnectionInMessage] = list()
        self.out_events: List[ConnectionOutMessage] = list()

    @property
    def client_id(self):
        return self.details.client_id

    def on_update(self, details: ConnectionDetails):
        self.details = details

    def on_process_event(self, ev: ConnectionInMessage):
        pass

    def on_client_connect(self):
        pass

    def on_client_disconnect(self):
        pass

    def on_server_disconnect(self):
        pass

    def flush_out_events(self):
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
        while True:
            events = list()
            for conn in self.connections.values():
                conn.flush_out_events()
                if conn.out_events:
                    events.extend(conn.out_events)
                    conn.out_events.clear()

            if events:
                await self.app.link.out_events.put(PortalOutMessage(PortalOutMessageType.EVENTS, os.getpid(), events))
            await asyncio.sleep(0.1)


    def get_or_create_client(self, details) -> Connection:
        if (conn := self.connections.get(details.client_id, None)):
            conn.on_update(details)
            return conn
        else:
            conn = self.conn_class(self, details)
            self.connections[details.client_id] = conn
            conn.on_client_connect()
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
                conn.on_process_event(ev)
        else:
            pass

    def remove_client(self, conn: Connection):
        pass
