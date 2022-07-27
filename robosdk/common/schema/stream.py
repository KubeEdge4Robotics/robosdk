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
from typing import Union
from uuid import UUID
from uuid import uuid4

from pydantic import BaseModel
from pydantic import Field

__all__ = ("ImageStream", "StreamClient", "StreamMgsCls", )


class ImageStream(BaseModel):
    fps: int = 30
    width: int = 620
    height: int = 480
    bind_uri: str = None
    process: Any = None


class StreamClient(BaseModel):
    id: Union[int, str, UUID] = Field(default_factory=uuid4)
    name: str
    client: Any = None

    def __str__(self):
        return self.name or self.id


class StreamMgsCls(BaseModel):
    name: str
    msg_type: Any = None
