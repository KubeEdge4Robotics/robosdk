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

from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.cloud_robotics.map_server import BaseMap
from robosdk.cloud_robotics.remote_control.cloud.command import ControlWSServer

from .base import RoboBase

__all__ = ("World", )


class World(RoboBase):

    def __init__(self,
                 name: str,
                 config: str = None,
                 ):
        super(World, self).__init__(name=name, config=config, kind="worlds")
        self.world_name = name

        world_map: BaseMap = ClassFactory.get_cls(
            ClassType.CLOUD_ROBOTICS,
            self.config.map.name
        )
        if world_map is None:
            self.world_map = None
            self.logger.warning(f"{self.config.map.name} initial failure")
        else:
            self.world_map = world_map(**self.config.map.param)  # noqa
        self._server = ControlWSServer(
            name=self.world_name,
            host=self.config.service.host,
            port=self.config.service.port
        )
        self.all_robots = {}

    def load_map(self, map_file: str, panoptic: str = None):
        """
        Initial word map by loading the map with panoptic datas
        :param map_file: map path, file
        :param panoptic: semantic information, yaml
        """
        if self.world_map is None:
            self.logger.error(
                "map server should be initial before loading mapfile")
            return
        self.world_map.load(map_file=map_file)
        if panoptic:
            self.logger.info(f"parsing panoptic to map from {panoptic}")
            self.world_map.parse_panoptic(panoptic)

    def start(self):
        self.logger.info("starting map server")
        self.world_map.calc_obstacle_map()
        self.world_map.start()
        self.logger.info("complete map server setup")

        self.logger.info("starting world server")
        self._server.run()

    def close(self):
        self.logger.info("stopping map server")
        self.world_map.stop()

        self.logger.info("stopping world server")
        self._server.close()
