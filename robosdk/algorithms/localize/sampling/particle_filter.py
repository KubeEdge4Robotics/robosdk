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

from copy import deepcopy

import numpy as np

from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from .base import SampleFilterBase


__all__ = ("ParticleFilter", )


@ClassFactory.register(ClassType.LOCALIZE)
class ParticleFilter(SampleFilterBase):
    def __init__(self, logger=None):
        super(ParticleFilter, self).__init__(logger=logger)
        self.particles = []

    def add_particle(self, p):
        self.particles.append(p)

    def normalize(self):
        w_sum = sum([p.weight for p in self.particles])
        return [p.normalize_weight(w_sum) for p in self.particles]

    def integrate_observation(self, observation):
        for p in self.particles:
            p.integrate_observation(observation)

    def predict(self, delta):
        for p in self.particles:
            p.predict(delta)

    @staticmethod
    def weighted_values(values, probabilities, size):
        bins = np.add.accumulate(probabilities)
        indices = np.digitize(np.random.random_sample(size), bins)
        sample = []
        for ind in indices:
            sample.append(deepcopy(values[ind]))
        return sample

    def resample(self):
        self.particles = self.weighted_values(
            self.particles,
            [p.weight for p in self.particles],
            len(self.particles)
        )
        for p in self.particles:
            p.weight = 1./len(self.particles)
