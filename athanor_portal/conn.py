import random
import string
import time
from typing import List
from athanor.shared import ConnectionDetails, ConnectionInMessageType, ConnectionOutMessage, ConnectionInMessage, ConnectionOutMessageType, MudProtocol


class MudConnection:

    def __init__(self, listener):
        self.listener = listener
        self.conn_id: str = self.generate_name()
        self.details = ConnectionDetails()
        self.details.client_id = self.conn_id
        self.details.protocol = listener.protocol
        self.created = time.time()
        self.running: bool = False
        self.started: bool = False
        self.ended: bool = False
        self.tls = bool(listener.ssl_context)
        self.in_events: List[ConnectionInMessage] = listener.service.in_conn_events

    def generate_name(self) -> str:
        prefix = f"{self.listener.name}_"

        attempt = f"{prefix}{''.join(random.choices(string.ascii_letters + string.digits, k=20))}"
        while attempt in self.listener.service.mudconnections:
            attempt = f"{prefix}{''.join(random.choices(string.ascii_letters + string.digits, k=20))}"
        return attempt

    def process_out_event(self, ev: ConnectionOutMessage):
        pass

    def on_start(self):
        self.started = True
        self.in_events.append(ConnectionInMessage(ConnectionInMessageType.READY, self.conn_id, self.details))

    def check_ready(self):
        pass
