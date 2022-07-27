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

from robosdk.common.schema.pose import BasePose
from robosdk.utils.lazy_imports import LazyImport
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType

from .base import MapPointLocalBase


__all__ = ("TFLocalizer", )


@ClassFactory.register(ClassType.LOCALIZE, "tf")
class TFLocalizer(MapPointLocalBase):  # noqa

    def __init__(self,
                 logger=None,
                 base_link: str = "/base_link",
                 mapframe: str = "/map",
                 ):
        super(TFLocalizer, self).__init__(logger=logger)
        self._base_link = base_link
        self._map_frame = mapframe
        self.tf = LazyImport("tf")
        self.msg_geometry_generator = LazyImport("geometry_msgs.msg")

    def get_curr_state(self, *args, **kwargs) -> BasePose:
        listener = self.tf.TransformListener()
        curr_state = BasePose()
        if (listener.frameExists(self._base_link) and
                listener.frameExists(self._map_frame)):
            t = self.tf.getLatestCommonTime(self._base_link, self._map_frame)
            position, orientation = self.tf.lookupTransform(
                self._base_link, self._map_frame, t
            )
            _, _, z = self.tf.transformations.euler_from_quaternion(
                orientation.x, orientation.y, orientation.z, orientation.w
            )

            curr_state.x = position.x
            curr_state.y = position.y
            curr_state.z = z
        return curr_state

    def set_curr_state(self, goal: BasePose, seq: int = 1):
        g = self.msg_geometry_generator.PoseWithCovarianceStamped()
        g.header.seq = seq
        g.header.frame_id = self._map_frame

        q = self.tf.transformations.quaternion_from_euler(0, 0, goal.z)
        g.pose.pose.position.x = goal.x
        g.pose.pose.position.y = goal.y
        g.pose.pose.position.z = 0.0

        g.pose.pose.orientation.x = q[0]
        g.pose.pose.orientation.y = q[1]
        g.pose.pose.orientation.z = q[2]
        g.pose.pose.orientation.w = q[3]

        return g, self.msg_geometry_generator.PoseWithCovarianceStamped
