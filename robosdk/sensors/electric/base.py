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

from typing import (
    Tuple,
    Optional,
    Any,
    Dict
)

from robosdk.sensors.base import SensorBase
from robosdk.common.config import Config


__all__ = ("ElectricBase", )


class ElectricBase(SensorBase):  # noqa
    """
    This is a parent class on which the robot
    specific Electric classes would be built.
    """

    def __init__(self, name, config: Config = None):
        super(ElectricBase, self).__init__(name=name, config=config)
        self.electric_info = None
        self.electric_battery = None
        self.sensor_kind = "electric"

    def get_data(self) -> Tuple[Dict, Any]:
        """
        This function returns the real-time battery data of robot.
        """
        raise NotImplementedError

    def get_intrinsics(self) -> Optional[Dict]:
        """
        This function returns the battery intrinsics.
        """
        raise NotImplementedError
