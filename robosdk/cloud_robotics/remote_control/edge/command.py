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

import json
import threading
import time
import uuid
from typing import Any
from typing import Callable
from typing import Dict
from typing import Optional

from robosdk.cloud_robotics.edge_base import WSClient
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.constant import ActionStatus
from robosdk.common.constant import RemoteCommandCode
from robosdk.common.constant import RoboControlMode
from robosdk.common.logger import logging
from robosdk.utils.queue import BaseQueue
from robosdk.utils.util import parse_kwargs

__all__ = ("ControlWSClient", "ControlWSRobot", "ThreadControlDataManage")


class ThreadControlDataManage(threading.Thread):
    __semaphore__ = threading.Semaphore(1)

    def __init__(self, robot,
                 name_space: str = "",
                 data_func: Callable = None,
                 **kwargs
                 ):
        super(ThreadControlDataManage, self).__init__(daemon=True)
        self._queue = BaseQueue(keep_when_full=True)
        self.robot = robot
        name = self.robot.robot_name
        self.logger = logging.bind(
            instance=f"{name}.{name_space}CommandDTC",
            system=True
        )
        self.command = {
            RemoteCommandCode.UP: False, RemoteCommandCode.DOWN: False,
            RemoteCommandCode.LEFT: False, RemoteCommandCode.RIGHT: False
        }
        self.data_func = data_func
        self._data_kwargs = dict(kwargs)
        self.task_status = {}

    @property
    def ready(self) -> bool:
        return self.robot.control_mode == RoboControlMode.Remote

    def add_stream(self, data: Any):
        try:
            self._queue.put(data)
        except Exception as err:
            self.logger.error(
                f'Failed to add data, skip this frame: {err}')

    def run(self):
        while 1:
            self._execute_direction()
            control = self._queue.get()
            if not control:
                continue
            if self.data_func:
                control = self.data_func(control, **self._data_kwargs)
            self._execute_control(control)

    def _execute_direction(self):
        if not hasattr(self.robot, "motion"):
            return
        forward = (self.command[RemoteCommandCode.UP] * 1 -
                   self.command[RemoteCommandCode.DOWN] * 1)
        left_right = (self.command[RemoteCommandCode.LEFT] * 1 -
                      self.command[RemoteCommandCode.RIGHT] * 1)
        if forward == 1:
            self.robot.motion.go_forward()
        if forward == -1:
            self.robot.motion.go_backward()
        if left_right == 1:
            self.robot.motion.turn_left()
        if left_right == -1:
            self.robot.motion.turn_right()

        self.command = {
            RemoteCommandCode.UP: False, RemoteCommandCode.DOWN: False,
            RemoteCommandCode.LEFT: False, RemoteCommandCode.RIGHT: False
        }

    def _execute_control(self, command: str):
        control = json.loads(command)
        command = control.get("command", "")
        task_id = control.get("taskId", "")
        if len(task_id):
            self.task_status[task_id] = ActionStatus.ACTIVE.value
        self.logger.info(f"start to execute task {command}")
        action = getattr(self.robot, command)
        _param: Dict = parse_kwargs(action, **control)
        try:
            action(**_param)
        except Exception as err:  # noqa
            self.logger.error(f"failure to execute task {command}: {err}")
            if len(task_id):
                self.task_status[task_id] = ActionStatus.PREEMPTED.value
        else:
            self.logger.info(f"success to complete task {command}")
            if len(task_id):
                self.task_status[task_id] = ActionStatus.SUCCEEDED.value

    def close(self):
        self.join(timeout=20)


@ClassFactory.register(ClassType.CLOUD_ROBOTICS, "socket_control_client")
class ControlWSClient(WSClient):  # noqa

    def __init__(self, name: str = "control", **kwargs, ):
        super(ControlWSClient, self).__init__(
            name=name, **kwargs
        )

    def connect(self, **kwargs):
        super(ControlWSClient, self).connect(**kwargs)
        self.send({"command": "initial", "name": self.name})

    def start(self):
        self.send({"command": "start"})

    def stop(self):
        self.send({"command": "stop"})


@ClassFactory.register(ClassType.CLOUD_ROBOTICS, "socket_control_robot")
class ControlWSRobot(WSClient):  # noqa

    def __init__(self, robot,
                 name: str = "control",
                 **kwargs, ):

        super(ControlWSRobot, self).__init__(
            name=name, **kwargs
        )
        self.robot = robot
        self._worker: Dict[str, ThreadControlDataManage] = {}

    def add_worker(
            self, name_space: str = "",
            data_func: Callable = None,
            **kwargs
    ):
        w = ThreadControlDataManage(
            robot=self.robot, name_space=name_space,
            data_func=data_func, **kwargs
        )
        self._worker[name_space] = w

    def send(self, data: Dict):
        data["name"] = getattr(self.robot, "robot_name", "test")
        super(ControlWSRobot, self).send(data)

    def start(self):
        self.send({"command": "join"})
        setattr(self.robot, "control_mode", RoboControlMode.Remote)
        self.add_worker("Vel")
        self.add_worker("Task")

    def stop(self):
        self.send({"command": "leave"})
        for name, worker in self._worker.items():
            self.logger.debug(f"closing worker {name}")
            worker.close()
        self._worker = {}

    def run(self):
        for name, worker in self._worker.items():
            self.logger.debug(f"start worker {name}")
            worker.start()
        try:
            tasks = self._worker["Task"]
            move = self._worker["Vel"]
        except KeyError:
            self.logger.error("worker not started")
            return
        while 1:
            if len(tasks.task_status):
                self.send(
                    {"command": "sync_task",
                     "_kwargs": tasks.task_status}
                )
            received: Optional[Dict] = self.recv()
            if not received:
                time.sleep(.1)
                continue
            command = received.get("command", "")
            if not len(command):
                continue
            if command == "start":
                self.start()

            if command == "direction":  # basic move
                code = received.get("code", "")
                if not RemoteCommandCode.has_value(code):
                    self.logger.error(f"unidentified task: {code} {command}")
                    continue
                move.command[RemoteCommandCode(code)] = True
            elif (hasattr(self.robot, "skill") and
                  hasattr(self.robot.skill, command)):  # long-time task execute
                if "taskId" not in self.robot:
                    received["taskId"] = str(uuid.uuid4())
                data = json.dumps(received)
                self._tasks.add_stream(data)
            elif hasattr(self.robot, command):  # basic control, short time
                data = json.dumps(received)
                move.add_stream(data)
            else:
                self.logger.error(f"unidentified task: {command}")
