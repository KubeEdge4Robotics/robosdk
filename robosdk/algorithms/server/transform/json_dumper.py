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

import json
import re
import sys
import zipfile
from typing import Dict

from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType

from .base import MessageDumper


@ClassFactory.register(ClassType.CLOUD_ROBOTICS_ALG, alias="json_dumper")
class JsonDumper(MessageDumper):  # noqa

    def __init__(self, file_out: str, logger=None, archive: bool = True):
        _subfix = ".json.zip" if archive else ".json"
        if not file_out.lower().endswith(_subfix):
            file_out = f"{file_out}{_subfix}"
        super(JsonDumper, self).__init__(file_out=file_out, logger=logger)
        self._json_handle = None
        self._zip_handle = None
        self._archive = archive
        self._size = 0

    def open(self,
             mode='w',
             compression=zipfile.ZIP_STORED,
             allowZip64=True,
             compresslevel=None
             ):

        if self._file_handle is not None:
            self.close()

        if self._archive:
            self._zip_handle = zipfile.ZipFile(
                self.file_out, "x",
                compression=compression,
                allowZip64=allowZip64,
                compresslevel=compresslevel
            )
            self._json_handle = self._zip_handle.open(
                re.sub("\.zip$", "", self.file_out), mode=mode)    # noqa
        else:
            self._json_handle = open(self.file_out, mode=mode)
        self._size = 0
        return self._json_handle

    def write(self, name: str, data: Dict, indent: int = 2):
        if not self._json_handle:
            _ = self.open()
        self._size += sys.getsizeof(data)
        json.dump(data, self._json_handle, indent=indent)

    def close(self):
        if self._json_handle is None:
            return
        self._json_handle.close()
        self._json_handle = None
        if self._zip_handle is not None:
            self._zip_handle.close()

    @property
    def size(self):
        return self._size

    def __del__(self):
        self.close()
