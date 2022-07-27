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

from copy import deepcopy
from typing import Any
from typing import List
from typing import Tuple

import numpy as np
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.config import Config
from robosdk.utils.lazy_imports import LazyImport

from .base import LidarBase

__all__ = ("RosLaserDriver", )


@ClassFactory.register(ClassType.SENSOR, alias="ros_laser_driver")
class RosLaserDriver(LidarBase):  # noqa

    def __init__(self, name, config: Config = None):
        super(RosLaserDriver, self).__init__(name=name, config=config)
        parameters = getattr(self.config.data, "subscribe", None) or {}
        self.lidar_sub = self.backend.subscribe(
            self.config.data.target,
            callback=self._callback,
            **parameters
        )
        self._tf = LazyImport("tf")
        self._base_link = getattr(self.config.data, "base_link", "laser")
        self._map_frame = getattr(self.config.data, "map_frame", "map")

    def quat2mat(self, data: np.ndarray):

        listener = self._tf.TransformListener()
        listener.waitForTransform(
            self._base_link, self._map_frame,
            self.backend.client.Time(0),
            timeout=self.backend.client.Duration(10.)
        )

        trans, rotation = listener.lookupTransform(
            self._map_frame, self._base_link,
            self.backend.client.Time(0),
        )
        rotation = self._tf.transformations.quaternion_matrix(rotation)
        shape = data.shape
        s = 4 - shape[1]
        if s > 0:
            data = np.hstack((data, np.zeros((shape[0], s))))
        elif s < 0:
            data = data[..., : 4]
        points = rotation.dot(data.T).T
        points[..., 0] += trans[0]
        points[..., 1] += trans[1]
        points[..., 2] += trans[2]

        return points

    def _callback(self, laser_scan):
        self._raw = deepcopy(laser_scan)
        theta_left, theta_step, dist_min, dist_max, distances = (
            laser_scan.angle_min, laser_scan.angle_increment,
            laser_scan.range_min, laser_scan.range_max,
            np.array(laser_scan.ranges)
        )
        # generate the range of angles
        thetas = theta_left + theta_step * np.arange(len(distances))

        # filter out the angles with inappropriate distances
        valid = (distances >= dist_min) & (distances <= dist_max)
        xs: List[float] = distances[valid] * np.cos(thetas[valid])
        ys: List[float] = distances[valid] * np.sin(thetas[valid])
        self.points = np.array(list(zip(xs, ys))).astype(np.float32)

        if hasattr(laser_scan, "intensities"):
            self.intensity = np.asarray(self._raw.intensities)

    def connect(self):
        if self.has_connect:
            self.logger.warning(
                f"sensor {self.sensor_name} has already connected")
            return
        self.has_connect = True

    @property
    def data(self) -> np.ndarray:
        return self.points

    def get_points(self) -> Tuple[np.ndarray, Any]:
        self.data_lock.acquire()
        ts = self.sys_time
        data = deepcopy(self.data)
        self.data_lock.release()
        return data, ts
