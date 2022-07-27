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
from robosdk.common.schema.pose import BasePose
from robosdk.sensors.base import SensorBase

__all__ = ("OdometryBase", )


class OdometryBase(SensorBase):  # noqa

    def __init__(self, name, config: Config = None):
        super(OdometryBase, self).__init__(name=name, config=config)
        self.sensor_kind = "odom"

    def get_curr_state(self, **kwargs) -> BasePose:
        raise NotImplementedError

    def set_curr_state(self, state: BasePose, **kwargs) -> BasePose:
        raise NotImplementedError
