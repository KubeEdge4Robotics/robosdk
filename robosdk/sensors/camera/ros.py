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

import copy

import numpy as np

from robosdk.common.config import Config
from robosdk.common.config import BaseConfig
from robosdk.common.class_factory import ClassType
from robosdk.common.class_factory import ClassFactory
from robosdk.utils.lazy_imports import LazyImport

from .base import CameraBase
from .base import RGBDCameraBase

__all__ = ("RosCameraDriver", "RosRGBDCameraDriver")


@ClassFactory.register(ClassType.SENSOR, alias="ros_camera_driver")
class RosCameraDriver(CameraBase):  # noqa

    def __init__(self, name, config: Config = None):
        self.bridge = LazyImport("cv_bridge")
        super(RosCameraDriver, self).__init__(name=name, config=config)
        rgb_topic = self.config.rgb.target
        self.rgb_sub, _ = self.backend.subscribe(rgb_topic)
        self.info_sub, _ = self.backend.subscribe(
            self.config.info.target,
            callback=self._camera_info_callback,
        )
        self._rgb_data = None
        self.cv_bridge = self.bridge.CvBridge()

    @property
    def rgb(self):
        if self.rgb_data is not None:
            try:
                self._rgb_data = self.cv_bridge.imgmsg_to_cv2(
                    self.rgb_data, self.config.rgb.encoding)
                if (self.config.rgb.encoding == "bgr8" and
                        BaseConfig.MAC_TYPE.startswith("aarch")):
                    self._rgb_data = self._rgb_data[:, :, ::-1]
            except Exception as e:  # noqa
                self.logger.error(f"get rgb data from camera "
                                  f"[{self.sensor_name}] fail: {str(e)}")
        else:
            self._rgb_data = None
        return self._rgb_data

    def get_rgb(self):
        """
        This function returns the RGB image perceived by the camera.
        """
        self.camera_img_lock.acquire()
        ts = self.sys_time
        rgb = copy.deepcopy(self.rgb)
        self.camera_img_lock.release()
        return rgb, ts

    def _rgb_callback(self, rgb):
        self._info["rgb"]["count"] += 1
        if rgb is not None:
            self.rgb_data = rgb
        else:
            self._info["rgb"]["error"] += 1

    def _camera_info_callback(self, msg):
        self.camera_info_lock.acquire()
        self.camera_info = msg
        self.camera_P = np.array(msg.P).reshape((3, 4))
        self.camera_info_lock.release()

    def connect(self):
        if self.has_connect:
            self.logger.warning(
                f"sensor {self.sensor_name} has already connected")
            return
        self.has_connect = True
        self.rgb_sub.registerCallback(self._rgb_callback)

        self._info["rgb"] = {
            "count": 0, "error": 0, "target": self.config.rgb.target,
            "connect": self.sys_time, "close": 0
        }

    def close(self):
        self.has_connect = False
        self._info["rgb"]["close"] = self.sys_time
        self.backend.unsubscribe(self.rgb_sub, self.info_sub)


@ClassFactory.register(ClassType.SENSOR, alias="ros_rgbd_camera_driver")
class RosRGBDCameraDriver(RGBDCameraBase, RosCameraDriver):  # noqa

    def __init__(self, name, config: Config = None):
        super(RosRGBDCameraDriver, self).__init__(name=name, config=config)
        self.cv2 = LazyImport("cv2")
        self.sync = LazyImport("message_filters")
        self.rgb_depth = [None, None]
        depth_topic = self.config.depth.target
        self.depth_sub, _ = self.backend.subscribe(depth_topic)
        self._dep_data = None

    def _dep_callback(self, depth):
        self._info["depth"]["count"] += 1
        if depth is not None:
            self.dep_data = depth
        else:
            self._info["depth"]["error"] += 1

    def _rgbd_callback(self, rgb, depth):
        self._rgb_callback(rgb)
        self._dep_callback(depth)
        rgb, _ = self.get_rgb()
        depth, _ = self.get_depth()
        self.rgb_depth = [rgb, depth]

    @property
    def dep(self):
        if self.dep_data is not None:
            try:
                self._dep_data = self.cv_bridge.imgmsg_to_cv2(
                    self.dep_data, self.config.depth.encoding)
                self._dep_data = np.nan_to_num(self._dep_data)
            except Exception as e:  # noqa
                self.logger.error(f"get depth data from camera "
                                  f"[{self.sensor_name}] fail: {str(e)}")
        else:
            self._dep_data = None
        return self._dep_data

    def connect(self):
        if self.has_connect:
            self.logger.warning(
                f"sensor {self.sensor_name} has already connected")
            return
        img_subs = [self.rgb_sub, self.depth_sub]
        sync = self.sync.ApproximateTimeSynchronizer(
            img_subs, queue_size=10, slop=0.2
        )
        self.has_connect = True
        self.rgb_sub.registerCallback(self._rgb_callback)
        self.depth_sub.registerCallback(self._dep_callback)
        now = self.sys_time
        self._info["rgb"] = {
            "count": 0, "error": 0, "target": self.config.rgb.target,
            "connect": now, "close": 0
        }
        self._info["depth"] = {
            "count": 0, "error": 0, "target": self.config.depth.target,
            "connect": now, "close": 0
        }

        sync.registerCallback(self._rgbd_callback)

    def close(self):
        self.has_connect = False
        now = self.sys_time
        self._info["rgb"]["close"] = now
        self._info["depth"]["close"] = now
        self.backend.unsubscribe(
            self.rgb_sub, self.depth_sub, self.info_sub
        )

    def get_depth(self):
        """
        This function returns the depth image perceived by the camera.

        The depth image is in meters.

        :rtype: np.ndarray or None
        """
        self.camera_depth_lock.acquire()
        ts = self.sys_time
        depth = copy.deepcopy(self.dep)
        self.camera_depth_lock.release()
        if self.config.depth.map_factor:
            depth = depth / self.config.depth.map_factor
        else:
            depth = self.cv2.normalize(depth, depth, 0, 255,
                                       self.cv2.NORM_MINMAX)
        return depth, ts

    def get_rgb_depth(self):

        return self.rgb_depth
