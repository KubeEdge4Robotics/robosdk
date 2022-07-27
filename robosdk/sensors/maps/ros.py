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

import copy
import os
import tempfile
from typing import Any
from typing import Tuple

import numpy as np
import yaml
from PIL import Image
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.config import Config
from robosdk.common.constant import PgmColor
from robosdk.common.constant import PgmItem
from robosdk.common.fileops import FileOps
from robosdk.common.schema.map import PgmMap
from robosdk.utils.lazy_imports import LazyImport

from .base import MapBase

__all__ = ("RosMappingDriver",)


@ClassFactory.register(ClassType.SENSOR, alias="ros_mapping_driver")
class RosMappingDriver(MapBase):  # noqa

    def __init__(self, name, config: Config = None):
        super(RosMappingDriver, self).__init__(name=name, config=config)
        self._cv2 = LazyImport("cv2")
        self._raw_map = None
        if self.config.data.kind == "topic":
            self.get_map_from_topic()
        else:
            self.get_map_from_mapfile()

    def get_data(self) -> Tuple[PgmMap, Any]:
        self.data_lock.acquire()
        ts = self.sys_time
        data = copy.deepcopy(self.map_info)
        self.data_lock.release()
        return data, ts

    def connect(self):
        self.has_connect = True
        if self.config.data.config:
            dst = tempfile.mkdtemp()
            image_path = os.path.join(dst, "map.pgm")
            yml_path = os.path.join(dst, "map.yml")
            self.config.data.config = FileOps.download(
                self.config.data.config, yml_path)
            if self.config.data.map:
                self.config.data.map = FileOps.download(
                    self.config.data.map, image_path)

    def close(self):
        self.has_connect = False

    def get_map_from_topic(self):
        parameters = getattr(self.config.data, "subscribe", None) or {}
        self.backend.get(
            self.config.data.map, callback=self._update_map, **parameters)

    def _update_map(self, msg):
        self._raw_map = msg
        info = msg.info

        height, width = int(info.height), int(info.width)
        _data = np.flipud(
            np.reshape(np.array(msg.data), (height, width))
        )
        self.map_data = np.zeros([height, width, 3])
        self.map_data[_data == PgmItem.FREE.value] = PgmColor.FREE.value
        self.map_data[_data == PgmItem.OBSTACLE.value] = PgmColor.OBSTACLE.value
        self.map_data[_data == PgmItem.UNKNOWN.value] = PgmColor.UNKNOWN.value
        obstacles = list(zip(*np.where(_data != PgmItem.UNKNOWN.value)))

        self.map_info = PgmMap(
            map_data=self.map_data,
            size=[height, width],
            resolution=round(float(info.resolution), 4),
            origin=[
                info.origin.position.x,
                info.origin.position.y,
                info.origin.position.z
            ],
            reverse=0,
            occupied_thresh=.65,
            free_thresh=.2,

        )
        self.obstacles = self.map_info.calc_obstacle_map(obstacles)

    def get_map_from_mapfile(self):
        with open(self.config.data.config) as f:
            data = yaml.load(f, Loader=yaml.FullLoader)
        self._raw_map = data
        image = self.config.data.map or data['image']
        if not os.path.isfile(image):
            image = os.path.join(
                os.path.dirname(self.config.data.config),
                os.path.basename(image)
            )
        map_path = PgmMap(
            image=image,
            resolution=round(float(data['resolution']), 4),
            origin=list(map(float, data['origin'])),
            reverse=int(data['negate']),
            occupied_thresh=data['occupied_thresh'],
            free_thresh=data['free_thresh']
        )
        self._load(map_path)

    def _load(self, map_path: PgmMap):
        self.map_info = _info = map_path
        if map_path.image:
            fh = Image.open(map_path.image)
            height, width = fh.size
            data = np.array(fh)  # noqa
            occ = data / 255. if _info.reverse else (255. - data) / 255.
            self.map_data = (np.zeros([height, width, 3]) +
                             PgmColor.UNKNOWN.value)
            self.map_data[occ > _info.occupied_thresh] = PgmColor.OBSTACLE.value
            self.map_data[occ < _info.free_thresh] = PgmColor.FREE.value
            map_path.size = [height, width]

    def save(self, file_out, tar: bool = True):
        zip_write = LazyImport("zipfile")
        map_file_config = {
            "resolution": self.info.resolution,
            "origin": self.info.origin,
            "occupied_thresh": self.info.occupied_thresh,
            "free_thresh": self.info.free_thresh,
            "negate": int(self.info.reverse)
        }

        dst = tempfile.mkdtemp()
        image_path = os.path.join(dst, "map.pgm")
        yml_path = os.path.join(dst, "map.yml")

        map_file_config["image"] = os.path.basename(image_path)

        with open(yml_path, 'w') as file:
            yaml.dump(map_file_config, file)

        max_value = np.iinfo(np.uint8).max
        unknown_value = int(max_value * (self.info.occupied_thresh +
                                         self.info.free_thresh) / 2.)
        image = self.map_data.astype(np.float32)
        image = image / 100.0 * max_value
        image = image.astype(np.uint8)
        image = self._cv2.bitwise_not(image)
        image[np.where(self.grid_data < 0)] = unknown_value
        image = np.flipud(image)
        self._cv2.imwrite(image_path, image)
        if tar:
            out = os.path.join(dst, "map.zip")
            with zip_write.ZipFile(out, 'w') as zipObj:
                zipObj.write(image_path, "map.pgm")
                zipObj.write(yml_path, "map.yaml")
            FileOps.upload(out, file_out, clean=True)
        else:
            FileOps.upload(image_path, file_out, clean=True)
            FileOps.upload(yml_path, file_out, clean=True)
