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
import os

from robosdk.backend.base import BackendBase
from robosdk.common.config import BaseConfig
from robosdk.common.config import Config
from robosdk.common.fileops import FileOps
from robosdk.common.logger import logging

__all__ = ("AlgorithmBase",)


class AlgorithmBase(metaclass=abc.ABCMeta):
    def __init__(self, logger=None):
        self.alg_config = None
        self.set_config_url(self.get_alg_cfg_url(self._alg_cls_name))
        self.logger = logger
        self.alg_name = getattr(self.alg_config, "name", self._alg_cls_name)
        if not self.logger:
            self.logger = logging.bind(instance=self.alg_name, system=True)
        self.backend: BackendBase = BaseConfig.BACKEND

    def set_logger(self, logger):
        self.logger = logger

    def set_config_url(self, config: str):
        if config.endswith((".yaml", ".yml")):
            _config = FileOps.download(
                config, self.get_alg_cfg_url(self._alg_cls_name)
            )
        else:
            _config = self.get_alg_cfg_url(config)
        self.alg_config = Config(_config) if os.path.isfile(_config) else None

    @property
    def _alg_cls_name(self):
        return str(self.__class__.__name__).lower()

    @staticmethod
    def get_alg_cfg_url(name: str):
        return os.path.join(
            BaseConfig.CONFIG_PATH, "algorithms", f"{name}.yaml"
        )
