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
import time
from typing import Any
from typing import Tuple


class BackendBase(abc.ABC):

    def __init__(self):
        self.msg_subscriber = None
        self.has_connect: bool = False

    @abc.abstractmethod
    def connect(self, name: str, **kwargs):
        ...

    @abc.abstractmethod
    def close(self):
        ...

    @property
    def now(self):
        return time.time()

    @abc.abstractmethod
    def get_time(self) -> float:
        ...

    @abc.abstractmethod
    def publish(self, *args, **kwargs):
        ...

    @abc.abstractmethod
    def subscribe(self, *args, **kwargs) -> Tuple[Any, int]:
        ...

    @abc.abstractmethod
    def unsubscribe(self, *args, **kwargs):
        ...

    @abc.abstractmethod
    def data_transform(self, msg, fmt):
        ...

    @abc.abstractmethod
    def get_message_list(self):
        ...
