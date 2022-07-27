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

import typing
from decimal import Decimal
from pathlib import Path

import numpy as np
from pydantic import BaseModel
from robosdk.utils.util import euler_to_q
from robosdk.utils.util import q_to_euler

from .pose import BasePose

__all__ = ("PgmMap",)


class PgmMap(BaseModel):
    image: typing.Optional[Path] = None
    size: typing.List = [200, 200]
    map_data: typing.Optional[typing.Any] = None
    resolution: typing.Union[float, Decimal]
    origin: typing.List
    reverse: typing.Union[int, bool]
    occupied_thresh: Decimal
    free_thresh: Decimal
    padding_map: typing.Optional[typing.List] = None

    def pixel2world(self,
                    x: float = 0.,
                    y: float = 0.,
                    z: float = 0.,
                    trans: bool = True) -> BasePose:

        data = np.array([x, y]).astype(int)
        if self.padding_map is not None:
            data += self.padding_map[:2]
        data[1] = self.size[0] - data[1]
        x, y = list(
            np.array(self.origin)[:2] + data * self.resolution
        )
        pose = BasePose(x=x, y=y, z=z)
        if trans:
            q = euler_to_q(pose)
            pose.z = q.z
            pose.w = q.w
        return pose

    def world2pixel(self, x, y, z=0.0, w=0.0, trans: bool = True) -> BasePose:
        p1 = (np.array([x, y]) - self.origin[:2]) / self.resolution
        p1[1] = self.size[0] - p1[1]
        if self.padding_map is not None:
            p1 -= self.padding_map[:2]
        px, py = int(p1[0] + 0.5), int(p1[1] + 0.5)
        pose = BasePose(x=px, y=py, z=z, w=w)
        if trans:
            q = q_to_euler(pose)
            pose.z = q.z
            pose.w = 0.0
        return pose

    def batch_pixel2world(self, points) -> np.ndarray:
        data = np.array(points).astype(int)
        if self.padding_map is not None:
            data += self.padding_map[:2]
        data[:, 1] = self.size[0] - data[:, 1]
        data[..., :2] = (np.array(self.origin)[:2] +
                         (data[..., :2] * self.resolution))
        return data

    def batch_world2pixel(self, points) -> np.ndarray:
        p1 = (np.array(points[:, [0, 1]]) - self.origin[:2]) / self.resolution
        p1[:, 1] = self.size[0] - p1[:, 1]
        if self.padding_map is not None:
            p1 -= self.padding_map[:2]
        x_max, y_max = self.map_data.shape[0], self.map_data.shape[1]
        valid = ((0 <= p1[:, 0]) & (p1[:, 0] <= x_max) &
                 (0 <= p1[:, 1]) & (p1[:, 1] <= y_max))
        pixel = np.unique((p1[valid] + 0.5).astype(int), axis=0)
        return pixel

    def calc_obstacle_map(self, obstacles: typing.List) -> typing.List:
        if not len(obstacles):
            return obstacles
        obstacles = np.array(obstacles)
        row = obstacles[:, 0]
        col = obstacles[:, 1]
        x_min, x_max = min(row), max(row)
        y_min, y_max = min(col), max(col)
        self.map_data = self.map_data[x_min:x_max, y_min:y_max]
        self.padding_map = [y_min, x_min, 0]
        obstacles = obstacles - [y_min, x_min]
        return obstacles
