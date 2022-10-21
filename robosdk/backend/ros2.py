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

import base64
from datetime import datetime
from threading import Thread
from typing import Dict
from typing import List

from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.schema.stream import StreamMgsCls
from robosdk.utils.lazy_imports import LazyImport

from .base import BackendBase


@ClassFactory.register(ClassType.BACKEND, alias="ros2")
class Ros2Backend(BackendBase):  # noqa
    """
    ROS2 backend.
    """
    ros_primitive_types = [
        "bool", "byte", "char", "float32", "float64", "int8", "uint8",
        "int16", "uint16", "int32", "uint32", "int64", "uint64", "string"
    ]
    ros_time_types = ["time", "duration"]

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
        """
        Connect to ROS2.
        """
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

    def now(self):
        """ convert datetime to ros time from timestamp """
        now = datetime.now().utcnow().timestamp()
        return self.client.Time(seconds=now).to_msg()

    def get_message_class(self, msg_type):
        return self.msg_lib.get_message(msg_type)

    def get_message_type(self, msg_topic):
        msg_type, _, _ = self.msg_listen.get_topic_type(msg_topic)
        return msg_type

    def get_time(self) -> float:
        return self._node.get_clock().now().tomsg().sec

    def get(self, topic, **kwargs):
        """
        Get a topic.
        """
        msg_type = self.get_message_type(topic)
        msg_cls = self.get_message_class(msg_type)
        return self._node.create_subscription(
            msg_cls, topic, self._sub[topic], **kwargs
        )

    def subscribe(self, name: str, **kwargs):
        """
        Subscribe a topic.
        """
        msg_type = self.get_message_type(name)
        msg_cls = self.get_message_class(msg_type)
        self._sub[name] = self.client.create_subscription(
            msg_cls, name, self._sub[name], **kwargs
        )

    def unsubscribe(self, *topics, filter_ids: List = None):
        """
        Unsubscribe a topic.
        """
        for topic in topics:
            if topic in self._sub:
                self._sub.pop(topic)

    def publish(self, *args, **kwargs):
        """Publish a ros2 topic."""
        self._node.create_publisher(*args, **kwargs)

    def get_message_list(self) -> List[StreamMgsCls]:
        """ get all topic lists """
        return self.msg_listen.get_topic_names_and_types()

    @classmethod
    def data_transform(cls, msg, fmt: str = "raw"):
        if fmt == "json":
            return cls._convert_ros_message_to_dictionary(msg)
        elif fmt == "numpy":
            return cls._convert_ros_message_to_nparray(msg)
        # todo: more formats should be supported
        return msg

    @classmethod
    def _convert_ros_message_to_dictionary(
            cls, message, binary_array_as_bytes=False) -> Dict:
        """
        Takes in a ROS message and returns a Python dictionary.
        """

        dictionary = {}
        message_fields = cls._get_message_fields(message)
        for field_name, field_type in message_fields:
            field_value = getattr(message, field_name)
            dictionary[field_name] = cls._convert_from_ros_type(
                field_type, field_value, binary_array_as_bytes)
        return dictionary

    @classmethod
    def _convert_ros_array_to_list(cls, msg):
        """
        Convert ROS array to list.
        """
        return list(msg.data)

    @classmethod
    def _convert_ros_message_to_nparray(cls, msg):
        """
        Convert ROS message to numpy array.
        """
        import numpy as np
        msg_dict = {}
        for field in msg.get_fields_and_field_types().keys():
            value = getattr(msg, field)
            if cls._is_ros_message(value):
                value = cls._convert_ros_message_to_nparray(value)
            msg_dict[field] = value
        return np.array(msg_dict)

    @classmethod
    def _is_ros_message(cls, msg):
        """
        Check if the message is a ROS message.
        """
        return hasattr(msg, "get_fields_and_field_types")

    @classmethod
    def _is_ros_array(cls, msg):
        """
        Check if the message is a ROS array.
        """
        return hasattr(msg, "data")

    @classmethod
    def _convert_from_ros_type(cls, field_type, field_value,
                               binary_array_as_bytes=True):
        if field_type in cls.ros_primitive_types:
            field_value = str(field_value)
        elif field_type in cls.ros_time_types:
            field_value = cls._convert_from_ros_time(field_value)
        elif cls._is_ros_binary_type(field_type):
            if binary_array_as_bytes:
                field_value = cls._convert_from_ros_binary(field_value)
            elif type(field_value) == str:
                field_value = [ord(v) for v in field_value]
            else:
                field_value = list(field_value)
        elif cls._is_field_type_a_primitive_array(field_type):
            field_value = cls._convert_from_ros_array(
                field_type, field_value, binary_array_as_bytes)
        else:
            field_value = cls._convert_ros_message_to_dictionary(
                field_value, binary_array_as_bytes)
        return field_value

    @classmethod
    def _convert_from_ros_time(cls, field_value):
        """
        Convert ROS time to string.
        """
        return str(field_value)

    @classmethod
    def _convert_from_ros_binary(cls, field_value):
        """
        Convert ROS binary to string.
        """
        field_value = base64.b64encode(field_value).decode('utf-8')
        return field_value

    @classmethod
    def _is_ros_binary_type(cls, field_type):
        """
        Check if the field type is a ROS binary type.
        """
        return field_type.startswith('uint8[') or field_type.startswith(
            'char[')

    @classmethod
    def _is_field_type_a_primitive_array(cls, field_type):
        """
        Check if the field type is a primitive array.
        """
        return field_type.startswith('[') and field_type.endswith(']')

    @classmethod
    def _convert_from_ros_array(cls, field_type, field_value,
                                binary_array_as_bytes):
        """
        Convert ROS array to list.
        """
        if field_type.startswith('['):
            field_type = field_type[1:]
        if field_type.endswith(']'):
            field_type = field_type[:-1]
        if cls._is_ros_binary_type(field_type):
            if binary_array_as_bytes:
                field_value = cls._convert_from_ros_binary(field_value)
            elif type(field_value) == str:
                field_value = [ord(v) for v in field_value]
            else:
                field_value = list(field_value)
        else:
            field_value = list(field_value)
        return field_value
