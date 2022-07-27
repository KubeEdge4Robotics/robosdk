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
import pickle
import asyncio
from typing import Dict

import tenacity
from tenacity import retry
import websockets
from websockets.exceptions import InvalidStatusCode
from websockets.exceptions import WebSocketException
from websockets.exceptions import ConnectionClosedError
from websockets.exceptions import ConnectionClosedOK

from robosdk.common.logger import logging
from robosdk.common.config import BaseConfig
from robosdk.common.constant import ServiceConst

__all__ = ("ClientBase", "WSClient")


class ClientBase:

    def __init__(self, name: str = "base", **kwargs):
        self.name = name
        self.logger = logging.bind(
            instance=f"client_{name}", system=True
        )
        host = kwargs.get("host", "") or BaseConfig.CLOUD_SERVERS_HOST
        port = kwargs.get("port", "") or BaseConfig.CLOUD_SERVERS_PORT
        self.host = host or "127.0.0.1"
        self.port = (int(port) if str(port).isdigit()
                     else ServiceConst.SocketDefaultPort.value)
        self.uri = kwargs.get("uri", "") or self.get_endpoint()

    def get_endpoint(self):
        return f"{self.host}:{self.port}/{self.name}"

    @abc.abstractmethod
    def connect(self, **kwargs):
        ...

    @abc.abstractmethod
    def send(self, **kwargs):
        ...

    @abc.abstractmethod
    def close(self):
        ...

    def __del__(self):
        self.close()


class WSClient(ClientBase):  # noqa
    """Client that interacts with the cloud server."""
    _ws_timeout = ServiceConst.SocketTimeout.value
    max_size = ServiceConst.SocketMsgMax.value

    def __init__(self, name: str, **kwargs, ):
        super(WSClient, self).__init__(name=name, **kwargs)
        if not self.uri.startswith("ws"):
            self.uri = f"ws://{self.uri}"
        self.ws = None
        self.loop = asyncio.get_event_loop()
        self.kwargs = {}
        timeout = kwargs.get("ping_timeout", "")
        self.timeout = (int(timeout) if str(timeout).isdigit()
                        else self._ws_timeout)
        interval = kwargs.get("ping_interval", "")
        interval = int(interval) if str(interval).isdigit(
        ) else self._ws_timeout
        max_size = kwargs.get("max_size", "")
        max_size = int(max_size) if str(max_size).isdigit() else self.max_size
        self.kwargs.update({
            "ping_timeout": self.timeout,
            "ping_interval": interval,
            "max_size": min(max_size, 16 * 1024 * 1024)
        })

    @retry(
        stop=tenacity.stop_after_attempt(
            ServiceConst.APICallTryTimes.value
        ),
        retry=tenacity.retry_if_result(lambda x: x is None),
        wait=tenacity.wait_fixed(
            ServiceConst.APICallTryHold.value
        ))
    async def _connect(self):
        try:
            self.ws = await asyncio.wait_for(
                websockets.connect(
                    self.uri, **self.kwargs
                ), self._ws_timeout)
            self.logger.info(f"{self.uri} connection succeed")
            return self.ws
        except ConnectionRefusedError:
            self.logger.error(f"{self.uri} connection refused by server")
        except ConnectionClosedError:
            self.logger.error(f"{self.uri} connection lost")
        except ConnectionClosedOK:
            self.logger.error(f"{self.uri} connection closed")
        except InvalidStatusCode as err:
            self.logger.error(
                f"{self.uri} websocket failed - "
                f"with invalid status code {err.status_code}")
        except WebSocketException as err:
            self.logger.error(f"{self.uri} websocket failed - with {err}")
        except OSError as err:
            self.logger.error(f"{self.uri} connection failed - with {err}")

    @retry(
        stop=tenacity.stop_after_attempt(
            ServiceConst.APICallTryTimes.value
        ),
        retry=tenacity.retry_if_result(lambda x: x is None),
        wait=tenacity.wait_fixed(
            ServiceConst.APICallTryHold.value
        ))
    async def _send(self, data: Dict):
        if not self.ws:
            await self._connect()
        try:
            data = pickle.dumps(data)
            await asyncio.wait_for(self.ws.send(data), self._ws_timeout)
            return True
        except Exception as err:
            self.logger.error(f"{self.uri} send data failed - with {err}")

    async def _recv(self):
        result = await self.ws.recv()
        try:
            result = pickle.loads(result)
        except:  # noqa
            pass
        return result

    def connect(self, **kwargs):
        self.loop.run_until_complete(
            asyncio.wait_for(self._connect(), timeout=self.timeout)
        )

    def send(self, data: Dict):
        self.loop.run_until_complete(self._send(data))

    def recv(self):
        data = self.loop.run_until_complete(self._recv())
        return data

    def close(self):
        if self.ws is None:
            return
        self.ws.close()
        self.ws = None
