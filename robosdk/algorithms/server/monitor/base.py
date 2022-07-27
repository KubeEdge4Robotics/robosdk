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

from typing import (
    List,
    Dict,
    Any
)

from robosdk.common.schema.stream import ImageStream
from robosdk.common.constant import ServiceState
from robosdk.algorithms.base import AlgorithmBase


__all__ = ("MonitorServer", )


class MonitorServer(AlgorithmBase):  # noqa
    def __init__(self, logger=None,):
        super(MonitorServer, self).__init__(logger=logger)
        self.should_exit = False
        self.streams: Dict[str, ImageStream] = {}
        self.state: Dict[str, ServiceState] = {}

    def streaming(self, stream: str, frame: Any, **parameters):
        raise NotImplementedError()

    def add(self, stream: str, **kwargs):
        raise NotImplementedError()

    def remove(self, stream: str, **kwargs):
        raise NotImplementedError()

    def start(self):
        raise NotImplementedError()

    def stop(self):
        self.should_exit = True
        all_stram = self.streams.keys()
        for stream in all_stram:
            self.logger.info(f'Stopping monitor for {stream}')
            self.remove(stream)

    def urls(self) -> List[str]:
        url = [mp.bind_uri for mp in self.streams.values()]
        return url
