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

from typing import (
    Tuple,
    Any
)

import numpy as np

from robosdk.sensors.base import SensorBase
from robosdk.common.config import Config
from robosdk.common.schema.pose import BasePose


__all__ = ("IMUBase", )


class IMUBase(SensorBase):  # noqa

    def __init__(self, name, config: Config = None):
        super(IMUBase, self).__init__(name=name, config=config)
        self.sensor_kind = "imu"

    def get_orientation(self) -> Tuple[BasePose, Any]:
        raise NotImplementedError

    def get_angular_velocity(self) -> Tuple[BasePose, Any]:
        raise NotImplementedError

    def get_linear_acceleration(self) -> Tuple[BasePose, Any]:
        raise NotImplementedError

    @staticmethod
    def q_to_euler(q: BasePose) -> np.ndarray:
        """ Returns the roll, pitch, yaw from the IMU quaternions """
        orientation = np.zeros(3)
        orientation[0] = np.arctan2(
            2 * (q.w * q.x + q.y * q.z),
            (1 - 2 * (q.x ** 2 * q.y ** 2))
        )
        orientation[1] = np.arcsin(
            2 * (q.w * q.y - q.x * q.z)
        )
        orientation[2] = np.arctan2(
            2 * (q.w * q.z + q.x * q.y),
            (1 - 2 * (q.y ** 2 * q.z ** 2))
        )
        return orientation
