import time

from asyncio import Protocol, transports
from typing import Optional, Union, Dict, Set, List

from mudtelnet import TelnetFrame, TelnetConnection, TelnetOutMessage, TelnetOutMessageType
from mudtelnet import TelnetInMessage, TelnetInMessageType
from athanor.shared import COLOR_MAP
from athanor.shared import ConnectionInMessageType, ConnectionOutMessage, ConnectionInMessage, ConnectionOutMessageType

from .conn import MudConnection


class TelnetMudConnection(MudConnection, Protocol):

    def __init__(self, listener):
        super().__init__(listener)
        self.telnet = TelnetConnection()
        self.telnet_in_events: List[TelnetInMessage] = list()
        self.telnet_pending_events: List[TelnetInMessage] = list()
        self.transport: Optional[transports.Transport] = None
        self.in_buffer = bytearray()

    def on_start(self):
        super().on_start()
        self.telnet_in_events.extend(self.telnet_pending_events)
        self.telnet_pending_events.clear()
        if self.telnet_in_events:
            self.process_telnet_events()

    def check_ready(self):
        if (time.time() - self.created) > 0.3:
            self.on_start()

    def data_received(self, data: bytearray):
        self.in_buffer.extend(data)

        while True:
            frame = TelnetFrame.parse_consume(self.in_buffer)
            if not frame:
                break
            events_buffer = self.telnet_in_events if self.started else self.telnet_pending_events
            out_buffer = bytearray()
            changed = self.telnet.process_frame(frame, out_buffer, events_buffer)
            if out_buffer:
                self.transport.write(out_buffer)
            if changed:
                self.update_details(changed)
                if self.started:
                    self.in_events.append(ConnectionInMessage(ConnectionInMessageType.UPDATE, self.conn_id,
                                                              self.details))

        if self.telnet_in_events:
            self.process_telnet_events()

    def connection_made(self, transport: transports.Transport) -> None:
        self.transport = transport
        addr, port = transport.get_extra_info('peername')
        self.details.host_address = addr
        self.details.host_port = port
        out_buffer = bytearray()
        self.telnet.start(out_buffer)
        self.running = True
        self.transport.write(out_buffer)

    def update_details(self, changed: dict):
        for k, v in changed.items():
            if k in ("local", "remote"):
                for feature, value in v.items():
                    setattr(self.details, feature, value)
            elif k == "naws":
                self.details.width = v.get('width', 78)
                self.details.height = v.get('height', 24)
            elif k == "mccp2":
                for feature, val in v.items():
                    if feature == "active":
                        self.details.mccp2_active = val
            elif k == "mccp3":
                for feature, val in v.items():
                    if feature == "active":
                        self.details.mccp3_active = val
            elif k == "mtts":
                for feature, val in v.items():
                    if feature in ("ansi", "xterm256", "truecolor"):
                        if not val:
                            self.details.color = None
                        else:
                            mapped = COLOR_MAP[feature]
                            if not self.details.color:
                                self.details.color = mapped
                            else:
                                if mapped > self.details.color:
                                    self.details.color = mapped
                    else:
                        setattr(self.details, feature, val)

    def telnet_in_to_conn_in(self, ev: TelnetInMessage):
        if ev.msg_type == TelnetInMessageType.LINE:
            return ConnectionInMessage(ConnectionInMessageType.GAMEDATA, self.conn_id, (('line', (ev.data.decode(),),
                                                                                         dict()),))
        elif ev.msg_type == TelnetInMessageType.GMCP:
            return None
        elif ev.msg_type == TelnetInMessageType.MSSP:
            return ConnectionInMessage(ConnectionInMessageType.REQSTATUS, self.conn_id, ev.data)
        else:
            return None

    def process_telnet_events(self):
        for ev in self.telnet_in_events:
            msg = self.telnet_in_to_conn_in(ev)
            if msg:
                self.in_events.append(msg)
        self.telnet_in_events.clear()

    def conn_out_to_telnet_out(self, ev: ConnectionOutMessage):
        out = list()
        if ev.msg_type == ConnectionOutMessageType.GAMEDATA:
            for cmd, args, kwargs in ev.data:
                cmd = cmd.lower().strip()
                if cmd == 'line':
                    out.append(TelnetOutMessage(TelnetOutMessageType.LINE, args[0]))
                elif cmd == 'text':
                    out.append(TelnetOutMessage(TelnetOutMessageType.TEXT, args[0]))
                elif cmd == 'prompt':
                    out.append(TelnetOutMessage(TelnetOutMessageType.PROMPT, args[0]))
                else:
                    out.append(TelnetOutMessage(TelnetOutMessageType.MSDP, (cmd, args, kwargs)))
        return out

    def process_out_event(self, ev: ConnectionOutMessage):
        outbox = bytearray()
        for msg in self.conn_out_to_telnet_out(ev):
            self.telnet.process_out_message(msg, outbox)
        if outbox:
            self.transport.write(outbox)
