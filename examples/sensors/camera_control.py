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
from robosdk.utils.fileops import FileOps


def main():
    robot = Robot(name="x20", config="ysc_x20")
    robot.connect()

    rgb_path = robot.camera.capture(save_path="/tmp/test.png")
    FileOps.upload(rgb_path, "s3://test/test.png")


if __name__ == '__main__':
    main()
