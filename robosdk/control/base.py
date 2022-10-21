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

from robosdk.common.config import BaseConfig
from robosdk.common.config import Config
from robosdk.common.logger import logging

__all__ = ("ControlBase", )


class ControlBase(metaclass=abc.ABCMeta):
    """
    This class defines an interface for control
    """

    def __init__(self, name: str, config: Config):
        self.backend = BaseConfig.BACKEND
        self.control_instance = name
        self.config = config
        self._info = {}
        self.has_connect = False
        self.interaction_mode = self.config.get("driver", {}).get("type", "UK")
        self.logger = logging.bind(instance=self.control_instance, sensor=True)

    def connect(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def reset(self):
        raise NotImplementedError
