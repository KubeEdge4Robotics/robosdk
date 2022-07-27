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

import cv2
import time

from robosdk.core.robot import Robot
from robosdk.common.fileops import FileOps


def main():
    robot = Robot(name="x20", config="ysc_x20")
    robot.connect()

    total_img = 10
    wait_time = .2
    upload_target = "s3://test"

    while total_img:
        time.sleep(wait_time)

        rgb, timer = robot.camera.get_rgb()
        if rgb is None:
            continue

        _ = cv2.imwrite(f"./{timer}.png", rgb)
        FileOps.upload(f"./{timer}.png", f"{upload_target}/{timer}.png")

        total_img -= 1
