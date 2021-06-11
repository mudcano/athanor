import ssl
import logging
import socket
import time
import asyncio
import uvloop

from collections import defaultdict
from athanor.utils import import_from_module
from logging.handlers import TimedRotatingFileHandler
from typing import List, Optional, Dict


# Must ensure that UvLoop is installed early!
uvloop.install()


class BaseConfig:
    """
    This class is used as the baseline for all Config objects used in the Athanor project.
    """

    def __init__(self):
        self.name: str = "athanor"
        self.process_name: str = "Athanor Application"
        self.application: str = "athanor.app.Application"

        # A Dict-of-Dicts that stores categorized, named Python paths to classes used by
        # the project.
        self.classes = defaultdict(dict)

        # How often the main loop runs in sync mode.
        self.interval: float = 0.01

        # A dict that maps names to IP Addresses/Interfaces used for networking.
        self.interfaces: Dict[str, str] = dict()

        # A dictionary that maps names to a dict of {"pem": <path>, "key": <path>}
        self.tls: Dict[str, Dict[str, str]] = dict()
        self.tls_contexts = dict()

        self.log_handlers = dict()
        self.logs = dict()

        # A dictionary that maps names to a re.compile() - compiled regex object.
        self.regex = dict()

        # A dict with the information used for the local app-link.
        self.link = dict()

    def setup(self):
        """
        Method that's called to initialize the configuration.
        """
        self._config_classes()
        self._config_interfaces()
        self._config_tls()
        self._init_tls_contexts()
        self._config_log_handlers()
        self._config_logs()
        self._config_regex()
        self._config_link()

    def _config_link(self):
        self.link = {"interface": "localhost", "port": 7998}

    def _config_classes(self):
        """
        Meant to add all necessary classes to the classes dictionary.
        """
        pass

    def _config_interfaces(self):
        """
        This lets you assign a name to an interface. 'internal' is for things hosted on an
        loopback is for hosting on the host itself with no access from other computers.
        internal is for your internal network. Same as loopback unless configured otherwise.
        external is for any internet-facing adapters.
        """
        self.interfaces["loopback"] = "localhost"
        self.interfaces["internal"] = "localhost"
        self.interfaces["external"] = socket.gethostname()
        self.interfaces["public"] = socket.gethostname()
        self.interfaces["any"] = ""
        self.interfaces["localhost"] = "localhost"

    def _config_tls(self):
        """
        can have multiple contexts for different TLS/SSL cert combos.
        These must be file paths to the certifications/keys in question.
        """
        pass

    def _init_tls_contexts(self):
        for k, v in self.tls.items():
            new_context = ssl.SSLContext(ssl.PROTOCOL_TLS)
            new_context.load_cert_chain(v["pem"], v["key"])
            self.tls_contexts[k] = new_context

    def _config_servers(self):
        pass

    def _config_clients(self):
        pass

    def _config_log_handlers(self):
        for name in ("application", "server", "client"):
            handler = TimedRotatingFileHandler(filename=f"logs/{name}.log", when="D")
            self.log_handlers[name] = handler

    def _config_logs(self):
        for name in ("application", "server", "client"):
            log = logging.getLogger(name)
            log.addHandler(self.log_handlers[name])
            self.logs[name] = log

    def _config_regex(self):
        """
        Compiling a regex is expensive, so do it once, here, and save it to self.regex for safekeeping.
        """


class LauncherConfig:
    """
    The config object used by the launcher.
    """

    def __init__(self):
        # This is a List[str] of app names. these are case-sensitive and must match with <name>.py files found
        # in the <template>/appdata/ folder, like portal.py
        self.applications: List[str] = ["portal", "server"]

    def setup(self):
        """
        By default, does nothing...
        """


