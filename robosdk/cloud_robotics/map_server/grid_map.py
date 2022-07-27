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
import subprocess

import numpy as np
import yaml
from PIL import Image
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.constant import PgmItem
from robosdk.common.schema.map import PgmMap

from .base import BaseMap

__all__ = ("RosPGMMap", )


# todo: DeprecationWarning

@ClassFactory.register(ClassType.CLOUD_ROBOTICS, alias="ros_pgm_map")
class RosPGMMap(BaseMap):  # noqa
    """
    ros grid map
    """
    _server_name_ = "map_server"

    def __init__(self):
        super(RosPGMMap, self).__init__()
        self.width = 0
        self.height = 0
        self.width_m = 0
        self.height_m = 0
        self.obstacles = []
        self.__process = None

    def start(self):
        self.stop()
        cmd = ["rosrun", "map_server", "map_server",
               f"__name:={self._server_name_}", self._map_file]
        self.__process = subprocess.Popen(cmd, shell=True,
                                          stderr=subprocess.DEVNULL)

    def stop(self):
        if self.__process:
            self.__process.kill()
        subprocess.Popen(f"rosnode kill {self._server_name_}",
                         shell=True, stderr=subprocess.DEVNULL)

    def load(self, map_file: str):  # noqa
        super(RosPGMMap, self).load(map_file=map_file)
        config = {}
        pgm = {}
        if os.path.isdir(self._map_file):
            for root, dirs, files in os.walk(self._map_file):
                for file in files:
                    file_path = os.path.join(root, file)
                    name, _ext = os.path.splitext(str(file).lower())
                    if _ext == ".pgm":
                        pgm[name] = file_path
                    elif _ext in (".yaml", ".yml"):
                        config[name] = file_path
        pgmf = None
        if not len(config):
            conf = self._map_file
        else:
            view = sorted([i for i in pgm.keys() if i in config])
            if len(view):
                conf = config[view[0]]
                pgmf = pgm[view[0]]
            else:
                conf = sorted(config.values())[0]

        self.read_from_pgm(config=conf, pgm=pgmf)

    def read_from_pgm(self, config: str, pgm: str = None):
        with open(config) as f:
            data = yaml.load(f, Loader=yaml.FullLoader)
        image = pgm if pgm else data['image']
        if not os.path.isfile(image):
            image = os.path.join(os.path.dirname(config),
                                 os.path.basename(image))
        if not os.path.isfile(image):
            prefix, _ = os.path.splitext(config)
            image = f"{prefix}.pgm"
        if not os.path.isfile(image):
            raise FileExistsError(f"Read PGM from {config} Error ...")
        self.info = PgmMap(
            image=image,
            resolution=round(float(data['resolution']), 4),
            origin=list(map(float, data['origin'])),
            reverse=int(data['negate']),
            occupied_thresh=data['occupied_thresh'],
            free_thresh=data['free_thresh']
        )
        fh = Image.open(image)
        self.height, self.width = fh.size
        self.info.size = [self.height, self.width]
        self.width_m = self.width * self.info.resolution
        self.height_m = self.height * self.info.resolution
        data = np.array(fh)  # noqa
        occ = data / 255. if self.info.reverse else (255. - data) / 255.

        self.maps = np.zeros((self.width, self.height)) + PgmItem.UNKNOWN.value
        self.maps[occ > self.info.occupied_thresh] = PgmItem.OBSTACLE.value
        self.maps[occ < self.info.free_thresh] = PgmItem.FREE.value
        obstacles = list(zip(*np.where(occ > self.info.occupied_thresh)))
        self.info.map_data = self.maps
        self.obstacles = self.map_info.calc_obstacle_map(obstacles)

    def calc_obstacle_map(self, robot_radius: float = 0.01):
        if not len(self.obstacles):
            return
        self.height, self.width = self.maps.shape[:2]
        self.width_m = self.width * self.info.resolution
        self.height_m = self.height * self.info.resolution

        if self.info.resolution < robot_radius:
            # todo: Adjust obstacles to robot size
            robot = int(robot_radius / self.info.resolution + 0.5)
            for ox, oy in self.obstacles:
                self.add_obstacle(
                    ox - robot, oy - robot,
                    ox + robot, ox + robot
                )

    def add_obstacle(self, x1, y1, x2, y2):
        # Todo
        pass

    def parse_panoptic(self, panoptic):
        # Todo
        pass
