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

from typing import Any
from typing import List
from typing import Optional

from robosdk.algorithms.base import AlgorithmBase
from robosdk.common.schema.stream import StreamClient

__all__ = ("ControlServer",)


class ControlServer(AlgorithmBase):  # noqa
    def __init__(self, name: str = "server", logger=None, ):
        super(ControlServer, self).__init__(logger=logger)
        self.controller: Optional[StreamClient] = None
        self.robots: List[StreamClient] = []
        self.should_exit = False
        self.tasks = {}
        self._room = name

    def __str__(self):
        return f"{self._room} Client ({self.number})"

    @property
    def number(self) -> int:
        return len(self.robots)

    def list_client(self) -> List:
        client = []
        if self.controller is not None:
            client.append(
                {"id": self.controller.id, "name": self.controller.name}
            )

        for robot in self.robots:
            client.append(
                {"id": robot.id, "name": robot.name}
            )

        return client

    def get_robot_by_id(self, id):
        robots = list(filter(lambda x: x.id == id, self.robots))
        return robots[0] if len(robots) else None

    def set_logger(self, logger):
        self.logger = logger

    def set_controller(self, user: StreamClient):
        self.controller = user

    def send(self, client: StreamClient, data: Any, **kwargs):
        raise NotImplementedError()

    async def async_send(self, client: StreamClient, data: Any, **kwargs):
        raise NotImplementedError()

    def add(self, robot: StreamClient, **kwargs):
        raise NotImplementedError()

    def remove(self, robot: StreamClient, **kwargs):
        raise NotImplementedError()

    def update_task(self, robot: StreamClient, **task_status):
        if robot.name not in self.tasks:
            self.tasks[robot.name] = dict(task_status)
        else:
            self.tasks[robot.name].update(task_status)

    def start(self):
        raise NotImplementedError()

    def stop(self):
        self.should_exit = True
        for robot in self.robots:
            self.logger.info(f'Stopping ControlServer for {robot}')
            self.remove(robot)
