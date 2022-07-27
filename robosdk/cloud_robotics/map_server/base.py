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

from robosdk.common.fileops import FileOps

__all__ = ("BaseMap", )


class BaseMap(metaclass=abc.ABCMeta):
    """
    Map base class
    """

    def __init__(self, *args, **kwargs):
        self.info = None
        self.maps = None
        self.obstacles = None
        self._map_file = ""

    def load(self, map_file: str, **kwargs):
        self._map_file = FileOps.download(map_file, untar=True)

    @property
    def map_file(self):
        return self._map_file

    @map_file.setter
    def map_file(self, map_file):
        self._map_file = map_file

    @abc.abstractmethod
    def start(self, *args, **kwargs):
        ...

    @abc.abstractmethod
    def stop(self, *args, **kwargs):
        ...

    @abc.abstractmethod
    def parse_panoptic(self, **kwargs):
        ...

    @abc.abstractmethod
    def add_obstacle(self, **kwargs):
        ...
