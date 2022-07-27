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
from typing import (
    Any,
    List,
    Dict,
    Callable
)

from numpy import ndarray

from robosdk.utils.lazy_imports import LazyImport
from robosdk.common.schema.stream import StreamMgsCls
from robosdk.common.class_factory import ClassType
from robosdk.common.class_factory import ClassFactory

from .base import BackendBase


@ClassFactory.register(ClassType.BACKEND, alias="ros1")
class Ros1Backend(BackendBase):  # noqa

    ros_time_types = ['time', 'duration']
    ros_system_topic = ["/rosout", "/rosout_agg"]
    ros_primitive_types = ['bool', 'byte', 'char', 'int8', 'uint8', 'int16',
                           'uint16', 'int32', 'uint32', 'int64', 'uint64',
                           'float32', 'float64', 'string']
    ros_header_types = ['Header', 'std_msgs/Header', 'roslib/Header']

    def __init__(self):
        super(Ros1Backend, self).__init__()
        self._sub = {}
        self._pub = {}
        self.client = LazyImport("rospy")

        self.msg_handle = LazyImport("rostopic")
        self.msg_lib = LazyImport("roslib.message")
        self.msg_subscriber = LazyImport("message_filters")
        self.msg_sensor_generator = LazyImport("sensor_msgs.msg")
        self.msg_geometry_generator = LazyImport("geometry_msgs.msg")

    def connect(self, name: str,
                anonymous: bool = True,
                disable_signals: bool = True):
        self.client.init_node(
            name,
            anonymous=anonymous,
            disable_signals=disable_signals
        )
        self.has_connect = True

    def close(self):

        # noinspection PyBrodException
        try:
            self.client.signal_shutdown("close")
        except:  # noqa
            pass

    @property
    def now(self):
        return self.client.get_rostime()

    def get_time(self):
        return self.now.secs

    def get_message_class(self, msg_type):
        return self.msg_lib.get_message_class(msg_type)

    def get_message_type(self, msg_topic):
        msg_type, _, _ = self.msg_handle.get_topic_type(msg_topic)
        return msg_type

    def _subscribe(self, name: str,
                   callback: Callable = None,
                   callback_args: Any = None,
                   **kwargs):
        if callable(kwargs.get("data_class", "")):
            data_class = kwargs["data_class"]
            if isinstance(data_class, str):
                data_class = self.get_message_class(data_class)
        else:
            try:
                msg_type = self.get_message_type(name)
                data_class = self.get_message_class(msg_type)
            except:  # noqa
                data_class = self.client.msg.AnyMsg
        kwargs["data_class"] = data_class
        sub = self.msg_subscriber.Subscriber(
            name,
            callback=callback,
            callback_args=callback_args,
            **kwargs
        )
        return sub

    def subscribe(self, name: str, **kwargs):
        if not kwargs:
            kwargs = {}

        key_id = hash(str(kwargs))
        key_name = (name, key_id)
        if name not in self._sub:
            self._sub[key_name] = self._subscribe(
                name, **kwargs
            )

        return self._sub[key_name], key_id

    def publish(self, name: str,
                data: Any,
                data_class: Callable,
                queue_size: int = 1, **kwargs):
        if not kwargs:
            kwargs = {}
        key_id = hash(str(kwargs))
        key_name = (name, key_id)
        if name not in self._pub:
            self._pub[key_name] = self.client.Publisher(
                name,
                data_class,
                queue_size=queue_size, **kwargs)
        self._pub[key_name].publish(data)

    def unsubscribe(self, *topics, filter_ids: List = None):
        for (topic, t_id), sub in self._sub.items():
            if not hasattr(sub, "sub"):
                continue
            if topic not in topics:
                continue
            if filter_ids and t_id not in filter_ids:
                continue
            sub.sub.unregister()
            del self._sub[(topic, t_id)]

    def get_message_list(self) -> List[StreamMgsCls]:
        pubs, _ = self.msg_handle.get_topic_list()

        all_data = []
        for msg, msg_type, publisher in pubs:
            if msg in self.ros_system_topic:
                continue
            data = StreamMgsCls(
                name=msg,
                msg_type=self.get_message_class(msg_type)
            )
            all_data.append(data)
        return all_data

    @staticmethod
    def _get_message_fields(message):
        return zip(message.__slots__, message._slot_types)  # noqa

    @staticmethod
    def _convert_from_ros_binary(field_value):
        field_value = base64.b64encode(field_value).decode('utf-8')
        return field_value

    @staticmethod
    def _convert_from_ros_time(field_value):
        field_value = {
            'secs': field_value.secs,
            'nsecs': field_value.nsecs
        }
        return field_value

    @classmethod
    def _convert_from_ros_array(cls, field_type, field_value,
                                binary_array_as_bytes=True):
        # use index to raise ValueError if '[' not present
        list_type = field_type[:field_type.index('[')]
        return [cls._convert_from_ros_type(
            list_type, value, binary_array_as_bytes) for value in field_value]

    @staticmethod
    def _is_ros_binary_type(field_type):
        """ Checks if the field is a binary array one, fixed size or not"""
        return field_type.startswith('uint8[') or field_type.startswith(
            'char[')

    @staticmethod
    def _is_field_type_an_array(field_type):
        return field_type.find('[') >= 0

    @classmethod
    def _is_field_type_a_primitive_array(cls, field_type):
        bracket_index = field_type.find('[')
        if bracket_index < 0:
            return False
        else:
            list_type = field_type[:bracket_index]
            return list_type in cls.ros_primitive_types

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
            field_value = list(field_value)
        elif cls._is_field_type_an_array(field_type):
            field_value = cls._convert_from_ros_array(
                field_type, field_value, binary_array_as_bytes)
        else:
            field_value = cls._convert_ros_message_to_dictionary(
                field_value, binary_array_as_bytes)
        return field_value

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

    @staticmethod
    def _convert_ros_message_to_nparray(message) -> ndarray:
        ros_numpy = LazyImport("ros_numpy")

        return ros_numpy.numpify(message)

    @classmethod
    def data_transform(cls, msg, fmt: str = "raw"):
        if fmt == "json":
            return cls._convert_ros_message_to_dictionary(msg)
        elif fmt == "numpy":
            return cls._convert_ros_message_to_nparray(msg)
        # todo: more formats to be supported
        return msg