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

import queue
import warnings
from typing import Any

from robosdk.common.constant import InternalConst
from robosdk.common.exceptions import RoboError


class BaseQueue:

    DATA_TIMEOUT: int = InternalConst.DATA_DUMP_TIMEOUT.value

    def __init__(self,
                 queue_maxsize: int = InternalConst.DATA_QUEUE_MAX.value,
                 keep_when_full: bool = False):
        self.mq = queue.Queue(maxsize=queue_maxsize)
        self._full = keep_when_full

    def __len__(self):
        return len(self.mq.queue)

    def get(self):

        try:
            data = self.mq.get_nowait()
        except queue.Empty:
            data = None
        return data

    def put(self, data: Any):
        if self.mq.full():
            if self._full:
                _ = self.get()
            warnings.warn('mq full, drop the message')
            return
        try:
            self.mq.put_nowait(data)
        except Exception as e:  # noqa
            raise RoboError(f'mq add message fail: {e}')
