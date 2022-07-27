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

from typing import Dict

import numpy as np
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.config import Config
from robosdk.sensors.base import RosSensorBase
from robosdk.utils.lazy_imports import LazyImport

from .base import VoiceBase

__all__ = ("RosVoiceDriver", )


@ClassFactory.register(ClassType.SENSOR, alias="ros_voice_driver")
class RosVoiceDriver(RosSensorBase, VoiceBase):  # noqa

    def __init__(self, name, config: Config = None):
        super(RosVoiceDriver, self).__init__(name=name, config=config)
        self._audio_cls = LazyImport("audio_common_msgs.msg")

        if hasattr(self.config, "info"):
            info_s_p = getattr(self.config.info, "subscribe", None) or {}
            self.backend.get(
                self.config.info.target,
                callback=self._voice_info_callback,
                **info_s_p
            )

    def _voice_info_callback(self, info):
        if info is not None:
            try:
                self.voice_info: Dict = self.backend.data_transform(
                    info, fmt="json"
                )
            except Exception as e:  # noqa
                self.logger.error(f"get data from [{self.config.info}]"
                                  f" fail: {str(e)}")
        else:
            self.voice_info = {}
        return self.voice_info

    @property
    def data(self) -> np.ndarray:
        return np.frombuffer(
            self._raw.data, dtype=np.int16)

    def close(self):
        super(RosVoiceDriver, self).close()

    def say(self, data: np.ndarray):
        data_buffer = data.tobytes()
        voice = self._audio_cls.AudioData(data=data_buffer)
        self.backend.publish(
            data=voice, data_class=self._audio_cls.AudioData,
            name=self.config.output.target
        )
