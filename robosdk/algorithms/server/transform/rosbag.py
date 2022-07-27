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

from typing import Any

from robosdk.utils.lazy_imports import LazyImport
from robosdk.utils.util import parse_kwargs
from robosdk.common.constant import Compression
from robosdk.common.class_factory import ClassType
from robosdk.common.class_factory import ClassFactory

from .base import MessageDumper


@ClassFactory.register(ClassType.CLOUD_ROBOTICS, alias="rosbag_dumper")
class RosBagDumper(MessageDumper):  # noqa

    def __init__(self, file_out: str, logger=None):
        if not file_out.lower().endswith(".bag"):
            file_out = f"{file_out}.bag"
        super(RosBagDumper, self).__init__(file_out=file_out, logger=logger)
        self._file_handle = None
        self.writer = LazyImport("rosbag")

    def open(self,
             mode='w',
             compression=Compression.NONE.value,
             chunk_threshold=768 * 1024,
             allow_unindexed=False,
             options=None,
             skip_index=False
             ):

        if self._file_handle is not None:
            self.close()

        self._file_handle = self.writer.Bag(
            self.file_out, mode=mode, compression=compression,
            chunk_threshold=chunk_threshold,
            allow_unindexed=allow_unindexed,
            options=options,
            skip_index=skip_index
        )
        return self._file_handle

    def write(self, name: str, data: Any, **kwargs):
        if not self._file_handle:
            _ = self.open()
        kvars = parse_kwargs(self._file_handle.write, **kwargs)
        kvars["topic"] = name
        kvars["msg"] = data
        self._file_handle.write(**kvars)

    def close(self):
        if self._file_handle is None:
            return
        self._file_handle.close()
        self._file_handle = None

    @property
    def size(self):
        return self._file_handle.size if self._file_handle else 0

    def __del__(self):
        self.close()
