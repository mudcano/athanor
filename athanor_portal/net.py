import ssl
import asyncio
import websockets
import os

from typing import Optional, Dict
from enum import IntEnum
from athanor.app import Service

from athanor.shared import PortalOutMessageType
from athanor.shared import ServerInMessageType, ServerInMessage, ConnectionOutMessage, ConnectionOutMessageType

from .conn import MudConnection
from .telnet import TelnetMudConnection
from .websocket import WebSocketConnection


class MudProtocol(IntEnum):
    TELNET = 0
    WEBSOCKET = 1


class MudListener:
    __slots__ = ['service', 'name', 'interface', 'port', 'protocol', 'ssl_context', 'server']

    def __init__(self, service: "NetService", name: str, interface: str, port: int, protocol: MudProtocol,
                 ssl_context: Optional[ssl.SSLContext] = None):
        self.service: "NetService" = service
        self.name: str = name
        self.interface: str = interface
        self.port: int = port
        self.protocol: MudProtocol = protocol
        self.ssl_context: Optional[ssl.SSLContext] = ssl_context
        self.server = None

    async def async_setup(self):
        if self.protocol == MudProtocol.TELNET:
            loop = asyncio.get_event_loop()
            self.server = await loop.create_server(self.accept_telnet, self.interface, self.port,
                                                   ssl=self.ssl_context, start_serving=False)
        elif self.protocol == MudProtocol.WEBSOCKET:
            self.server = websockets.serve(self.accept_websocket, self.interface, self.port,
                                           ssl=self.ssl_context)

    def accept_telnet(self):
        conn = TelnetMudConnection(self)
        self.service.mudconnections[conn.conn_id] = conn
        return conn

    def accept_websocket(self, ws, path):
        conn = WebSocketConnection(self, ws, path)
        self.service.mudconnections[conn.conn_id] = conn
        return conn.run()

    async def run(self):
        if self.protocol == MudProtocol.TELNET:
            await self.server.serve_forever()
        elif self.protocol == MudProtocol.WEBSOCKET:
            await self.server


class NetService(Service):
    __slots__ = ['app', 'ssl_contexts', 'listeners', 'listeners', 'mudconnections', 'interfaces', 'selector',
                 'ready_listeners', 'ready_readers', 'ready_writers']

    def __init__(self, app):
        super().__init__(app)
        self.app.net = self
        self.listeners: Dict[str, MudListener] = dict()
        self.mudconnections: Dict[str, MudConnection] = dict()
        self.in_events: Optional[asyncio.Queue] = None
        self.out_events: Optional[asyncio.Queue] = None
        self.in_conn_events = list()
        self.out_conn_events = list()

    def register_listener(self, name: str, interface: str, port: int, protocol: MudProtocol,
                          ssl_context: Optional[str] = None):
        if name in self.listeners:
            raise ValueError(f"A Listener is already using name: {name}")
        host = self.app.config.interfaces.get(interface, None)
        if host is None:
            raise ValueError(f"Interface not registered: {interface}")
        if port < 0 or port > 65535:
            raise ValueError(f"Invalid port: {port}. Port must be number between 0 and 65535")
        use_ssl = self.app.config.tls_contexts.get(ssl_context, None)
        if ssl_context and not use_ssl:
            raise ValueError(f"SSL Context not registered: {ssl_context}")
        listener = MudListener(self, name, host, port, protocol, ssl_context=use_ssl)
        self.listeners[name] = listener

    def setup(self):
        for name, config in self.app.config.listeners.items():
            try:
                protocol = MudProtocol(config.get("protocol", -1))
            except ValueError:
                raise ValueError(f"Must provide a valid protocol for {name}!")
            self.register_listener(name, config.get("interface", None), config.get("port", -1), protocol,
                                   config.get("ssl", None))

    async def async_setup(self):
        self.in_events = asyncio.Queue()
        self.out_events = asyncio.Queue()
        for listener in self.listeners.values():
            await listener.async_setup()

    async def async_run(self):
        gathered = asyncio.gather(self.poll_in_events(), self.poll_out_events(),
                                  *[listener.run() for listener in self.listeners.values()])
        await gathered

    async def poll_out_events(self):
        while True:
            ended = set()
            msg = await self.out_events.get()
            if msg.msg_type == PortalOutMessageType.EVENTS:
                for ev_dict in msg.data:
                    conn_out_msg = ConnectionOutMessage.from_dict(ev_dict)
                    if (conn := self.mudconnections.get(conn_out_msg.client_id, None)):
                        if conn_out_msg.msg_type == ConnectionOutMessageType.DISCONNECT:
                            ended.add(conn)
                        conn.process_out_event(conn_out_msg)
            elif msg.msg_type == PortalOutMessageType.HELLO:
                pass
            elif msg.msg_type == PortalOutMessageType.SYSTEM:
                pass

            for conn in ended:
                self.mudconnections.pop(conn.conn_id, None)

    async def poll_in_events(self):

        while True:
            ended = {conn for conn in self.mudconnections.values() if conn.ended}
            not_ready = {conn for conn in self.mudconnections.values() if not conn.started}
            for conn in not_ready:
                conn.check_ready()

            if self.in_conn_events:
                data = [ev.to_dict() for ev in self.in_conn_events]
                msg = ServerInMessage(ServerInMessageType.EVENTS, os.getpid(), data)
                await self.app.link.in_events.put(msg)
                self.in_conn_events.clear()

            for conn in ended:
                self.mudconnections.pop(conn.conn_id, None)

            await asyncio.sleep(0.1)
