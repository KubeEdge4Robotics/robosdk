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
from typing import (
    Dict,
    List,
    Optional,
    Union
)

from fastapi import WebSocket
from fastapi.routing import APIRoute
from starlette.responses import JSONResponse
from starlette.endpoints import WebSocketEndpoint

from robosdk.cloud_robotics.cloud_base import WSEndpoint
from robosdk.common.exceptions import CloudError
from robosdk.common.constant import ServiceStatusCode
from robosdk.common.constant import ActionStatus
from robosdk.common.class_factory import ClassType
from robosdk.common.class_factory import ClassFactory
from robosdk.common.schema.stream import StreamClient
from robosdk.utils.util import parse_kwargs
from robosdk.algorithms.server.control import ControlServer


class BroadcastCtl(WebSocketEndpoint):
    encoding: str = "bytes"
    count: int = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.server: Optional[ControlServer] = None
        self.clients: List[WebSocket] = []

    async def on_connect(self, websocket: WebSocket):
        servername = websocket.scope['path'].lstrip("/")
        server: Optional[ControlServer] = self.scope.get(servername)
        if server is None:
            raise CloudError(
                "Server unavailable!", ServiceStatusCode.InternalServerError)
        self.server = server
        self.clients.append(websocket)
        await websocket.accept()

    async def close(self, _websocket: WebSocket):
        if _websocket in self.clients:
            self.clients.remove(_websocket)

    async def on_disconnect(self, _websocket: WebSocket, _close_code: int):
        self.clients.remove(_websocket)

    async def on_receive(self, _websocket: WebSocket, msg: bytes):
        msg = pickle.loads(msg)
        command = msg.get("command", "")
        client = msg.get("name", "")
        user = StreamClient(name=client, client=_websocket)
        _param = msg.get("_kwargs", None) or {}
        if command == "initial":
            if self.server.controller and user != self.server.controller:
                self.server.logger.warning(
                    f"new user {client} set to controller")
                await self.close(self.server.controller.client)
            self.server.set_controller(user)
        elif command == "start":
            self.server.start()
        elif command == "stop":
            self.server.stop()
        elif command == "join":
            self.server.add(user, **_param)
        elif command == "leave":
            self.server.remove(user, **_param)
            await self.close(_websocket)
        elif command == "sync_task":
            self.server.update_task(user, **_param)
        else:
            data = msg.get("data", {})
            self.server.send(user, data, **_param)


class ControlWSServer(WSEndpoint):  # noqa
    def __init__(self,
                 name: str = "control",
                 host: str = "0.0.0.0",
                 port: int = 5540,
                 use_backend: str = "socket_control_server",
                 **backend_parameter
                 ):
        super(ControlWSServer, self).__init__(
            name=name,
            broadcast=BroadcastCtl,
            host=host,
            port=port,
        )
        self.app.routes.append(
            APIRoute(
                f"/{name}/tasks",
                self.get_all_tasks,
                response_class=JSONResponse,
            ),
        )
        self.app.routes.append(
            APIRoute(
                f"/{name}/tasks/" + "{robot}",
                self.get_robot_task,
                response_class=JSONResponse,
                methods=["GET"]
            ),
        )
        my_server = ClassFactory.get_cls(
            ClassType.CLOUD_ROBOTICS, use_backend
        )
        all_k: Dict = parse_kwargs(my_server, **backend_parameter)
        self.server: ControlServer = my_server(**all_k)

        self.server.set_logger(self.logger)

    def run(self, **kwargs):
        super(ControlWSServer, self).run(server=self.server)

    def get_all_tasks(self):
        return self.server.tasks

    def get_robot_task(self, robot: str, taskid: Union[str, None] = None):
        if taskid:
            return {
                taskid: self.server.tasks.get(robot, {}).get(
                    taskid, ActionStatus.UNKONWN.value)
            }
        return self.server.tasks.get(robot, {})


if __name__ == '__main__':
    server = ControlWSServer()
    server.run()
