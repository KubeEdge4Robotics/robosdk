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
import re
import time
from subprocess import DEVNULL
from subprocess import PIPE
from subprocess import Popen
from threading import Thread
from typing import Dict

from robosdk.common.schema.robot import RoboStatus
from robosdk.utils.lazy_imports import LazyImport
from robosdk.utils.util import get_host_ip


class RobotStatus(Thread):
    """ Get robot machine status """

    def __init__(self, timer: float = 1):

        self._period = float(timer)
        self._data = RoboStatus()
        super(RobotStatus, self).__init__()

    def run(self):
        while 1:
            time.sleep(self._period)
            try:
                self.get_status()
            except:  # noqa
                pass

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, new_data: Dict):
        if not isinstance(new_data, dict):
            raise ValueError("data must set as a dict")
        self._data = RoboStatus(**new_data)

    def get_status(self):
        psutil = LazyImport("psutil")
        cpu_usage = psutil.cpu_percent()
        mem_usage = (100 - psutil.virtual_memory().available *
                     100 / psutil.virtual_memory().total)
        disk_usage = self.get_disk_usage()
        _result = Popen('iwconfig', shell=True, stdout=PIPE, stderr=DEVNULL)
        if _result.returncode == 0:
            _output = _result.communicate()[0].decode('utf-8')
            ifname = re.match('(\w+)', _output)  # noqa
            network = re.search('ESSID(?:\W)+?(\w+)', _output)  # noqa
            quality = re.search('Link Quality(?:\W)+?(\d+)/(\d+)', _output)  # noqa
            if ifname:
                name = ifname.group(1)
                self._data.localIp = self.get_ip_address(name)
            if network:
                self._data.wifiNetwork = network.group(1)
            if quality:
                q = quality.groups()
                self._data.wifiStrength = int(q[0]) / int(q[1]) * 100
        self._data.diskUsage = disk_usage
        self._data.memUsage = mem_usage
        self._data.cpuUsage = cpu_usage

    @staticmethod
    def get_disk_usage(mount_point='/'):
        result = os.statvfs(mount_point)
        total_blocks = result.f_blocks
        free_blocks = result.f_bfree
        return 100 - (free_blocks * 100 / total_blocks)

    @staticmethod
    def get_ip_address(ifname: str = "wlan0"):
        try:
            _result = Popen(f'ip addr show {ifname}', shell=True,
                            stdout=PIPE, stderr=DEVNULL)
            _output = _result.communicate()[0].decode('utf-8')
            address = re.search("inet(?:\s+)?([0-9\.]+)", _output).group(1)  # noqa
        except:  # noqa
            address = get_host_ip()
        return address
