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

import sys
import types

__all__ = ("LazyImport",)


class LazyImport(types.ModuleType):
    """
    LazyImport is a wrapper of module, which provides a convenient way to import
    modules lazily.
    """

    def __getattribute__(self, item):
        """
        :param item: attribute name
        :return: attribute value
        """

        name = object.__getattribute__(self, '__name__')

        try:
            __import__(name)
        except ModuleNotFoundError:
            return

        module = sys.modules[name]

        class LoadedLazyImport(types.ModuleType):
            __get_attribute__ = module.__getattribute__
            __repr__ = module.__repr__

        # object.__setattr__(self, "__class__", LoadedLazyImport)

        return module.__getattribute__(item)

    def __repr__(self):
        return object.__getattribute__(self, '__name__')
