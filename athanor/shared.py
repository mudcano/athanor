import time
import orjson
import asyncio
import websockets

from typing import Optional
from enum import IntEnum
from dataclasses import dataclass
from dataclasses_json import dataclass_json
from websockets.exceptions import (
    ConnectionClosedError,
    ConnectionClosed,
    ConnectionClosedOK,
)

from athanor.app import Service


UNKNOWN = "UNKNOWN"


class MudProtocol(IntEnum):
    TELNET = 0
    WEBSOCKET = 1

    def __str__(self):
        if self == 0:
            return "Telnet"
        elif self == 1:
            return "WebSocket"
        else:
            return "Unknown"


# Shamelessly yoinked this IntEnum from Rich for K.I.S.S. purposes.
class ColorSystem(IntEnum):
    """One of the 3 color system supported by terminals."""

    STANDARD = 1
    EIGHT_BIT = 2
    TRUECOLOR = 3
    WINDOWS = 4


COLOR_MAP = {
    "ansi": ColorSystem.STANDARD,
    "xterm256": ColorSystem.EIGHT_BIT,
    "truecolor": ColorSystem.TRUECOLOR,
}


@dataclass_json
@dataclass
class ConnectionDetails:
    protocol: MudProtocol = 0
    client_id: str = UNKNOWN
    client_name: str = UNKNOWN
    client_version: str = UNKNOWN
    host_address: str = UNKNOWN
    host_name: str = UNKNOWN
    host_port: int = 0
    connected: float = time.time()
    utf8: bool = False
    color: Optional[ColorSystem] = None
    screen_reader: bool = False
    proxy: bool = False
    osc_color_palette: bool = False
    vt100: bool = False
    mouse_tracking: bool = False
    naws: bool = False
    width: int = 78
    height: int = 24
    mccp2: bool = False
    mccp2_active: bool = False
    mccp3: bool = False
    mccp3_active: bool = False
    mtts: bool = False
    ttype: bool = False
    mnes: bool = False
    suppress_ga: bool = False
    force_endline: bool = False
    linemode: bool = False
    mssp: bool = False
    mxp: bool = False
    mxp_active: bool = False
    oob: bool = False


class ConnectionInMessageType(IntEnum):
    GAMEDATA = 0
    CONNECT = 1
    READY = 2
    REQSTATUS = 3
    DISCONNECT = 4
    UPDATE = 5


@dataclass_json
@dataclass
class ConnectionInMessage:
    msg_type: ConnectionInMessageType
    client_id: str
    data: Optional[object]


class ConnectionOutMessageType(IntEnum):
    GAMEDATA = 0
    MSSP = 1
    DISCONNECT = 2


@dataclass_json
@dataclass
class ConnectionOutMessage:
    msg_type: ConnectionOutMessageType
    client_id: str
    data: Optional[object]


class PortalOutMessageType(IntEnum):
    EVENTS = 0
    HELLO = 1
    SYSTEM = 2


@dataclass_json
@dataclass
class PortalOutMessage:
    msg_type: PortalOutMessageType
    process_id: int
    data: Optional[object]


class ServerInMessageType(IntEnum):
    EVENTS = 0
    HELLO = 1
    SYSTEM = 2


@dataclass_json
@dataclass
class ServerInMessage:
    msg_type: ServerInMessageType
    process_id: int
    data: Optional[object]


class LinkProtocol:
    def __init__(self, service, ws, path):
        self.service = service
        self.connection = ws
        self.path = path
        self.outbox = asyncio.Queue()
        self.task = None
        self.running = False

    async def run(self):
        self.running = True
        self.task = asyncio.create_task(self.run_tasks())
        await self.task
        self.running = False

    async def run_tasks(self):
        await asyncio.gather(self.read(), self.write())

    async def read(self):
        try:
            async for message in self.connection:
                await self.process_message(message)
        except ConnectionClosedError:
            self.running = False
            self.task.cancel()
        except ConnectionClosedOK:
            self.running = False
            self.task.cancel()
        except ConnectionClosed:
            self.running = False
            self.task.cancel()

    async def write(self):
        while self.running:
            msg = await self.outbox.get()
            # print(f"{self.service.app.config.name.upper()} SENDING MESSAGE: {msg}")
            if isinstance(msg, str):
                await self.connection.send(msg)
            else:
                await self.connection.send(orjson.dumps(msg))

    async def process_message(self, message):
        # print(f"{self.service.app.config.name.upper()} RECEIVED MESSAGE: {message}")
        if isinstance(message, bytes):
            data = orjson.loads(message.decode())
            await self.service.message_from_link(data)
        else:
            print(
                f"{self.service.app.config.name} got unknown websocket message: {message}"
            )


class LinkService(Service):
    def __init__(self, app):
        super().__init__(app)
        self.app.link = self
        self.link: Optional[LinkProtocol] = None
        self.interface: Optional[str] = None
        self.port: int = 0
        self.in_events: Optional[asyncio.Queue] = None
        self.out_events: Optional[asyncio.Queue] = None

    def setup(self):
        link_conf = self.app.config.link
        interface = self.app.config.interfaces.get(link_conf["interface"], None)
        if interface is None:
            raise ValueError("Portal must have a link interface!")
        self.interface = interface
        port = int(link_conf["port"])
        if port < 0 or port > 65535:
            raise ValueError(
                f"Invalid port: {port}. Port must be 16-bit unsigned integer"
            )
        self.port = port

    async def async_setup(self):
        self.in_events = asyncio.Queue()
        self.out_events = asyncio.Queue()

    async def async_run(self):
        pass

    async def handle_in_events(self):
        pass

    async def handle_out_events(self):
        pass

    def new_link(self, ws, path):
        link = LinkProtocol(self, ws, path)
        if self.link:
            self.close_link()
        self.link = link
        self.on_new_link()
        return link.run()

    def on_new_link(self):
        pass

    def close_link(self):
        pass

    async def message_from_link(self, message):
        pass


class LinkServiceServer(LinkService):
    def __init__(self, app):
        super().__init__(app)
        self.listener = None

    async def async_run(self):
        await asyncio.gather(
            self.listener, self.handle_in_events(), self.handle_out_events()
        )

    async def async_setup(self):
        await super().async_setup()
        self.listener = websockets.serve(self.new_link, self.interface, self.port)


class LinkServiceClient(LinkService):
    async def async_run(self):
        await asyncio.gather(
            self.async_link(), self.handle_in_events(), self.handle_out_events()
        )

    async def async_link(self):
        url = f"ws://{self.interface}:{self.port}"
        while True:
            async with websockets.connect(url) as ws:
                self.link = LinkProtocol(self, ws, "/")
                self.on_new_link()
                await self.link.run()
            await asyncio.sleep(0.1)

    async def handle_in_events(self):
        while True:
            msg = await self.in_events.get()
            await self.app.conn.in_events.put(msg)

    async def handle_out_events(self):
        while True:
            if self.link:
                msg = await self.out_events.get()
                await self.link.outbox.put(msg)
            else:
                await asyncio.sleep(1)
