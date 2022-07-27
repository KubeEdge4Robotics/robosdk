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

import time
import json
import uuid
import threading
from typing import Dict
from typing import Optional

from robosdk.common.constant import ActionStatus
from robosdk.common.constant import RemoteCommandCode
from robosdk.utils.queue import BaseQueue
from robosdk.utils.util import parse_kwargs
from robosdk.cloud_robotics.edge_base import WSClient

__all__ = ("ControlWSClient", "ControlWSRobot",)


class _ThreadControlDataManage(threading.Thread):
    __semaphore__ = threading.Semaphore(1)

    def __init__(self, robot):
        super(_ThreadControlDataManage, self).__init__(daemon=True)
        self.queue = BaseQueue(keep_when_full=True)
        self.robot = robot
        self.command = {
            RemoteCommandCode.UP: False, RemoteCommandCode.DOWN: False,
            RemoteCommandCode.LEFT: False, RemoteCommandCode.RIGHT: False
        }
        self.task_status = {}

    def run(self):
        while 1:
            self.execute_direction()
            control = self.queue.get()
            if not control:
                continue
            self.execute_control(control)

    def execute_direction(self):
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

    def execute_control(self, command: str):
        control = json.loads(command)
        command = control.get("command", "")
        task_id = control.get("taskId", "")
        if len(task_id):
            self.task_status[task_id] = ActionStatus.ACTIVE.value
        self.robot.logger.info(f"start to execute task {command}")
        action = getattr(self.robot, command)
        _param: Dict = parse_kwargs(action, **control)
        try:
            action(**_param)
        except Exception as err:  # noqa
            self.robot.logger.error(f"failure to execute task {command}: {err}")
            if len(task_id):
                self.task_status[task_id] = ActionStatus.PREEMPTED.value
        else:
            self.robot.logger.info(f"success to complete task {command}")
            if len(task_id):
                self.task_status[task_id] = ActionStatus.SUCCEEDED.value

    def close(self):
        self.join(timeout=20)


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


class ControlWSRobot(WSClient):  # noqa

    def __init__(self, robot,
                 name: str = "control",
                 **kwargs, ):

        super(ControlWSRobot, self).__init__(
            name=name, **kwargs
        )
        self.robot = robot
        self._worker = _ThreadControlDataManage(robot=robot)
        self._tasks = _ThreadControlDataManage(robot=robot)

    def send(self, data: Dict):
        data["name"] = getattr(self.robot, "robot_name", "test")
        super(ControlWSRobot, self).send(data)

    def start(self):
        self.send({"command": "join"})

    def stop(self):
        self.send({"command": "leave"})
        self._tasks.close()
        self._worker.close()

    def run(self):
        self._worker.start()
        self._tasks.start()
        while 1:
            if len(self._tasks.task_status):
                self.send(
                    {"command": "sync_task",
                     "_kwargs": self._tasks.task_status}
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
                self._worker.command[RemoteCommandCode(code)] = True
            elif (hasattr(self.robot, "skill") and
                  hasattr(self.robot.skill, command)):  # long-time task execute
                if "taskId" not in self.robot:
                    received["taskId"] = str(uuid.uuid4())
                data = json.dumps(received)
                self._tasks.queue.put(data)
            elif hasattr(self.robot, command):  # basic control, short time
                data = json.dumps(received)
                self._worker.queue.put(data)
            else:
                self.logger.error(f"unidentified task: {command}")
                continue
