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
from robosdk.common.logger import logging


__all__ = ("AlgorithmBase",)


class AlgorithmBase(metaclass=abc.ABCMeta):
    def __init__(self, logger=None,):
        self.logger = logger
        if not self.logger:
            self.logger = logging.bind(system=True)

    def set_logger(self, logger):
        self.logger = logger
