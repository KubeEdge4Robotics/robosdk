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

import abc
import copy
import threading
from typing import Dict

from robosdk.common.logger import logging
from robosdk.common.config import Config
from robosdk.common.config import BaseConfig


__all__ = ("SensorBase", "RosSensorBase", "SensorManage")


class SensorBase(metaclass=abc.ABCMeta):
    """
    This class defines an interface for sensors, it defines
    the basic functionality required by sensors being used in
    an environment.
    """

    def __init__(self, name: str, config: Config):
        self.backend = BaseConfig.BACKEND
        self.sensor_name = name
        self.config = config
        self._info = {}
        self.has_connect = False
        self.interaction_mode = self.config.get("driver", {}).get("type", "UK")
        self.logger = logging.bind(instance=self.sensor_name, sensor=True)

    @property
    def sys_time(self) -> float:
        return self.backend.get_time()

    @property
    def info(self):
        """
        Property used to store sensor readings
        """
        return self._info

    @info.setter
    def info(self, value):
        self._info = value

    @info.deleter
    def info(self):
        self._info = {}

    def connect(self):
        """Connect with sensor"""
        raise NotImplementedError()

    def close(self):
        """stop subscribe the sensor data"""
        raise NotImplementedError()

    def reset(self):
        """Reset the sensor data"""
        raise NotImplementedError()


class RosSensorBase(SensorBase):  # noqa
    def __init__(self, name, config: Config = None):
        super(RosSensorBase, self).__init__(name=name, config=config)
        data_topic = self.config.data.target
        self.topic_lock = threading.RLock()
        self.data_sub, _ = self.backend.subscribe(data_topic)
        self._data: Dict = {}
        self._raw = None

    def connect(self):
        if self.has_connect:
            self.logger.warning(
                f"sensor {self.sensor_name} has already connected")
            return
        self.has_connect = True
        self._info[self.sensor_name] = {
            "count": 0, "error": 0, "target": self.config.data.target,
            "connect": self.sys_time, "close": 0
        }
        self.data_sub.registerCallback(self._callback)

    def close(self):
        self.has_connect = False
        self.backend.unsubscribe(self.data_sub)
        self._info[self.sensor_name]["close"] = self.sys_time

    @property
    def data(self) -> Dict:
        if self._raw is not None:
            try:
                self._data: Dict = self.backend.data_transform(
                    self._raw, fmt="json"
                )
            except Exception as e:  # noqa
                self.logger.error(f"get data from battery "
                                  f"[{self.sensor_name}] fail: {str(e)}")
        else:
            self._data = {}
        return self._data

    def get_data(self):
        self.topic_lock.acquire()
        ts = self.sys_time
        data = copy.deepcopy(self.data)
        self.topic_lock.release()
        return data, ts

    def _callback(self, data):
        self._info[self.sensor_name]["count"] += 1
        if data is not None:
            self._raw = data
        else:
            self._info[self.sensor_name]["error"] += 1


class SensorManage:

    def __init__(self):
        self.default_sensor = ""
        self._all_sensors = {}

    def add(self, name: str, sensor: SensorBase = None):
        if not len(self._all_sensors):
            self.default_sensor = name

        self._all_sensors[name] = sensor

    def remove(self, name: str):
        if name in self._all_sensors:
            del self._all_sensors[name]
        if self.default_sensor == name:
            self.default_sensor = (list(self._all_sensors.keys())[0]
                                   if len(self) else None)

    def clear(self):
        for sensor in self._all_sensors:
            # noinspection PyBrodException
            try:
                self._all_sensors[sensor].close()
            except:  # noqa
                pass

    def __len__(self) -> int:
        return len(self._all_sensors)

    def __getitem__(self, item: str) -> SensorBase:
        return self._all_sensors.get(item, None)
