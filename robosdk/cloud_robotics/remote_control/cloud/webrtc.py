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

import asyncio
import itertools
import json
import os
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

import socketio
from aiortc import RTCIceServer
from fastapi import FastAPI
from fastapi import Request
from fastapi.routing import APIRoute
from robosdk.algorithms.server.control import ControlServer
from robosdk.cloud_robotics.cloud_base import ServiceBase
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.config import BaseConfig
from robosdk.common.fileops import FileOps
from robosdk.common.schema.stream import StreamClient
from robosdk.utils.util import parse_kwargs
from starlette.responses import FileResponse
from starlette.responses import JSONResponse

__all__ = ("WebRTCControlServer", )


class RTCClients:

    def __init__(self, _id: str, sio: socketio.AsyncServer):
        self._client = sio
        self._id = _id

    async def send_json(self, data: Dict):
        event = data.get("event", "")
        if not event:
            return
        data = data.get("data", {})

        await self._client.emit(
            event, data,
            to=self._id
        )


class BroadcastCtl:
    DISCONNECT_DELAY_S = 1
    INACTIVE_DELAY_S = 5
    PING_TIME_OUT = 60

    def __init__(self,
                 use_backend: str,
                 logger: None,
                 auth_func: Callable = None,
                 async_mode: str = "asgi",
                 cors_allowed_origins: Union[str, list] = '*',
                 **backend_parameter
                 ):

        self.logger = logger
        self._server = ClassFactory.get_cls(
            ClassType.CLOUD_ROBOTICS_ALG, use_backend
        )
        self._server_d: Dict = parse_kwargs(self._server, **backend_parameter)
        self.room_manager: Dict[str, ControlServer] = {}
        self._auth = auth_func
        self._sio = socketio.AsyncServer(
            async_mode=async_mode,
            ping_timeout=self.PING_TIME_OUT,
            cors_allowed_origins=cors_allowed_origins)
        self._lock = asyncio.Lock()
        self._all_rooms: Dict[str, ControlServer] = {}

    def auth(self, data: Dict) -> bool:
        if self._auth is None:
            return True
        return self._auth(**data)

    @property
    def sio(self) -> socketio.AsyncServer:
        """Return the Socket.IO instance."""
        return self._sio

    def initial(self):
        self.sio.on("connect", self.on_connect)
        self.sio.on("disconnect", self.disconnect)

        self.sio.on("join-room", self.join_room)
        self.sio.on("send-ice-candidate", self.ice_candidate)
        self.sio.on("make-peer-call-answer", self.make_call_answer)
        self.sio.on("call-all", self.call_all)
        self.sio.on("call-peer", self.call_peer)
        self.sio.on("call-ids", self.call_ids)
        self.sio.on("close-all-room-peer-connections", self.close)

    async def on_connect(self, id, env):
        if "asgi.scope" in env:
            headers = dict(env["asgi.scope"].get("headers", []))
            if not self.auth(headers):
                self.logger.info(f'inactive: {id}')
                await self.sio.disconnect(id)
                return

    async def disconnect(self, id):
        if id not in self.room_manager:
            return
        room: ControlServer = self.room_manager[id]
        self.logger.info(f"disconnect {id} from {room}")

        robot = room.get_robot_by_id(id)
        if robot is None:
            return
        room.remove(robot)
        del self.room_manager[id]
        await self.sio.disconnect(id)

    async def disconnect_inactive_user(self, room):
        await asyncio.sleep(self.INACTIVE_DELAY_S)

        for s in room.list_client():
            sid = s.get("id", "")
            if sid not in self.room_manager:
                self.logger.info(f'disconnect_inactive_user: {sid}')
                await self.sio.disconnect(sid)
                return

    async def add_client(self, robot: StreamClient, room: ControlServer):
        async with self._lock:
            if robot.id in self.room_manager:
                return
            self.room_manager[robot.id] = room
            room.add(robot)
            return True

    async def get_room(self, room: str) -> Optional[ControlServer]:
        async with self._lock:
            if not len(room):
                return
            if room not in self._all_rooms:
                self._all_rooms[room] = self._server(
                    name=room, logger=self.logger,
                    **self._server_d
                )
            return self._all_rooms[room]

    async def join_room(self, id, data: Dict):
        room_name = data.get("room", "")
        self.logger.info(f'join_room {id} ==> ({room_name})')

        if not len(room_name):
            return False
        client = RTCClients(
            _id=id, sio=self.sio
        )
        robot = StreamClient(
            id=id,
            name=data.get("name", id),
            client=client
        )
        room = await self.get_room(room_name)
        await self.add_client(robot, room)
        await self.disconnect_inactive_user(room)

        _data = {
            "event": 'room-clients',
            "data": room.list_client()
        }
        await room.async_send(robot, _data)
        return True

    async def _call_client(self, from_id: str, data: Dict, event: str):
        if "toId" not in data:
            return
        to_id = data["toId"]
        room1 = self.room_manager.get(from_id, None)
        room2 = self.room_manager.get(to_id, None)
        if not (room1 and room2):
            return
        _form = room1.get_robot_by_id(from_id)
        _to = room2.get_robot_by_id(data['toId'])
        self.logger.info(
            f'{event}: {_form} ({room1}) to {_to} ({room2}): {data}'
        )
        if room1 == room2:
            data['fromId'] = from_id
            await self.sio.emit(event, data, to=to_id)

    async def ice_candidate(self, from_id: str, data: Dict):
        await self._call_client(from_id, data, 'ice-candidate-received')

    async def call_peer(self, from_id, data):
        await self._call_client(from_id, data, 'peer-call-received')

    async def make_call_answer(self, from_id, data):
        await self._call_client(from_id, data, 'peer-call-answer-received')

    async def call_all(self, from_id):
        self.logger.info(f'call-all by {from_id}')
        room = self.room_manager.get(from_id, None)

        if room is not None:
            clients = room.list_client()
            ids = [client['id'] for client in clients]
            await self._make_peer_calls(ids)

    async def call_ids(self, from_id, ids: List):
        self.logger.info(f'call-id {from_id} - {ids}')
        room = self.room_manager.get(from_id, None)

        if room is not None:
            clients = room.list_client()
            all_ids = [client['id'] for client in clients]
            ids.append(from_id)
            await self._make_peer_calls(list(set(ids) & set(all_ids)))

    async def _make_peer_calls(self, ids):
        combinations = list(itertools.combinations(ids, 2))

        tasks = []
        for _id in ids:
            ids_to_call = [c[1] for c in combinations if c[0] == _id]
            if not len(ids_to_call):
                continue
            tasks.append(self.sio.emit('make-peer-call', ids_to_call, to=_id))
            self.logger.info(f'make-peer-call {_id} <- {ids_to_call}')

        await asyncio.wait(tasks)

    async def close(self, from_id):
        self.logger.info(f'close-all-room-peer-connections {from_id}')
        room = self.room_manager[from_id]
        robot = room.get_robot_by_id(from_id)
        data = {
            "event": "close-all-peer-connections-request-received"
        }
        if room is not None:
            await room.async_send(robot, data)


