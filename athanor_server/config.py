from athanor.app import BaseConfig


class Config(BaseConfig):
    def __init__(self):
        super().__init__()
        self.name = "server"
        self.process_name: str = "Athanor Server"
        self.application = "athanor_server.app.Application"

    def _config_classes(self):
        self.classes["services"]["link"] = "athanor_server.link.LinkService"
        self.classes["services"]["conn"] = "athanor_server.conn.ConnectionService"
        self.classes["game"]["connection"] = "athanor_server.conn.Connection"
