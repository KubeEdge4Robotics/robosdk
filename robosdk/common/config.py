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
import sys
import json
import yaml
import time
import warnings
import threading
from typing import Dict
from copy import deepcopy
from importlib import import_module

from robosdk.utils.util import singleton
from robosdk.utils.util import EnvBaseContext
from robosdk.utils.util import get_machine_type
from robosdk.utils.util import get_host_ip


__all__ = ("BaseConfig", "Config", )


def _url2dict(arg):
    if arg.endswith('.yaml') or arg.endswith('.yml'):
        with open(arg) as f:
            raw_dict = yaml.load(f, Loader=yaml.FullLoader)
    elif arg.endswith('.py'):
        module_name = os.path.basename(arg)[:-3]
        config_dir = os.path.dirname(arg)
        sys.path.insert(0, config_dir)
        mod = import_module(module_name)
        sys.path.pop(0)
        raw_dict = {
            name: value
            for name, value in mod.__dict__.items()
            if not name.startswith('__')
        }
        sys.modules.pop(module_name)
    elif arg.endswith(".json"):
        with open(arg) as f:
            raw_dict = json.load(f)
    else:
        try:
            raw_dict = json.loads(arg, encoding="utf-8")
        except json.JSONDecodeError:
            raise Exception('config file must be yaml or py')
    return raw_dict


def _dict2config(config, dic):
    """Convert dictionary to config.

    :param Config config: config
    :param dict dic: dictionary

    """
    if isinstance(dic, dict):
        for key, value in dic.items():
            if isinstance(value, dict):
                config[key] = Config()
                _dict2config(config[key], value)
            else:
                config[key] = value


class Config(dict):
    """A Config class is inherit from dict.

    Config class can parse arguments from a config file
    of yaml, json or pyscript.
    :param args: tuple of Config initial arguments
    :type args: tuple of str or dict
    :param kwargs: dict of Config initial argumnets
    :type kwargs: dict
    """

    def __init__(self, *args, **kwargs):
        """Init config class with multiple config files or dictionary."""
        super(Config, self).__init__()
        for arg in args:
            if isinstance(arg, str):
                _dict2config(self, _url2dict(arg))
            elif isinstance(arg, dict):
                _dict2config(self, arg)
            else:
                raise TypeError('args is not dict or str')
        if kwargs:
            _dict2config(self, kwargs)

    def update_obj(self, update: Dict):

        for k, v in update.items():
            orig = getattr(self, k, Config({}))
            if isinstance(orig, dict):
                orig = Config(orig)
            target = deepcopy(v)
            if isinstance(target, (Config, dict)):
                orig.update_obj(target)
                setattr(self, k, orig)
            else:
                setattr(self, k, target)

    def to_json(self, f_out):
        with open(f_out, "w", encoding="utf-8") as fh:
            json.dump(dict(self), fh, indent=4)

    def to_yaml(self, f_out):
        with open(f_out, "w", encoding="utf-8") as fh:
            yaml.dump(dict(self), fh, default_flow_style=False)

    def __call__(self, *args, **kwargs):
        """Call config class to return a new Config object.

        :return: a new Config object.
        :rtype: Config

        """
        return Config(self, *args, **kwargs)

    def __setstate__(self, state):
        """Set state is to restore state from the unpickled state values.

        :param dict state: the `state` type should be the output of
             `__getstate__`.

        """
        _dict2config(self, state)

    def __getstate__(self):
        """Return state values to be pickled.

        :return: change the Config to a dict.
        :rtype: dict

        """
        d = dict()
        for key, value in self.items():
            if isinstance(value, Config):
                value = value.__getstate__()
            d[key] = value
        return d

    def __getattr__(self, key):
        """Get a object attr by its `key`.

        :param str key: the name of object attr.
        :return: attr of object that name is `key`.
        :rtype: attr of object.

        """
        if key in self:
            return self[key]
        else:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        """Get a object attr `key` with `value`.

        :param str key: the name of object attr.
        :param value: the `value` need to set to target object attr.
        :type value: attr of object.

        """
        self[key] = value

    def __delattr__(self, key):
        """Delete a object attr by its `key`.

        :param str key: the name of object attr.

        """
        del self[key]

    def __deepcopy__(self, memo):
        """After `deepcopy`, return a Config object.

        :param dict memo: same to deepcopy `memo` dict.
        :return: a deep copyed self Config object.
        :rtype: Config object

        """
        return Config(deepcopy(dict(self)))


