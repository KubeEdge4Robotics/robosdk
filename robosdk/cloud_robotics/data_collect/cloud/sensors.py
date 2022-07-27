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
import datetime
import os.path
import pickle
from typing import Dict
from typing import Optional

from fastapi import WebSocket
from robosdk.algorithms.server.transform import MessageDumper
from robosdk.cloud_robotics.cloud_base import WSEndpoint
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.config import BaseConfig
from robosdk.common.constant import DateTimeFormat
from robosdk.common.constant import ServiceStatusCode
from robosdk.common.exceptions import CloudError
from robosdk.utils.util import parse_kwargs
from starlette.endpoints import WebSocketEndpoint


class _BroadcastDS(WebSocketEndpoint):
    encoding: str = "bytes"
    count: int = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dumper: Optional[MessageDumper] = None
        self.client: Optional[WebSocket] = None

    async def on_connect(self, websocket: WebSocket):
        servername = websocket.scope['path'].lstrip("/")
        dumper: Optional[MessageDumper] = self.scope.get(servername)
        if dumper is None:
            raise CloudError(
                "Server unavailable!", ServiceStatusCode.InternalServerError)
        self.dumper = dumper
        self.client = websocket
        await websocket.accept()

    async def on_disconnect(self, _websocket: WebSocket, _close_code: int):
        self.dumper.close()

    async def on_receive(self, _websocket: WebSocket, msg: bytes):
        msg: Dict = pickle.loads(msg)
        command = msg.get("command", "")

        if command == "start":
            self.dumper.open()
        elif command == "stop":
            self.dumper.close()
        else:
            name = msg.get("name", "")
            data = msg.get("data", None)
            _param = msg.get("_kwargs", None) or {}
            if not (name and data):
                return
            all_k: Dict = parse_kwargs(self.dumper.write, **_param)
            all_k["name"] = name
            all_k["data"] = data
            self.dumper.write(**all_k)


@ClassFactory.register(ClassType.CLOUD_ROBOTICS, "data_collect_server")
class CollectWSServer(WSEndpoint):  # noqa
    def __init__(self,
                 file_out: str = None,
                 name: str = "dataCollect",
                 host: str = "0.0.0.0",
                 port: int = 5540,
                 use_backend: str = "json_dumper",
                 **backend_parameter
                 ):
        super(CollectWSServer, self).__init__(
            name=name,
            broadcast=_BroadcastDS,
            host=host,
            port=port,
        )
        if not file_out:
            now = datetime.datetime.now().strftime(DateTimeFormat)
            file_out = os.path.join(
                BaseConfig.TEMP_DIR, f"{name}-{now}"
            )
        self.server = ClassFactory.get_cls(
            ClassType.CLOUD_ROBOTICS_ALG, use_backend
        )
        all_k: Dict = parse_kwargs(self.server, **backend_parameter)
        self.server = self.server(file_out=file_out, **all_k)

        self.server.set_logger(self.logger)

    def run(self, **kwargs):
        super(CollectWSServer, self).run(server=self.server)
