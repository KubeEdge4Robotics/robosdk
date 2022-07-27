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

"""This script contains some common tools."""
import asyncio
import os
import platform
import socket
import warnings
from copy import deepcopy
from functools import wraps
from inspect import getfullargspec
from typing import Callable

import numpy as np
import yaml
from robosdk.common.schema.pose import BasePose


def cancel_on_exception(task):
    def handler(loop, context):
        loop.default_exception_handler(context)
        if not task.cancelled():
            task.cancel()

    asyncio.get_event_loop().set_exception_handler(handler)


def singleton(cls):
    """Set class to singleton class.

    :param cls: class
    :return: instance
    """
    __instances__ = {}

    @wraps(cls)
    def get_instance(*args, **kw):
        """Get class instance and save it into glob list."""
        if cls not in __instances__:
            __instances__[cls] = cls(*args, **kw)

        return __instances__[cls]

    return get_instance


def get_machine_type() -> str:
    return str(platform.machine()).lower()


def get_host_ip():
    """get local ip address"""
    name = socket.gethostname()
    try:
        return socket.gethostbyname(name)
    except:  # noqa
        return name


class MethodSuppress:

    __dict__ = {}

    def __init__(self, logger, method: str = ""):
        self._method = method
        self.logger = logger

    def __getattr__(self, item):
        self.logger.error(f"{self._method} | [{item}] unable working.")
        raise AttributeError


class EnvBaseContext:
    """The Context provides the capability of obtaining the context"""
    parameters = os.environ

    def __enter__(self):
        self._raw = deepcopy(self.parameters)
        self.load()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.parameters = self._raw

    @classmethod
    def load(cls, config_map: str = ""):
        if not config_map:
            config_map = cls.get("CONFIG_MAP", "")
        if not os.path.isfile(config_map):
            return
        cls.parameters = dict(cls.parameters)
        with open(config_map, "r") as stream:
            try:
                cm = yaml.load(stream, Loader=yaml.FullLoader)
            except yaml.YAMLError as e:
                warnings.warn(f"Error detect while loading {config_map}, {e}")
            else:
                if isinstance(cm, dict):
                    cls.parameters.update(cm)
                elif isinstance(cm, (tuple, list)):
                    for item in cm:
                        if not isinstance(item, dict):
                            continue
                        cls.parameters.update(item)

    @classmethod
    def update(cls, key, value=""):
        cls.parameters[key] = value

    @classmethod
    def get(cls, param: str, default: str = None) -> str:
        """get the value of the key `param` in `PARAMETERS`,
        if not exist, the default value is returned"""
        value = cls.parameters.get(
            param) or cls.parameters.get(str(param).upper())
        return value or default

    @classmethod
    def __getitem__(cls, item: str, default: str = None):
        return cls.get(item, default)


def parse_kwargs(func: Callable, **kwargs):
    use_kwargs = getfullargspec(func)
    if use_kwargs.varkw == "kwargs":
        return dict(kwargs)
    return {k: v for k, v in kwargs.items() if k in use_kwargs.args}


def q_to_euler(q: BasePose) -> BasePose:
    my_epsilon = 1e-10
    euler = BasePose()
    sqx, sqy, sqz, sqw = np.square([q.x, q.y, q.z, q.w])

    euler.y = np.arcsin(2.0 * (q.w * q.y - q.x * q.z))
    if np.pi / 2 - np.abs(euler.y) > my_epsilon:
        euler.z = np.arctan2(
            2.0 * (q.x * q.y + q.w * q.z),
            sqx - sqy - sqz + sqw)
        euler.x = np.arctan2(
            2.0 * (q.w * q.x + q.y * q.z),
            sqw - sqx - sqy + sqz)
    else:
        euler.z = np.arctan2(
            2 * q.y * q.z - 2 * q.x * q.w,
            2 * q.x * q.z + 2 * q.y * q.w)
        euler.x = 0.0
        # If facing down, reverse yaw
        if euler.y < 0:
            euler.z = np.pi - euler.z
    return euler


def euler_to_q(euler: BasePose) -> BasePose:
    q = BasePose()
    cx, cy, cw = np.cos(np.array([euler.x, euler.y, euler.z]) / 2.0)
    sx, sy, sw = np.sin(np.array([euler.x, euler.y, euler.z]) / 2.0)
    q.x = cw * cy * sx - sw * sy * cx
    q.y = cw * sy * cx + sw * cy * sx
    q.z = sw * cy * cx - cw * sy * sx
    q.w = cw * cy * cx + sw * sy * sx

    return q
