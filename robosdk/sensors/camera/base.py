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

import threading
from typing import Tuple, Optional, Any

import numpy as np

from robosdk.sensors.base import SensorBase
from robosdk.common.config import Config


class CameraBase(SensorBase):  # noqa
    """
    This is a parent class on which the robot
    specific Camera classes would be built.
    """

    def __init__(self, name, config: Config = None):
        super(CameraBase, self).__init__(name=name, config=config)
        self.camera_info_lock = threading.RLock()
        self.camera_img_lock = threading.RLock()
        self.camera_info = None
        self.camera_P = None
        self.sensor_kind = "camera"
        self.rgb_data = None

    def get_rgb(self) -> Tuple[np.array, Any]:
        """
        This function returns the RGB image perceived by the camera.
        """
        raise NotImplementedError

    def get_intrinsics(self) -> Optional[np.array]:
        """
        This function returns the camera intrinsics.

        :rtype: np.ndarray
        """
        raise NotImplementedError


class RGBDCameraBase(SensorBase):  # noqa
    def __init__(self, name, config: Config = None):
        super(RGBDCameraBase, self).__init__(name=name, config=config)
        self.camera_depth_lock = threading.RLock()
        self.dep_data = None

    def get_depth(self) -> Tuple[np.array, Any]:
        """
        This function returns the depth image perceived by the camera.
        """
        raise NotImplementedError

    def get_rgb_depth(self) -> Tuple[np.array, np.array]:
        """
        This function returns both the RGB and depth
        images perceived by the camera.
        The depth image is in meters.
        :rtype: np.ndarray or None
        """
        raise NotImplementedError
