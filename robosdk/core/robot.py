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

import asyncio
from importlib import import_module
from typing import Any
from typing import List

from robosdk.backend import BackendBase
from robosdk.cloud_robotics.skills import SkillBase
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.config import BaseConfig
from robosdk.common.config import Config
from robosdk.common.constant import RoboControlMode
from robosdk.common.exceptions import SensorError
from robosdk.sensors.base import SensorManage
from robosdk.utils.util import MethodSuppress
from robosdk.utils.util import cancel_on_exception

from .base import RoboBase

__all__ = ("Robot", )


class Robot(RoboBase):
    """
     This class builds robot specific objects by reading
     a configuration and instantiating the necessary robot
     module objects.
    """

    def __init__(self, name: str,
                 config: str = None,
                 only_sensors: List = None,
                 ignore_sensors: List = None,
                 use_control: bool = True
                 ):
        """
        :param name: robot name
        :param config: robot config
        :param only_sensors: only use sensors in this list
        :param ignore_sensors: ignore sensors in this list
        :param use_control: if use control
        """

        super(Robot, self).__init__(name=name, config=config, kind="robots")
        self.robot_name = name
        self.skill = None
        self.all_sensors = {}
        self.ignore_sensors = ignore_sensors if ignore_sensors else []
        self.only_sensors = only_sensors if only_sensors else []
        self.has_connect: bool = False
        if BaseConfig.BACKEND is None:
            if hasattr(self.config, "environment"):
                self.backend: BackendBase = ClassFactory.get_cls(
                    ClassType.BACKEND,
                    self.config.environment.backend
                )()
            else:
                self.backend = None
            BaseConfig.BACKEND = self.backend
        else:
            self.backend = BaseConfig.BACKEND
        self._mode: RoboControlMode = RoboControlMode.Lock
        self.use_control = (use_control and "control" in self.config)

    @property
    def control_mode(self):
        """
        :return: control mode
        """
        return self._mode

    @control_mode.setter
    def control_mode(self, mode: RoboControlMode):
        # todo: when control_mode change to lock, only manual is allowed
        if mode != self._mode:
            pass
        self._mode = mode

    def connect(self):
        """
        connect robot
        """
        if self.backend:
            self.backend.connect(name=self.robot_name)
        loop = asyncio.get_event_loop()
        tasks = asyncio.gather(
            self.initial_sensors(),
            self.initial_control(),
            self.initial_skill(),
        )
        cancel_on_exception(tasks)
        try:
            loop.run_until_complete(tasks)
        except asyncio.CancelledError:
            pass
        self.has_connect = True
        self._mode = RoboControlMode.Auto

    def close(self):
        if self.backend:
            self.backend.close()
        map(lambda s: s.clear(), self.all_sensors.values())

    def add_sensor(self, sensor: str, name: str, config: Config):

        try:
            _ = import_module(f"robosdk.sensors.{sensor.lower()}")
            cls = getattr(ClassType, sensor.upper())
        except (ModuleNotFoundError, AttributeError):
            cls = ClassType.GENERAL
        if sensor not in self.all_sensors:
            self.all_sensors[sensor] = SensorManage()

        # noinspection PyBrodException
        try:
            driver_cls = ClassFactory.get_cls(cls, config['driver']['name'])
            driver = driver_cls(name=name, config=config)
        except:  # noqa
            raise SensorError(f"Initial sensor driver {name} failure")
        self.all_sensors[sensor].add(name=name, sensor=driver)
        if len(self.all_sensors[sensor]) == 1:
            setattr(self, sensor.lower(), driver)

    def add_sensor_cls(self, sensor: str):
        try:
            _ = import_module(f"robosdk.sensors.{sensor.lower()}")
        except (ModuleNotFoundError, AttributeError):
            self.logger.error(f"Non-existent sensor driver: "
                              f"`robosdk.sensors.{sensor.lower()}`")
        if sensor not in self.all_sensors:
            self.all_sensors[sensor] = SensorManage()
        for inx, cfg in enumerate(self.config.sensors[sensor]):
            _cfg = self._init_cfg(config=cfg['config'], kind=sensor)
            sensor_cfg = Config(_cfg)
            sensor_cfg.update_obj(cfg)
            name = sensor_cfg["name"] or f"{sensor}{inx}"
            # noinspection PyBrodException
            try:
                driver_cls = ClassFactory.get_cls(
                    ClassType.SENSOR, sensor_cfg['driver']['name'])
                driver = driver_cls(name=name, config=sensor_cfg)
                driver.connect()
            except Exception as err:  # noqa
                self.logger.error(
                    f"Initial sensor driver {name} failure : {err}")
            else:
                if inx == 0:
                    setattr(self, sensor.lower(), driver)
                self.all_sensors[sensor].add(name=name, sensor=driver)
        if len(self.all_sensors[sensor]) > 1:
            self.logger.warning(
                f"Multiple {sensor}s defined in Robot {self.robot_name}.\n"
                f"In this case, {self.all_sensors[sensor].default_sensor} "
                f"is set as default. Switch the sensors excepted to use by "
                f"calling the `switch_sensor` method.")
        self.logger.info(f"Sensor {sensor} added")

    async def initial_sensors(self):
        for sensor in self.config.sensors:
            if ((self.ignore_sensors and sensor in self.ignore_sensors) or
                    (self.only_sensors and sensor not in self.only_sensors)):
                self.logger.info(f"skip sensor {sensor} ...")
                continue
            self.add_sensor_cls(sensor)

    def switch_sensor(self, sensor: str, name: str):
        driver = self.all_sensors[sensor][name]
        if driver is None:
            self.logger.error(f"Switch {sensor} fails because the "
                              f"device {name} cannot be located.")
            return False
        setattr(self, sensor.lower(), driver)
        self.all_sensors[sensor].default_sensor = name
        self.logger.info(f"Switch {sensor} to {name} as default.")
        return True

    async def initial_control(self):
        if not self.use_control:
            return
        for ctl_dict in self.config['control']:
            ctl = list(ctl_dict.keys())[0]
            cfg = ctl_dict[ctl]
            _cfg = self._init_cfg(config=cfg['config'], kind="control")
            control = Config(_cfg)
            try:
                _ = import_module(f"robosdk.control.{ctl.lower()}")
                driver_cls = ClassFactory.get_cls(ClassType.CONTROL,
                                                  control['driver']['name'])
                driver = driver_cls(name=ctl, config=control)
            except Exception as e:
                self.logger.error(f"Initial control driver {ctl} failure, {e}")
                setattr(self, ctl.lower(),
                        MethodSuppress(logger=self.logger, method=ctl.lower()))
            else:
                driver.connect()
                setattr(self, ctl.lower(), driver)

    async def initial_skill(self):
        # todo: allow load/unload skills for robot from CloudRobotics
        skills = ClassFactory.list(ClassType.ROBOTICS_SKILL)
        self.skill = MethodSuppress(logger=self.logger, method="skill")
        for skill in skills:
            driver_cls: SkillBase = ClassFactory.get_cls(
                ClassType.ROBOTICS_SKILL, skill)
            action = driver_cls(robot=self)
            setattr(self.skill, skill, action)

    def skill_register(self, name: str, driver_cls: Any):
        if not issubclass(driver_cls, SkillBase):
            self.logger.error(f"skill {name} should inherit `SkillBase`")
            return
        ClassFactory.register_cls(
            ClassType.ROBOTICS_SKILL, name, driver_cls
        )
        action = driver_cls(robot=self)
        setattr(self.skill, name, action)
        self.logger.info(f"register skill {name} to {self.robot_name}")
