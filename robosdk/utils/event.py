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
"""Event dispatcher for modules"""

import asyncio


class EventBus:

    def __init__(self, logger):
        self._logger = logger

        self._ready = asyncio.Event()
        self._error = asyncio.Event()
        self._close = asyncio.Event()

        self.__error = None

    @property
    def error(self):
        return self.__error

    def register(self):
        pass

    def unregister(self):
        pass

    def destroy(self):
        pass
