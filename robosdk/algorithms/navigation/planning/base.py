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

from robosdk.common.schema.pose import BasePose
from robosdk.common.schema.pose import PoseSeq
from robosdk.common.constant import ActionStatus
from robosdk.algorithms.base import AlgorithmBase


__all__ = ("MovePlanner",)


class MovePlanner(AlgorithmBase):  # noqa

    def __init__(self, logger=None):
        super(MovePlanner, self).__init__(logger=logger)
        self.goal_lock = threading.RLock()

    def goto(self,
             goal: BasePose,
             async_run: bool = False,
             start_pos: BasePose = None,
             plan_alg: str = "AStar",
             **kwargs
             ) -> ActionStatus:
        raise NotImplementedError()

    def goto_absolute(self,
                      target: BasePose,
                      async_run: bool = False,
                      **kwargs) -> ActionStatus:
        raise NotImplementedError()

    def cancel(self, *args, **kwargs):
        raise NotImplementedError()

    def track_trajectory(self, plan: PoseSeq, **kwargs):
        raise NotImplementedError()
