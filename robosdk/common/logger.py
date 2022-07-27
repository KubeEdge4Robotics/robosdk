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
"""
logger provides a pre-instanced logger to the run logs
"""

import os
import sys
import atexit
import loguru

from robosdk.common.config import BaseConfig
from robosdk.common.fileops import FileOps


__all__ = ("logging", )


class _Logger:

    logger: loguru.logger = loguru.logger

    def __init__(self, base: str = BaseConfig.ROBOT_ID,
                 level: str = BaseConfig.LOG_LEVEL):
        self.logger.remove()
        if not base:
            base = "RoboArtisan"
        info_format = (
            '[<green>{time:YYYY-MM-DD HH:mm:ss.S}</green>]{extra[taskId]}'
            ':<cyan>{extra[instance]}</cyan> | <level>{level: <8}</level> | '
            '<cyan>{name}</cyan> - <level>{message}</level>'
        )
        debug_format = (
            '[<green>{time:YYYY-MM-DD HH:mm:ss.SSSS}</green>]{extra[taskId]}'
            ':<cyan>{extra[instance]}</cyan> | <level>{level: <9}</level> | '
            '<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}'
            '</level> '
        )
        log_format = debug_format if level == 'DEBUG' else info_format
        self.log_file = os.path.join(
            BaseConfig.LOG_DIR, f"{base}_launch.log"
        )
        self.sys_log_file = os.path.join(
            BaseConfig.LOG_DIR, f"{base}_system.log"
        )
        self.sensor_log_file = os.path.join(
            BaseConfig.LOG_DIR, f"{base}_sensor.log"
        )
        self.logger.add(
            self.log_file,
            format=log_format,
            level=level,
            enqueue=True,
            rotation="00:00",
            compression='tar.gz',
            encoding="utf-8",
            backtrace=True,
            diagnose=True,
            colorize=False
        )
        self.logger.add(
            self.sys_log_file,
            format=debug_format,
            level="DEBUG",
            enqueue=True,
            rotation="00:00",
            compression='tar.gz',
            encoding="utf-8",
            backtrace=True,
            diagnose=True,
            colorize=False,
            filter=lambda record: "system" in record["extra"]
        )
        self.logger.add(
            self.sensor_log_file,
            format=debug_format,
            level="DEBUG",
            enqueue=True,
            rotation="00:00",
            compression='tar.gz',
            encoding="utf-8",
            backtrace=True,
            diagnose=True,
            colorize=False,
            filter=lambda record: "sensor" in record["extra"]
        )
        self.logger = self.logger.patch(
            lambda record: record["extra"].update(
                taskId=BaseConfig.DYNAMICS_CONFING.taskId
            )
        )
        self.logger.configure(extra={"instance": base})
        self.logger.add(sys.stderr, level=level, format=log_format,
                        backtrace=True, diagnose=True, colorize=True, )
        atexit.register(self.close)

    def close(self):
        """
        Synchronizing Logs to Remote OBS
        """
        if BaseConfig.LOG_URI:
            for f in (self.sys_log_file, self.sensor_log_file, self.log_file):
                log_save = FileOps.upload(f, BaseConfig.logUri, clean=True)
                self.logger.debug(f"log files has upload to {log_save}")


logging = _Logger().logger