class Application:
    """
    The basic application framework for Athanor. This is used by both the Portal and Server. However, it
    can also be used for new applications.
    """

    # If this is true, the program will be run asynchronously.
    run_async = False

    def __init__(self, config: BaseConfig):
        self.config: BaseConfig = config

        # This will be a Dict[str, Dict[str, class]] once setup finishes loading.
        self.classes = defaultdict(dict)

        # The application services are stored here once loaded.
        self.services: Dict[str, Service] = dict()

        # This is a list of services which subscribed to the update loop.
        self.services_update: List[Service] = list()

        # Used to show whether the application's currently running. Is this even used?
        self.running: bool = True

        # cached version of the program's run interval for the main loop.
        self.interval = self.config.interval

        # Starting delta for the main loop.
        self.delta = self.interval

    def setup(self):
        """
        Method called by launcher to initialize the Application.
        """
        found_classes = list()
        # Import all classes from the given config object.
        for category, d in self.config.classes.items():
            for name, path in d.items():
                found = import_from_module(path)
                self.classes[category][name] = found
                # Very few classes will likely have this classmethod, but... just in case...
                if hasattr(found, "class_init"):
                    found_classes.append(found)

        for name, v in sorted(
            self.classes["services"].items(),
            key=lambda x: getattr(x[1], "init_order", 0),
        ):
            self.services[name] = v(self)

        self.services_update = sorted(
            self.services.values(), key=lambda x: getattr(x, "update_order", 0)
        )

        for service in sorted(
            self.services.values(), key=lambda s: getattr(s, "load_order", 0)
        ):
            service.setup()

        # call class inits on imported classes, if necessary.
        for cls in found_classes:
            cls.class_init(self)

    async def async_enter(self):
        """
        This is called by start_async as the entry point for the async context.
        """
        # first, run all async setup.
        await self.async_setup()

        # Next, gather the async_run coroutines from all services.
        a_services = [service.async_run() for service in self.services.values()]

        # Await forever for the Application to finish.
        await asyncio.gather(self.async_main_task(), self.async_run_loop(), *a_services)

    async def async_setup(self):
        for service in sorted(
            self.services.values(), key=lambda s: getattr(s, "load_order", 0)
        ):
            await service.async_setup()

    def start_async(self):
        self.running = True
        asyncio.run(self.async_enter(), debug=True)

    async def async_main_task(self):
        """
        Does whatever the program does. Which is probably nothing - most programs act through their Services.

        You could stick something here though.
        """

    async def async_run_loop(self):
        """
        Asynchronous version of the main loop. Does the same thing but uses asyncio to time its calls.
        """
        while self.running:
            self.run_time_loop()

            if self.interval > self.delta:
                await asyncio.sleep(self.interval - self.delta)
            else:
                await asyncio.sleep(0)

    def start(self):
        """
        The synchronous start point for the program, called by startup.
        """
        self.running = True

        while self.running:
            self.run_loop()

    def run_time_loop(self):
        now = time.time()
        self.run_loop_once(now, self.delta)
        self.delta = time.time() - now

    def run_loop(self):
        self.run_time_loop()

        if self.interval > self.delta:
            time.sleep(self.interval - self.delta)
        else:
            time.sleep(0)

    def run_loop_once(self, now: float, delta: float):
        """
        Called by either the async run loop, or the sync one. Does the heavy lifting of updating services.

        Args:
            now (float): The time.time() of this update.
            delta (float): Time since last update.
        """
        self.before_update(now, delta)
        for s in self.services_update:
            s.update(now, delta)
        self.after_update(now, delta)

    def before_update(self, now: float, delta: float):
        """
        What does this do? Whatever you want it to do. It's called before .update()

        Args:
            now (float): The time.time() of this update.
            delta (float): Time since last update.
        """

    def after_update(self, now: float, delta: float):
        """
        What does this do? Whatever you want it to do. It's called after .update()

        Args:
            now (float): The time.time() of this update.
            delta (float): Time since last update.
        """


class Service:
    """
    Base class used for all Services.
    """

    name: Optional[str] = None
    init_order = 0
    setup_order = 0
    update_order = 0

    def __init__(self, app: Application):
        self.app = app

    async def async_setup(self):
        """
        This does nothing by default. It is meant to be overloaded, and used to initialize any
        asynchronous code that .setup() couldn't.
        """

    def setup(self):
        """
        Called during Application setup, use this to ready the Service's resources. Do not use
        any async code here.
        """

    def start(self):
        """
        Begins the Service's synchronous services. Likely unused if the Application is async.
        """

    def update(self, now: float, delta: float):
        """
        Called by Application every time the main loop runs once.

        Args:
            now (float): The current time.time()
            delta (float): The time since the last update.
        """

    async def async_run(self):
        """
        Called by the Application in an asyncio.gather().

        The default implementation does nothing but ensure that the service stays running forever.
        """
        while True:
            await asyncio.sleep(5)
