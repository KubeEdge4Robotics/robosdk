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
from typing import Any
from typing import Tuple

from robosdk.common.config import Config
from robosdk.common.schema.map import PgmMap
from robosdk.sensors.base import SensorBase

__all__ = ("MapBase", )


class MapBase(SensorBase):  # noqa
    """
    This is a parent class on which the robot
    specific Electric classes would be built.
    """

    def __init__(self, name, config: Config = None):
        super(MapBase, self).__init__(name=name, config=config)
        self.obstacles = []
        self.map_data = None
        self.map_info = None
        self.sensor_kind = "map"
        self.data_lock = threading.RLock()

    def get_data(self) -> Tuple[PgmMap, Any]:
        """
        This function returns the real-time map data of robot.
        """
        raise NotImplementedError

    def save(self, file_out, **kwargs):
        raise NotImplementedError
