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

from threading import Thread
from typing import List

from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.schema.stream import StreamMgsCls
from robosdk.utils.lazy_imports import LazyImport

from .base import BackendBase


@ClassFactory.register(ClassType.BACKEND, alias="ros2")
class Ros2Backend(BackendBase):  # noqa

    def __init__(self):

        self.client = LazyImport("rclpy")
        self.msg_listen = LazyImport("ros2topic")
        self.msg_lib = LazyImport("rosidl_runtime_py.utilities")

        self._sub = {}
        self._ctx = self.client.Context()
        self._exec = None
        self._node = None
        super(Ros2Backend, self).__init__()

    def connect(self, name: str,
                anonymous: bool = True,
                disable_signals: bool = True):
        if self.has_connect:
            return
        # noinspection PyBrodException
        try:
            self.client.init(context=self._ctx)
        except Exception:  # noqa
            pass

        self._node = self.client.create_node(name, context=self._ctx)
        self._exec = self.client.executor.MultiThreadExecutor(
            context=self._ctx
        )
        self._exec.add_node(self._node)
        self.has_connect = True
        spinner = Thread(target=self._spin)
        spinner.daemon = True
        spinner.start()

    def _spin(self):
        while self._ctx and self._ctx.ok():
            self._exec.spin_once(timeout_sec=1)

    def close(self):

        # noinspection PyBrodException
        try:
            self._exec.shutdown()
            self._ctx.shutdown()
        except:  # noqa
            pass

    def get_message_class(self, msg_type):
        return self.msg_lib.get_message(msg_type)

    def get_message_type(self, msg_topic):
        msg_type, _, _ = self.msg_listen.get_topic_type(msg_topic)
        return msg_type

    def get_time(self) -> float:
        return self._node.get_clock().now().tomsg().sec

    def get(self, topic, **kwargs):
        # todo: get a single msg
        pass

    def subscribe(self, name: str, **kwargs):
        # todo: subscribe a topic
        pass

    def unsubscribe(self, *topics, filter_ids: List = None):
        # todo: unsubscribe the topics
        pass

    def publish(self, *args, **kwargs):
        # todo: publish a topic
        pass

    def get_message_list(self) -> List[StreamMgsCls]:
        # todo: get all topics
        pass

    @classmethod
    def data_transform(cls, msg, fmt: str = "raw"):
        # todo: more formats to be supported
        return msg
