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
from typing import Any
from typing import Dict

from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.config import Config
from robosdk.sensors.base import RosSensorBase

from .base import ElectricBase

__all__ = ("RosBatteryDriver", )


@ClassFactory.register(ClassType.SENSOR, alias="ros_battery_driver")
class RosBatteryDriver(RosSensorBase, ElectricBase):  # noqa

    def __init__(self, name, config: Config = None):
        super(RosBatteryDriver, self).__init__(name=name, config=config)
        if hasattr(self.config, "info"):
            parameters = getattr(self.config.info, "subscribe", None) or {}
            self.backend.get(
                self.config.info.target,
                callback=self._battery_info_callback,
                **parameters
            )

    def _battery_info_callback(self, info: Any):
        if info is not None:
            try:
                self.electric_info: Dict = self.backend.data_transform(
                    info, fmt="json"
                )
            except Exception as e:  # noqa
                self.logger.error(f"get data from [{self.config.info}]"
                                  f" fail: {str(e)}")
        else:
            self.electric_info = {}
        return self.electric_info

    @property
    def battery(self) -> Dict:
        return self.data

    def close(self):
        super(RosBatteryDriver, self).close()
