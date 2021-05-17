import mudstring
mudstring.install()

from athanor.app import Application as BaseApplication
from .conn import ConnectionService
from .link import LinkService
from .config import Config
from typing import Optional, List, Set, Dict, Union


class Application(BaseApplication):
    run_async = True

    def __init__(self, config: Config):
        super().__init__(config)
        self.link: Optional[LinkService] = None
        self.conn: Optional[ConnectionService] = None