@ClassFactory.register(ClassType.CLOUD_ROBOTICS, "webrtc_control_server")
class WebRTCControlServer(ServiceBase):  # noqa

    def __init__(self,
                 name: str = "control",
                 host: str = "0.0.0.0",
                 port: int = 5540,
                 static_folder: str = "",
                 auth_func: Callable = None,
                 async_mode: str = "asgi",
                 cors_allowed_origins: Union[str, list] = '*',
                 ice_servers: str = "",
                 mount_location: str = "/",
                 socketio_path: str = "socket.io",
                 use_backend: str = "socket_control_server",
                 **backend_parameter
                 ):
        super(WebRTCControlServer, self).__init__(
            name=name, host=host, port=port, static_folder=static_folder
        )
        self.server = BroadcastCtl(
            use_backend=use_backend,
            logger=self.logger,
            auth_func=auth_func,
            async_mode=async_mode,
            cors_allowed_origins=cors_allowed_origins,
            **backend_parameter
        )
        _app = socketio.ASGIApp(
            socketio_server=self.server.sio,
            socketio_path=socketio_path
        )

        self._ice_servers = []
        if not ice_servers:
            ice_servers = BaseConfig.ICE_SERVER_URLS
        try:
            _ice_servers = FileOps.download(ice_servers)
        except:  # noqa
            _ice_servers = ""
        if os.path.isfile(_ice_servers):
            try:
                with open(ice_servers) as fin:
                    self._ice_servers = [
                        RTCIceServer(**json.load(fin)).__dict__
                    ]
            except:  # noqa
                self._ice_servers = []

        self.app = FastAPI(
            routes=[
                APIRoute(
                    f"/{name}",
                    self.get_all_urls,
                    response_class=JSONResponse,
                ),
                APIRoute(
                    f"/{name}/offer",
                    self.offer,
                    methods=["POST"],
                    response_class=JSONResponse,
                ),
                APIRoute(
                    f"/{name}/iceservers",
                    self.get_ice_servers,
                    response_class=JSONResponse,
                ),
                APIRoute(
                    f"/{name}/get_world_map",
                    self.get_world_map,
                    methods=["GET"],
                    response_class=FileResponse,
                ),
            ],
        )
        self.map_file = ""
        self.app.shutdown = False
        self.app.mount(mount_location, _app)  # noqa

    def set_world_map(self, map_file: str):
        self.map_file = map_file

    async def get_world_map(self, request: Request):
        if (self.server.auth(dict(request.headers))
                and os.path.isfile(self.map_file)):
            filename = os.path.basename(self.map_file)
            return FileResponse(self.map_file, filename=filename)
        return

    def run(self, **kwargs):
        self.server.initial()
        super(WebRTCControlServer, self).run(**kwargs)

    async def get_ice_servers(self, request: Request):
        if self.server.auth(dict(request.headers)):
            return self._ice_servers
        return []

    async def offer(self, request):
        pass

    def close(self):
        self.app.shutdown = True
