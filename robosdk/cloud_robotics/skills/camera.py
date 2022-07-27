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
import tempfile
import time

from robosdk.algorithms.perception.evaluation.images import ImagQualityEval
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.fileops import FileOps

from .base import SkillBase

__all__ = ("CapturePhoto", )


@ClassFactory.register(ClassType.ROBOTICS_SKILL, alias="capture_photo")
class CapturePhoto(SkillBase):  # noqa
    _cap_time_hold = .5

    def __init__(self, robot):
        super(CapturePhoto, self).__init__(name="CapturePhoto", robot=robot)
        self._eval_func = ImagQualityEval(logger=self.logger)

    def call(self,
             output: str,
             candidate: int = 10,
             eval_method: str = "entropy"):

        candidates = []
        for _ in range(candidate):
            rgb, timer = self.robot.camera.get_rgb()
            if rgb is None:
                continue
            candidates.append(rgb)
            time.sleep(self._cap_time_hold)
        img_selected = self._eval_func.evaluation(
            candidates, eval_alg=eval_method)
        save_name = os.path.basename(output)
        _, ext = os.path.splitext(save_name)
        if not ext:
            save_name = "tmp.png"
        dst = tempfile.mkdtemp()
        tmp = os.path.join(dst, save_name)
        try:
            self._eval_func.cv2.imwrite(
                tmp, img_selected
            )
            output = FileOps.upload(tmp, output)
        except Exception as e: # noqa
            self.logger.error(f"save image error, {e}")
        else:
            self.logger.info(f"save image to {output}")
