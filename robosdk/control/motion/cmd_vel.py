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

from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.config import Config

from .base import MotionControl

__all__ = ("CmdVelMotion",)


@ClassFactory.register(ClassType.CONTROL, alias="ros_cmd_vel")
class CmdVelMotion(MotionControl):  # noqa

    def __init__(self, name: str = "cmd_vel", config: Config = None):
        super(CmdVelMotion, self).__init__(name=name, config=config)

    def connect(self):
        if self.has_connect:
            return
        self.has_connect = True

    def set_vel(self, linear: float = 0., rotational: float = 0.):
        msg = self.backend.msg_geometry_generator.Twist()

        msg.linear.x = linear
        msg.angular.z = rotational

        self.backend.publish(
            data=msg,
            data_class=self.backend.msg_geometry_generator.Twist,
            name=self.config.data.target
        )

    def close(self):
        self.has_connect = False
        self.stop()

    def reset(self):
        self.stop()
