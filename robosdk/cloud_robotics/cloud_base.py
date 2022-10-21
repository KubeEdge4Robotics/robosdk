# Copyright 2021 The KubeEdge Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import abc
import contextlib
import os.path
import threading
import time
from typing import Any
from typing import Dict

import uvicorn
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from robosdk.common.config import BaseConfig
from robosdk.common.logger import logging
from robosdk.utils.util import parse_kwargs
from starlette.responses import JSONResponse
from starlette.routing import WebSocketRoute
from starlette.types import ASGIApp
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send

__all__ = ("ServiceBase", "WSEndpoint")


class Server(uvicorn.Server):
    def install_signal_handlers(self):
        pass

    @contextlib.contextmanager
    def run_in_thread(self):
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
        try:
            yield thread
        finally:
            self.should_exit = True
            thread.join()


class ServiceBase:
    _WAIT_TIME = 15

    def __init__(self,
                 name: str,
                 port: int,
                 host: str = "",
                 static_folder: str = "",
                 ssl_key: str = BaseConfig.CLOUD_SERVERS_SSL_KEY,
                 ssl_cert: str = BaseConfig.CLOUD_SERVERS_SSL_CERT,
                 protocol: str = "http"):

        self.name = name
        self.logger = logging.bind(
            instance=f"servers_{name}", system=True
        )
        self.host = host or "0.0.0.0"
        self.port = port or int(BaseConfig.CLOUD_SERVERS_PORT)
        self.schema = f"{protocol}s" if ssl_key else protocol
        self.use_ssl = {
            "key": ssl_key,
            "cert": ssl_cert
        }
        self.app = None
        self._static_folder = [
            _p for _p in static_folder.split(";") if os.path.exists(_p)
        ]

    def get_endpoint(self):
        return f"{self.schema}://{self.host}:{self.port}/{self.name}"

    def run(self, **kwargs):
        # if hasattr(self.app, "add_middleware"):
        #     self.app.add_middleware(
        #         CORSMiddleware, allow_origins=["*"],
        #         allow_credentials=True,
        #         allow_methods=["*"],
        #         allow_headers=["*"],
        #     )

        self.logger.info(f"Start {self.name} server over {self}")

        all_k: Dict = parse_kwargs(uvicorn.Config, **kwargs)
        all_k.update(dict(
            app=self.app,
            host=self.host,
            port=self.port,
            ssl_keyfile=self.use_ssl["key"],
            ssl_certfile=self.use_ssl["cert"],
            log_level=BaseConfig.CLOUD_SERVERS_LOG_LEV
        ))

        config = uvicorn.Config(**all_k)

        if len(self._static_folder) and hasattr(self.app, "mount"):
            for _p in self._static_folder:
                self.app.mount(
                    "/static",
                    StaticFiles(directory=_p, html=False),
                    name="static"
                )
        server = Server(config=config)
        with server.run_in_thread() as current_thread:
            return self.wait_stop(current=current_thread)

    @abc.abstractmethod
    def close(self):
        ...

    def wait_stop(self, current):
        """wait the stop flag to shut down the server"""
        while 1:
            time.sleep(self._WAIT_TIME)
            if not current.isAlive():
                return
            if getattr(self.app, "shutdown", False):
                return

    def get_all_urls(self):
        url_list = [{"path": route.path, "name": route.name}
                    for route in getattr(self.app, 'routes', [])]
        return url_list

    def __del__(self):
        self.close()

    def __repr__(self):
        return self.get_endpoint()

    __str__ = __repr__


class WSEventMiddleware:  # pylint: disable=too-few-public-methods
    def __init__(self, app: ASGIApp, name: str = "", server: Any = None):
        self._app = app
        self._name = name
        self._server = server

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] in ("lifespan", "http", "websocket"):
            if self._name not in scope:
                scope[self._name] = self._server

        await self._app(scope, receive, send)
        scope["app"].shutdown = getattr(self._server, "should_exit", False)


class WSEndpoint(ServiceBase):  # noqa

    def __init__(self,
                 name: str,
                 host: str = None,
                 port: int = None,
                 broadcast: Any = None,
                 ssl_key: str = BaseConfig.CLOUD_SERVERS_SSL_KEY,
                 ssl_cert: str = BaseConfig.CLOUD_SERVERS_SSL_CERT,
                 ws_size: int = 10 * 1024 * 1024):
        super(WSEndpoint, self).__init__(
            name=name, host=host, port=port,
            ssl_key=ssl_key, ssl_cert=ssl_cert,
            protocol="ws"
        )
        self.buffer_size = ws_size
        self.app = FastAPI(
            routes=[
                APIRoute(
                    f"/{name}",
                    self.get_all_urls,
                    response_class=JSONResponse,
                ),
                WebSocketRoute(
                    f"/{name}",
                    broadcast
                )
            ],
        )
        self.app.shutdown = False

    def run(self, server: Any, **kwargs):
        self.app.add_middleware(
            WSEventMiddleware,
            name=self.name,
            server=server,
        )
        super(WSEndpoint, self).run(**kwargs)

    def close(self):
        self.app.shutdown = True
