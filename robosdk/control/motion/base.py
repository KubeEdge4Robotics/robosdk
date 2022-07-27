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

from robosdk.common.config import Config
from robosdk.common.constant import Motion
from robosdk.control.base import ControlBase


__all__ = ("MotionControl", )


class MotionControl(ControlBase):  # noqa

    def __init__(self, name: str = "motion", config: Config = None):
        super(MotionControl, self).__init__(name=name, config=config)

    def set_vel(self, linear: float = 0., rotational: float = 0.):
        raise NotImplementedError

    def turn_left(self):
        self.set_vel(
            rotational=Motion.StepVel.value,
        )

    def turn_right(self):
        v = - Motion.StepVel.value
        self.set_vel(
            rotational=v,
        )

    def go_forward(self):
        self.set_vel(
            linear=Motion.StepVel.value,
        )

    def go_backward(self):
        v = - Motion.StepVel.value
        self.set_vel(
            linear=v,
        )

    def stop(self):
        for _ in range(Motion.ForceTimes.value):
            self.set_vel()
