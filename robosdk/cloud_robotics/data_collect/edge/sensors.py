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

import os
import threading
from datetime import datetime, timedelta
from typing import (
    Callable,
    Dict,
    List,
    Optional,
    Union,
)

from robosdk.utils.queue import BaseQueue
from robosdk.backend import BackendBase
from robosdk.common.fileops import FileOps
from robosdk.common.config import BaseConfig
from robosdk.common.schema.stream import StreamMgsCls
from robosdk.common.class_factory import ClassType
from robosdk.common.class_factory import ClassFactory
from robosdk.cloud_robotics.edge_base import WSClient
from robosdk.cloud_robotics.edge_base import ClientBase
from robosdk.algorithms.server.transform import MessageDumper

__all__ = ("CollectRTClient", "CollectOffClient")


class _ThreadDataCollect(threading.Thread):

    def __init__(self,
                 push: Callable,
                 robot_backend: BackendBase = BaseConfig.BACKEND,
                 transform_fmt: str = "raw"
                 ):
        self.transform_fmt = transform_fmt
        super(_ThreadDataCollect, self).__init__()
        self._all_msg: List[StreamMgsCls] = []
        self._all_queue: Dict[str, BaseQueue] = {}
        self.robot_backend: BackendBase = (
                robot_backend or
                ClassFactory.get_cls(ClassType.BACKEND, "ros1")()
        )
        self.push = push

    def run(self):
        if self.robot_backend is None:
            return
        if not self.robot_backend.has_connect:
            self.robot_backend.connect(name="anonymous")
        while 1:
            self.get_all_data()

            for data in self._all_msg:
                queue = self._all_queue.get(data.name, None)

                if not isinstance(queue, BaseQueue):
                    continue
                msg = queue.get()
                if msg is None:
                    continue
                _data = self.robot_backend.data_transform(
                    msg, fmt=self.transform_fmt)
                self.push({"name": data.name, "data": _data})

    def get_all_data(self):
        self._all_msg: List = self.robot_backend.get_message_list()
        for msg in self._all_msg:
            if msg.name in self._all_queue:
                continue
            self._all_queue[msg.name] = BaseQueue(keep_when_full=False)
            sub = self.robot_backend.msg_subscriber.Subscriber(
                msg.name, msg.msg_type
            )
            sub.registerCallback(self._put_data, msg.name)

    def _put_data(self, data, name):
        self._all_queue[name].put(data)

    def close(self):
        self.join(timeout=20)


class CollectRTClient(WSClient):  # noqa
    """Real-time sensors data-collection"""

    def __init__(self, name: str = "dataCollect", **kwargs, ):
        super(CollectRTClient, self).__init__(
            name=name, **kwargs
        )
        _backend: BackendBase = (
                BaseConfig.BACKEND or
                ClassFactory.get_cls(ClassType.BACKEND, "ros1")()
        )
        self._worker = _ThreadDataCollect(
            push=self.push, robot_backend=_backend
        )

    def start(self):
        self.send({"command": "start"})
        self._worker.start()

    def stop(self):
        self.send({"command": "stop"})
        self._worker.close()

    def push(self, msg: Dict):
        msg["command"] = "update"
        self.send(msg)


class CollectOffClient(ClientBase):  # noqa
    """Offline sensors data-collection"""

    def __init__(self,
                 name: str = "dataCollect",
                 rotation: Optional[Union[int, timedelta, Callable]] = None,
                 use_backend: str = "json_dumper",
                 **kwargs, ):
        super(CollectOffClient, self).__init__(
            name=name, **kwargs
        )
        self._backend: BackendBase = (
                BaseConfig.BACKEND or
                ClassFactory.get_cls(ClassType.BACKEND, "ros1")()
        )
        self._worker = _ThreadDataCollect(
            push=self.send, robot_backend=self._backend
        )
        self._local_path = BaseConfig.TEMP_DIR
        self._remote_path = (BaseConfig.FILE_TRANS_REMOTE_URI
                             or self._local_path)
        self._file_index = 0
        self.use_backend = use_backend or "json_dumper"
        self.file_handle: MessageDumper = self._file_handle(
            file_out=self.local_file, use_backend=self.use_backend
        )
        self._pre_upload_time = datetime.now()
        self._curr_frame = None
        self._rotation = rotation

    def _file_handle(self, file_out: str, use_backend: str) -> MessageDumper:
        return ClassFactory.get_cls(
            ClassType.CLOUD_ROBOTICS, use_backend
        )(file_out=file_out, logger=self.logger)

    @property
    def local_file(self):
        return os.path.join(
            self._local_path, f"{self.name}.{self._file_index}"
        )

    def connect(self, **kwargs):
        self.file_handle.open()

    def start(self):
        self._worker.start()

    def stop(self):
        self.file_handle.close()
        self._push()
        self._worker.close()

    def _check_policy(self) -> bool:
        if self._rotation is None:
            return False
        if isinstance(self._rotation, int):
            return self.file_handle.size > self._rotation
        elif isinstance(self._rotation, timedelta):
            return (datetime.now() - self._pre_upload_time) > self._rotation
        elif callable(self._rotation):
            return self._rotation(self)
        return False

    def send(self, msg: Dict):
        self._curr_frame = msg
        if self._check_policy():
            self.logger.info("try to upload data base on policy")
            self.file_handle.close()
            self._push()
            self._file_index += 1
            self.file_handle = self._file_handle(
                file_out=self.local_file, use_backend=self.use_backend
            )

        name: str = msg.get("name", "")
        data = msg.get("data", None)
        self.file_handle.write(name, data)

    def _push(self):
        self._pre_upload_time = datetime.now()
        events = threading.Thread(
            target=FileOps.upload,
            kwargs={
                "src": self.file_handle.file_out,
                "dst": self._remote_path,
                "clean": True
            },
            daemon=True
        )
        events.start()

    def __del__(self):
        self.stop()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def __repr__(self):
        return getattr(self.file_handle, "file_out", self.local_file)

    __str__ = __repr__


if __name__ == '__main__':
    backend: BackendBase = ClassFactory.get_cls(
        ClassType.BACKEND, "ros1"
    )()
    BaseConfig.BACKEND = backend
    d = CollectOffClient(use_backend="rosbag_dumper")
    d.start()
