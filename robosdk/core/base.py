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

import os

from robosdk.common.config import BaseConfig
from robosdk.common.config import Config
from robosdk.common.fileops import FileOps
from robosdk.common.logger import logging

__all__ = ("RoboBase", )


class RoboBase:
    """
    Base class for robot and backend
    """

    def __init__(self,
                 name: str,
                 config: str = None,
                 kind: str = "robots"
                 ):
        self.logger = logging.bind(instance=name)
        config: str = self._init_cfg(config, kind=kind)
        self.config = Config(config) if config else {}
        self.ip = BaseConfig.MAC_IP

    @staticmethod
    def _init_cfg(config="base", kind="robots"):
        """
        :param config: config file
        :param kind: config kind
        :return: config file
        """
        _url = os.path.join(
            BaseConfig.CONFIG_PATH, kind, f"{config}.yaml"
        )
        if config.endswith((".yaml", ".yml")):
            config = FileOps.download(config, _url)
        else:
            config = _url
        return config if os.path.isfile(config) else {}

    def close(self):
        raise NotImplementedError

    def __del__(self):
        self.close()
