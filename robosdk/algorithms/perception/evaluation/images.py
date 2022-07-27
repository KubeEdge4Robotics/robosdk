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

import math
from typing import List

import numpy as np
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.exceptions import RoboError
from robosdk.utils.lazy_imports import LazyImport

from .base import SampleEvaluateBase

__all__ = ("ImagQualityEval", )


@ClassFactory.register(ClassType.PERCEPTION)
class ImagQualityEval(SampleEvaluateBase):  # noqa

    _support_alg = (
        "brenner", "smd", "smd2",
        "variance", "energy", "vollath", "entropy"
    )

    def __init__(self, logger=None):
        super(ImagQualityEval, self).__init__(logger=logger)
        self.cv2 = LazyImport("cv2")

    @classmethod
    def brenner(cls, img):
        shape = np.shape(img)
        out = 0
        for x in range(0, shape[0] - 2):
            for y in range(0, shape[1]):
                out += (int(img[x + 2, y]) - int(img[x, y])) ** 2
        return out

    @classmethod
    def smd(cls, img):
        shape = np.shape(img)
        out = 0
        for x in range(1, shape[0] - 1):
            for y in range(0, shape[1]):
                out += math.fabs(int(img[x, y]) - int(img[x, y - 1]))
                out += math.fabs(int(img[x, y] - int(img[x + 1, y])))
        return out

    @classmethod
    def smd2(cls, img):
        shape = np.shape(img)
        out = 0
        for x in range(0, shape[0] - 1):
            for y in range(0, shape[1] - 1):
                out += math.fabs(
                    int(img[x, y]) - int(img[x + 1, y])) * math.fabs(
                    int(img[x, y] - int(img[x, y + 1])))
        return out

    @classmethod
    def variance(cls, img):
        out = 0
        u = np.mean(img)
        shape = np.shape(img)
        for x in range(0, shape[0]):
            for y in range(0, shape[1]):
                out += (img[x, y] - u) ** 2
        return out

    @classmethod
    def energy(cls, img):
        shape = np.shape(img)
        out = 0
        for x in range(0, shape[0] - 1):
            for y in range(0, shape[1] - 1):
                out += (((int(img[x + 1, y]) - int(img[x, y])) ** 2) *
                        ((int(img[x, y + 1] - int(img[x, y]))) ** 2))
        return out

    @classmethod
    def vollath(cls, img):
        shape = np.shape(img)
        u = np.mean(img)
        out = -shape[0] * shape[1] * (u ** 2)
        for x in range(0, shape[0] - 1):
            for y in range(0, shape[1]):
                out += int(img[x, y]) * int(img[x + 1, y])
        return out

    @classmethod
    def entropy(cls, img):
        out = 0
        count = np.shape(img)[0] * np.shape(img)[1]
        p = np.bincount(np.array(img).flatten())
        for i in range(0, len(p)):
            if p[i] != 0:
                out -= p[i] * math.log(p[i] / count) / count
        return out

    def evaluation(self, samples: List[np.ndarray], eval_alg: str = "entropy"):
        if not len(samples):
            raise RoboError("No input images found")
        if len(samples) == 1:
            return samples[0]
        if eval_alg not in self._support_alg:
            self.logger.error(f"not support eval algorithms: {eval_alg}")
            evaluator = self.vollath
        else:
            evaluator = getattr(self, eval_alg)
        s = sorted(samples, key=lambda j: evaluator(
            self.cv2.cvtColor(j, self.cv2.COLOR_BGR2GRAY)
        ))
        return s[-1]
