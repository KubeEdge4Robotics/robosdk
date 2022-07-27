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

import abc

from robosdk.common.logger import logging

__all__ = ("SkillBase", )


class SkillBase(metaclass=abc.ABCMeta):
    """
    RoboSkill base class
    """

    def __init__(self, robot, name: str = ""):
        self.name = name
        self.robot = robot
        self.logger = logging.bind(
            instance=f"{robot.robot_name}.skill_{name}", system=True
        )

    def __call__(self, *args, **kwargs):
        return self.call(*args, **kwargs)

    @abc.abstractmethod
    def call(self, *args, **kwargs):
        ...
