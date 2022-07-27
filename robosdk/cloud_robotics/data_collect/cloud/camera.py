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

import pickle
from typing import Dict
from typing import Optional

from fastapi import WebSocket
from robosdk.algorithms.server.monitor import MonitorServer
from robosdk.cloud_robotics.cloud_base import WSEndpoint
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.constant import ServiceStatusCode
from robosdk.common.exceptions import CloudError
from robosdk.utils.util import parse_kwargs
from starlette.endpoints import WebSocketEndpoint

__all__ = ("CameraWSServer", )


class _BroadcastCam(WebSocketEndpoint):
    encoding: str = "bytes"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.server: Optional[MonitorServer] = None

    async def on_connect(self, websocket: WebSocket):
        servername: Optional[str] = websocket.scope['path'].lstrip("/")
        server: Optional[MonitorServer] = self.scope.get(servername)
        if server is None:
            raise CloudError(
                "Server unavailable!", ServiceStatusCode.InternalServerError)
        self.server = server
        await websocket.accept()

    async def on_disconnect(self, _websocket: WebSocket, _close_code: int):
        if self.server is None:
            raise CloudError(
                "Server unavailable!", ServiceStatusCode.InternalServerError)
        self.server.stop()

    async def on_receive(self, _websocket: WebSocket, msg: bytes):
        msg = pickle.loads(msg)
        command = msg.get("command", "")
        channel = msg.get("channel", "") or "camera"
        _param = msg.get("_kwargs", None) or {}
        if command == "add":
            self.server.add(channel, **_param)
        elif command == "start":
            self.server.start()
        elif command == "stop":
            self.server.stop()
        else:
            data = msg.get("data", "")
            self.server.streaming(channel, data, **_param)


@ClassFactory.register(ClassType.CLOUD_ROBOTICS, "camera_server")
class CameraWSServer(WSEndpoint):  # noqa

    _support_protocol = (
        "rtsp", "file"
    )

    def __init__(self,
                 name: str = "camera",
                 host: str = "0.0.0.0",
                 port: int = 5540,
                 protocol: str = "rtsp",
                 use_backend: str = None,
                 **backend_parameter
                 ):

        super(CameraWSServer, self).__init__(
            name=name,
            broadcast=_BroadcastCam,
            host=host,
            port=port,
        )

        if protocol not in self._support_protocol:
            msg = f"CameraServer: {name} with `{protocol}` is not supported."
            raise CloudError(msg, ServiceStatusCode.InternalServerError)
        if not use_backend:
            use_backend = f"{protocol}_camera_server"
        self.server = ClassFactory.get_cls(
            ClassType.CLOUD_ROBOTICS_ALG, use_backend
        )
        all_k: Dict = parse_kwargs(self.server, **backend_parameter)
        self.server = self.server(**all_k)
        self.server.set_logger(self.logger)

    def run(self, **kwargs):
        super(CameraWSServer, self).run(server=self.server)
