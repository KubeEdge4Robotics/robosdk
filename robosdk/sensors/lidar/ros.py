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

import numpy as np

from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.config import Config
from robosdk.utils.lazy_imports import LazyImport
from robosdk.sensors.base import RosSensorBase

from .base import LidarBase


__all__ = ("RosLidarDriver", )


@ClassFactory.register(ClassType.SENSOR, alias="ros_lidar_driver")
class RosLidarDriver(RosSensorBase, LidarBase):  # noqa

    def __init__(self, name, config: Config = None):
        super(RosLidarDriver, self).__init__(name=name, config=config)
        self.ros2array = LazyImport("ros_numpy.point_cloud2")
        self.frame_id = getattr(self.config.data, "frame_id", "") or "/lidar"

    def _callback(self, data):
        super(RosLidarDriver, self)._callback(data=data)
        if self._raw is None:
            return np.zeros((1800, 4))
        msg_cloud = self.pointcloud2_to_array(self._raw)
        _shape = msg_cloud.shape
        x = np.nan_to_num(msg_cloud['x'])
        y = np.nan_to_num(msg_cloud['y'])
        z = np.nan_to_num(msg_cloud['z'])
        i = np.nan_to_num(msg_cloud['intensity']) / 255.0

        if len(_shape) == 1:
            # velodyne point cloud
            points = np.zeros((_shape[0], 3))
        else:
            points = np.zeros((_shape[0], _shape[1], 3))
            i = i.reshape(-1)
        points[..., 0] = x
        points[..., 1] = y
        points[..., 2] = z
        if len(points.shape) == 3:
            self.points = points.astype(np.float32).reshape(-1, 3)
        else:
            self.points = points.astype(np.float32)
        self.intensity = i
