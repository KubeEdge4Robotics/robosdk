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
from typing import Tuple

from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.config import Config
from robosdk.common.schema.pose import BasePose
from robosdk.sensors.base import RosSensorBase

from .base import IMUBase

__all__ = ("RosIMUDriver", )


@ClassFactory.register(ClassType.SENSOR, alias="ros_imu_driver")
class RosIMUDriver(RosSensorBase, IMUBase):  # noqa

    def __init__(self, name, config: Config = None):
        super(RosIMUDriver, self).__init__(name=name, config=config)
        self.frame_id = getattr(self.config.data, "frame_id", "") or "base_link"

    def get_orientation(self) -> Tuple[BasePose, Any]:
        orientation = BasePose()
        ts = self.sys_time
        if self._raw is not None:
            data = getattr(self._raw, "orientation", None)
            if data is not None:
                orientation.x = data.x
                orientation.y = data.y
                orientation.z = data.z
                orientation.w = data.w
        return orientation, ts

    def get_angular_velocity(self) -> Tuple[BasePose, Any]:
        angel = BasePose()
        ts = self.sys_time
        if self._raw is not None:
            data = getattr(self._raw, "angular_velocity", None)
            if data is not None:
                angel.x = data.x
                angel.y = data.y
                angel.z = data.z
        return angel, ts

    def get_linear_acceleration(self) -> Tuple[BasePose, Any]:
        linear = BasePose()
        ts = self.sys_time
        if self._raw is not None:
            data = getattr(self._raw, "linear_acceleration", None)
            if data is not None:
                linear.x = data.x
                linear.y = data.y
                linear.z = data.z
        return linear, ts

    def update(self,
               orientation: BasePose = None,
               linear_acceleration: BasePose = None,
               angular_velocity: BasePose = None,
               ):
        imu = self.backend.msg_sensor_generator.Imu()
        imu.header.frame_id = self.frame_id
        imu.header.stamp = self.backend.now
        if orientation is None:
            orientation = BasePose()
        imu.orientation.w = orientation.w
        imu.orientation.x = orientation.x
        imu.orientation.y = orientation.y
        imu.orientation.z = orientation.z
        if linear_acceleration is None:
            linear_acceleration = BasePose()
        imu.linear_acceleration.x = linear_acceleration.x
        imu.linear_acceleration.y = linear_acceleration.y
        imu.linear_acceleration.z = linear_acceleration.z
        if angular_velocity is None:
            angular_velocity = BasePose()
        imu.angular_velocity.x = angular_velocity.x
        imu.angular_velocity.y = angular_velocity.y
        imu.angular_velocity.z = angular_velocity.z

        self.backend.publish(data=imu,
                             data_class=self.backend.msg_sensor_generator.Imu,
                             name=self.config.data.target)
