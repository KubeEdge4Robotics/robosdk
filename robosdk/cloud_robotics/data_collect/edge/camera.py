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

from robosdk.cloud_robotics.edge_base import WSClient
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType

__all__ = ("CameraWSClient", )


@ClassFactory.register(ClassType.CLOUD_ROBOTICS, "camera_client")
class CameraWSClient(WSClient):  # noqa

    def __init__(self, name: str = "camera", **kwargs, ):

        super(CameraWSClient, self).__init__(
            name=name, **kwargs
        )

    def add_stream(self, name: str, **kwargs):
        self.send({"command": "add", "channel": name, "_kwargs": kwargs})

    def start(self):
        self.send({"command": "start"})

    def stop(self):
        self.send({"command": "stop"})

    def stream(self, name: str, data: Any, **kwargs):
        self.send({
            "command": "stream",
            "channel": name,
            "data": data,
            "_kwargs": kwargs
        })