class UserConfig(threading.Thread):
    __semaphore__ = threading.Semaphore(1)

    def __init__(self, cfg_path: str, check_period: int = 60):
        self.cfg_path = os.path.abspath(cfg_path)
        self._period = int(check_period)
        self.__data__ = self.load(self.cfg_path)
        self._task_id = ""
        super(UserConfig, self).__init__()

    def run(self):
        while 1:
            time.sleep(self._period)
            if not (self.cfg_path and os.path.isfile(self.cfg_path)):
                continue

            self.__data__ = self.load(self.cfg_path)

    @staticmethod
    def load(cfg_path):
        # noinspection PyBroadException
        try:
            return Config(cfg_path)
        except Exception as err:
            warnings.warn(f"Update user config fail: {err}")
            return {}

    @property
    def taskId(self):
        return os.environ.get(
            "task_id",
            self.data.get("task_id", self._task_id)
        )

    @taskId.setter
    def taskId(self, new_task_id: str):
        self._task_id = new_task_id

    @property
    def data(self):
        return self.__data__

    @data.setter
    def data(self, new_data: Dict):
        if not isinstance(new_data, dict):
            raise ValueError("data must set as a dict")
        self.__data__ = Config(new_data)

    def get(self, item, default=None):
        return self.data.get(item, None) or default


@singleton
class BaseConfig:
    """ Base configuration """
    with EnvBaseContext() as Context:
        ROBO_MASTER_URI = Context.get(
            'ROS_MASTER_URI', "http://localhost:11311"
        )
        ROBOT_ID = Context.get('ROBOT_ID', "")
        MAC_TYPE = get_machine_type()
        MAC_IP = Context.get('MAC_HOST_IP', get_host_ip())

        CLOUD_SERVERS_HOST = Context.get('CLOUD_SERVERS_HOST', "")
        CLOUD_SERVERS_PORT = Context.get('CLOUD_SERVERS_PORT', "")
        CLOUD_SERVERS_SSL_KEY = Context.get('CLOUD_SERVERS_SSL_KEY', "")
        CLOUD_SERVERS_SSL_CERT = Context.get('CLOUD_SERVERS_SSL_CERT', "")
        CLOUD_SERVERS_LOG_LEV = Context.get('CLOUD_SERVERS_LOG_LEVEL', "info")

        FILE_TRANS_PROTOCOL = Context.get(
            "FILE_TRANS_PROTOCOL", "s3")  # support s3/http/local

        # Auth by searching values of the following key in `DYNAMICS_CONFING`
        FILE_TRANS_REMOTE_URI = Context.get(
            "FILE_TRANS_REMOTE_URI", "")
        FILE_TRANS_ENDPOINT_NAME = Context.get(
            "FILE_TRANS_ENDPOINT_NAME", "S3_ENDPOINT_URL")
        FILE_TRANS_AUTH_AK_NAME = Context.get(
            "FILE_TRANS_AK_NAME", "ACCESS_KEY_ID")
        FILE_TRANS_AUTH_SK_NAME = Context.get(
            "FILE_TRANS_SK_NAME", "SECRET_ACCESS_KEY")

        __cfg_search = os.path.abspath(
            os.path.join(__file__, "..", "..", "..", "configs")
        )
        if not os.path.isdir(__cfg_search):
            __cfg_search = os.path.join(
                sys.prefix, "share", "robosdk", "configs"
            )
        CONFIG_PATH = Context.get("CFG_PATH", __cfg_search)

        TEMP_DIR = Context.get("TEMP_DIR", "/tmp")
        LOG_DIR = Context.get("LOG_DIR", "/tmp")  # local path for logs saved
        LOG_URI = Context.get("LOG_URI", "")  # remote url for logs upload
        LOG_LEVEL = Context.get("LOG_LEVEL", "INFO")  # global logger level

        _DYNAMICS_CFG = Context.get(
            "USER_CFG_PATH", os.path.join(CONFIG_PATH, "system.custom.yaml")
        )  # user-defined hot loading config file

        _DYNAMICS_CFG_UPDATE_TIME = int(Context.get(
            "USER_CFG_UPDATE_TIME", "10"
        ))  # user-defined hot loading config file update time

    DYNAMICS_CONFING = UserConfig(
        cfg_path=_DYNAMICS_CFG, check_period=_DYNAMICS_CFG_UPDATE_TIME)
    DYNAMICS_CONFING.start()

    BACKEND = None
