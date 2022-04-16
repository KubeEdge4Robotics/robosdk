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
from robosdk.core.robot import Robot
from robosdk.core.world import World

from robosdk.utils.schema import BasePose
from robosdk.utils.logger import logging
from robosdk.utils.context import Context, BaseConfig
from robosdk.utils.fileops import FileOps

from robosdk.algorithms.path_planning import AStar



def main():
    world = World(name="E1")  # 初始化运行世界
    bot = Robot(name="x20", config="x20_base_config")  # 初始化机器人，加载预置的配置文件
    world.add_robot(bot)  # 导入机器人

    map_file = BaseConfig.MAP_FILE_url  # "s3://lifelong_map/e1.map.zip"
    panoptic_yml = "s3://lifelong_map/e1.map.zip.yaml"
    world.load_gridmap(map_file, panoptic=panoptic_yml)  # 加载远程栅格地图, panoptic_data 为语义信息

    goal_position = list(map(float, Context.get("goal", "").split(",")))  # 从上下文管理器从得到目标位置, 110, -10.8, 0.3
    target_coor = BasePose(x=goal_position[0], y=goal_position[1], z=goal_position[2])  # 定义目标位置
    logging.info(f"initial new Robot {bot.robot_name} in world {world.world_name}")

    waypoint = AStar(
        world_map=world.world_map,
        start=bot.navigation.get_location(),
        goal=target_coor
    ).planning()

    bot.contorl.change_gait(step="pace")
    bot.navigation.execute_track(waypoint)  # 路径规划，导航，异步操作

    rgb_path = bot.camera.capture(save_path="/tmp")
    FileOps.upload(rgb_path, BaseConfig.OUTPUT_URL)


if __name__ == '__main__':
    main()
