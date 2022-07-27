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

import numpy as np
from robosdk.common.config import Config
from robosdk.sensors.base import SensorBase

__all__ = ("VoiceBase", )


class VoiceBase(SensorBase):  # noqa

    def __init__(self, name, config: Config = None):
        super(VoiceBase, self).__init__(name=name, config=config)
        self.sensor_kind = "voice"
        self.voice_info = {}
        self.data_lock = threading.RLock()

    def get_data(self) -> Tuple[np.ndarray, Any]:
        raise NotImplementedError

    def say(self, data: np.ndarray):
        raise NotImplementedError
