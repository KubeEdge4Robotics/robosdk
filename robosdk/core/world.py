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

from importlib import import_module

from robosdk.cloud_robotics.map_server import BaseMap
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.config import BaseConfig

from .base import RoboBase

__all__ = ("World", )


class World(RoboBase):
    """
    This class builds world specific objects by reading
    """

    def __init__(self,
                 name: str,
                 config: str = None,
                 ):
        super(World, self).__init__(name=name, config=config, kind="worlds")
        self.world_name = name

        world_map: BaseMap = ClassFactory.get_cls(
            ClassType.CLOUD_ROBOTICS,
            self.config.map.driver
        )
        if world_map is None:
            self.world_map = None
            self.logger.warning(f"{self.config.map.name} initial failure")
        else:
            param = self.config.map.param or {}
            self.world_map = world_map(**param)  # noqa
        self.map_file = self.config.map.save_url or BaseConfig.MAP_SAVE_URL
        _ = import_module("robosdk.cloud_robotics.remote_control.cloud")
        server = ClassFactory.get_cls(
            ClassType.CLOUD_ROBOTICS,
            self.config.service.driver
        )
        if server is None:
            self._server = None
            self.logger.warning(f"{self.config.service.name} initial failure")
        else:
            self._server = server(
                name=self.world_name,
                **self.config.service.param
            )

    def load_map(self, map_file: str = "", panoptic: str = None):
        """
        Initial word map by loading the map with panoptic datas
        :param map_file: map path, file
        :param panoptic: semantic information, yaml
        """
        if self.world_map is None:
            self.logger.error(
                "map server should be initial before loading mapfile")
            return
        if not map_file:
            map_file = self.map_file
        else:
            self.map_file = map_file
        self.world_map.load(map_file=map_file)
        if panoptic:
            self.logger.info(f"parsing panoptic to map from {panoptic}")
            self.world_map.parse_panoptic(panoptic)

    def start(self):
        """
        Start world server
        """
        if self.world_map is not None:
            self.logger.info("starting map server")
            self.world_map.calc_obstacle_map()
            self.world_map.start()
            self.logger.info("complete map server setup")

        if self._server is not None:
            self.logger.info("starting world server")
            if self.world_map and hasattr(self.world_map, "map_file"):
                self._server.set_world_map(self.world_map.map_file)
            self._server.run()

    def close(self):
        if self.world_map is not None:
            self.logger.info("stopping map server")
            self.world_map.stop()

        if self._server is not None:
            self.logger.info("stopping world server")
            self._server.close()
