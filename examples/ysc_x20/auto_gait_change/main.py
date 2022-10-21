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

import time
from typing import (
    List,
    Tuple
)

import numpy as np
import cv2

from robosdk.core import Robot
from robosdk.common.constant import GaitType


class DepthBaseJudgment:
    """
    In this method, we will only use the depth camera to calc the difference of
    the estimated depth of the front position. If the difference is greater
    than the threshold, make dog change to `stair` gaitType.
    The robustness of this method has not been proved,
    it is only used as a demo.
    """
    dogHeight = 450
    imgShape = (424, 240)
    dogFov = (69.4, 42.5)
    # ref: https://www.intel.com/content/www/us/en/support/articles/000030385/emerging-technologies/intel-realsense-technology.html # noqa

    def __init__(self, threshold: int = 50):
        self.threshold = max(threshold, 1)
        self._h_fov = self.dogFov[1] * self.imgShape[1] / self.imgShape[0]
        self._curr_lookup = np.sin(
            (90. - self._h_fov / 2) * np.pi / 180.
        )
        self._forward_lookup = np.sin(
            (90. - self._h_fov * 1.5) * np.pi / 180.
        )

        self._lookup_seq: List = []

    def predict(self, dep_data: np.ndarray) -> Tuple[str, GaitType]:
        if np.max(dep_data) < 1000:
            dep_data *= 1000
        canvas = cv2.resize(dep_data, self.imgShape)
        width, height = self.imgShape
        mid_x, mid_y = int(height // 2), int(width // 2)
        _r = 5
        min_depth = 10
        curr = canvas[height - _r: height, mid_y - _r: mid_y + _r]
        curr_depth = np.median(curr[curr > min_depth])

        if not np.isnan(curr_depth):
            self.dogHeight = curr_depth * self._curr_lookup
        forward = canvas[mid_x - _r: mid_x + _r, mid_y - _r: mid_y + _r]
        forward_depth = np.median(forward[forward > min_depth])
        forward_plane_depth = self.dogHeight / self._forward_lookup
        if np.isnan(forward_depth):
            forward_depth = forward_plane_depth
        diff = (forward_plane_depth - forward_depth) * self._forward_lookup

        take_len = len(self._lookup_seq)
        if take_len > 4:
            self._lookup_seq = self._lookup_seq[take_len - 4:]
        self._lookup_seq.append(diff)

        diff = np.mean(self._lookup_seq)
        if abs(diff) > self.threshold:
            rsl = "up" if diff > 0 else "down"
            gait = GaitType.UPSTAIR
        else:
            rsl = "plane"
            gait = GaitType.TROT
        return rsl, gait


class DogAutoGait:
    WAIT_TIME_AFTER_CHANGE = 3

    def __init__(self):
        self.robot = Robot(name="dog", config="ysc_x20")
        self.robot.connect()
        self.detector = DepthBaseJudgment()

    def run(self):

        # make camera_front_down as default camera
        self.robot.switch_sensor("camera", "camera_front_down")

        data_cls = self.robot.backend.msg_sensor_generator.Image
        data_trans = self.robot.camera.cv_bridge.cv2_to_imgmsg
        
        while 1:
            img, depth = self.robot.camera.get_rgb_depth()

            if img is None or depth is None:
                time.sleep(.1)
                continue
            curr_gait = self.robot.legged.get_curr_gait()
            rsl, gait = self.detector.predict(depth)
            _text = f"Curr Gait: {gait} - {rsl}"
            cv2.putText(
                img, _text, (20, 20), cv2.FONT_HERSHEY_SIMPLEX, 
                .8, (255, 255, 0), thickness=1
            )
            if curr_gait != gait:
                self.robot.logger.info(
                    f"DepthBaseJudgment: {rsl}-{gait}, now {gait}")
                self.robot.legged.change_gait(gait)
                time.sleep(self.WAIT_TIME_AFTER_CHANGE)
            else:
                self.robot.logger.debug(f"DepthBaseJudgment: {rsl}-{gait}")
            self.robot.backend.publish(
                name="gait_detect", 
                data=data_trans(img), 
                data_class=data_cls
            )


if __name__ == '__main__':
    client = DogAutoGait()
    client.run()
