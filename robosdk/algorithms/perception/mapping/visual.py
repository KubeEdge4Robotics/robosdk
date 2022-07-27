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

import numpy as np
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.constant import PgmColor
from robosdk.common.schema.map import PgmMap
from robosdk.common.schema.pose import BasePose
from robosdk.utils.lazy_imports import LazyImport

from .base import MappingBase

__all__ = ("RosMapVisual",)


@ClassFactory.register(ClassType.PERCEPTION)
class RosMapVisual(MappingBase):  # noqa

    def __init__(self, logger=None):
        super(RosMapVisual, self).__init__(logger=logger)
        self._cv2 = LazyImport("cv2")
        self.localizer = None
        self.raw_map = None
        self.curr_frame = None

    def initial_map(self, map_data: PgmMap):
        map_data.map_data = np.clip(map_data.map_data, 0, 255).astype(np.uint8)
        self.raw_map = map_data
        self.curr_frame = deepcopy(self.raw_map.map_data)

    def add_laser(self, scan: np.ndarray):
        if self.curr_frame is None:
            return
        if scan is not None:
            scan_pixel = self.raw_map.batch_world2pixel(scan)
        else:
            scan_pixel = []
        for point in scan_pixel:
            self._cv2.circle(
                self.curr_frame, (point[0], point[1]), 0,
                PgmColor.LASER.value
            )

    def add_robot(self, location: BasePose, robot_size: int = 5):
        if self.raw_map is None:
            return
        self.logger.debug(f"get robot point @ {location}")
        pixel = self.raw_map.world2pixel(
            location.x, location.y,
            location.z, trans=False
        )

        mx = self.curr_frame.shape
        x1 = max(int(pixel.x - robot_size), 0)
        y1 = max(int(pixel.y - robot_size), 0)
        x2 = min(int(pixel.x + robot_size), mx[0])
        y2 = min(int(pixel.y + robot_size), mx[1])
        _ = self._cv2.rectangle(
            self.curr_frame, (x1, y1), (x2, y2),
            PgmColor.ROBOT.value, 1
        )
        _ = self._cv2.circle(
            self.curr_frame, (int(pixel.x), int(pixel.y)), 1,
            PgmColor.ROBOT.value
        )

    def add_label(self,
                  x: int = 0,
                  y: int = 0,
                  kind: str = "marker",
                  size: int = 1,
                  name: str = ""):

        if self.curr_frame is None:
            return
        _type = getattr(PgmColor, str(kind).upper(), PgmColor.UNKNOWN)
        color = _type.value
        if _type.name == "WAYPOINT":
            marker_type = self._cv2.MARKER_TRIANGLE_DOWN
        else:
            marker_type = self._cv2.MARKER_DIAMOND
        self._cv2.drawMarker(self.curr_frame, (x, y), color,
                             markerType=marker_type)
        self._cv2.putText(
            self.curr_frame, name, (x - size, y - size),
            self._cv2.FONT_HERSHEY_PLAIN, size,
            PgmColor.TEXT.value, size
        )
