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
import tempfile
from contextlib import ContextDecorator
from pathlib import Path
from typing import Any
from typing import AnyStr

__all__ = ("FileCache",)


class FileCache(ContextDecorator):
    """
    wrapper of file, which provides a convenient way to cache data.
    """

    def __init__(self, delete: bool = True):
        self.data = {}
        self._delete = delete

    def __enter__(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            self._cache_path = f.name
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __repr__(self):
        return self._cache_path

    def close(self):
        if self._delete:
            Path(self._cache_path).unlink(missing_ok=True)

    def load(self):
        with open(self._cache_path, "r", encoding="utf-8") as fin:
            return json.load(fin)

    def save(self):
        with open(self._cache_path, "w", encoding="utf-8") as fout:
            json.dump(self.data, fout)
        return self

    def update(self, key: AnyStr, value: Any = ""):
        self.data[key] = value
        return self.data

    def __getitem__(self, item):
        return self.data.get(item, None)

    __str__ = __repr__


def test_file_cache():
    with FileCache() as cache:
        cache.update("a")
        cache.update("b", 1)
        cache.update("c", {"a": 0})
        cache.update("d", "test")
        cache.save()
        data = cache.load()
    assert data == {"a": "", "b": 1, "c": {"a": 0}, "d": "test"}
