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
import math
from typing import List

from robosdk.algorithms.base import AlgorithmBase
from robosdk.common.schema.map import PgmMap
from robosdk.common.schema.pose import BasePose
from robosdk.common.schema.pose import PoseSeq


class PathMaker(AlgorithmBase):  # noqa
    motion = [[1, 0, 1],
              [0, 1, 1],
              [-1, 0, 1],
              [0, -1, 1],
              [-1, -1, math.sqrt(2)],
              [-1, 1, math.sqrt(2)],
              [1, -1, math.sqrt(2)],
              [1, 1, math.sqrt(2)]]

    def __init__(self,
                 world_map: PgmMap,
                 start: BasePose,
                 goal: BasePose,
                 logger=None):
        super(PathMaker, self).__init__(logger=logger)
        self.world = world_map
        self.s_start = self.world.world2pixel(x=start.x, y=start.y, z=start.z)
        self.s_goal = self.world.world2pixel(x=goal.x, y=goal.y, z=start.z)

    def planning(self, **kwargs) -> PoseSeq:
        raise NotImplementedError()

    def set_motion(self, motions: List):
        self.motion = motions.copy()
