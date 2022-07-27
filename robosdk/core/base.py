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

from robosdk.common.config import Config
from robosdk.common.config import BaseConfig
from robosdk.common.fileops import FileOps
from robosdk.common.logger import logging


__all__ = ("RoboBase", )


class RoboBase:

    def __init__(self,
                 name: str,
                 config: str = None,
                 kind: str = "robots"
                 ):
        self.logger = logging.bind(instance=name)
        config: str = self._init_cfg(config, kind=kind)
        self.config = Config(config) if config else None
        self.ip = BaseConfig.MAC_IP

    @staticmethod
    def _init_cfg(config, kind="robots"):
        if config and config.endswith((".yaml", ".yml")):
            config = FileOps.download(config)
        else:
            if not config:
                config = "base"
            config = os.path.join(
                BaseConfig.CONFIG_PATH, kind, f"{config}.yaml"
            )
        return config if os.path.isfile(config) else None
