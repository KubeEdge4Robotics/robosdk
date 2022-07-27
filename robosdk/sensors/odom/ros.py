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

from typing import (
    Tuple,
    Any
)

from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.config import Config
from robosdk.common.schema.pose import BasePose
from robosdk.utils.lazy_imports import LazyImport
from robosdk.sensors.base import RosSensorBase

from .base import OdometryBase

__all__ = ("RosOdomDriver",)


@ClassFactory.register(ClassType.SENSOR, alias="ros_odom_driver")
class RosOdomDriver(RosSensorBase, OdometryBase):  # noqa

    def __init__(self, name, config: Config = None):
        super(RosOdomDriver, self).__init__(name=name, config=config)
        self.mapframe_id = getattr(self.config.data, "mapframe", "") or "map"
        self.frame_id = getattr(self.config.data, "frame_id", "") or "odom"
        self.child_frame_id = (getattr(self.config.data, "child_frame_id", "")
                               or "base_link")
        self.curr_state = BasePose()
        self._transformer = LazyImport("tf.transformations")

    def get_position(self) -> Tuple[BasePose, Any]:
        pose = BasePose()
        ts = self.sys_time

        if not hasattr(self._raw, "pose"):
            return pose, ts
        pose.x = self._raw.pose.pose.postion.x
        pose.y = self._raw.pose.pose.postion.y
        pose.z = self._raw.pose.pose.postion.z
        return pose, ts

    def get_orientation(self) -> Tuple[BasePose, Any]:
        orientation = BasePose()
        ts = self.sys_time

        if not hasattr(self._raw, "pose"):
            return orientation, ts
        orientation.x = self._raw.pose.pose.orientation.x
        orientation.y = self._raw.pose.pose.orientation.y
        orientation.z = self._raw.pose.pose.orientation.z
        orientation.w = self._raw.pose.pose.orientation.z
        return orientation, ts

    def get_angular_velocity(self) -> Tuple[BasePose, Any]:
        angel = BasePose()
        ts = self.sys_time
        if not hasattr(self._raw, "twist"):
            return angel, ts
        angel.x = self._raw.twist.twist.angular.x
        angel.y = self._raw.twist.twist.angular.y
        angel.z = self._raw.twist.twist.angular.z
        return angel, ts

    def get_linear_acceleration(self) -> Tuple[BasePose, Any]:
        linear = BasePose()
        ts = self.sys_time
        if not hasattr(self._raw, "twist"):
            return linear, ts
        linear.x = self._raw.twist.twist.linear.x
        linear.y = self._raw.twist.twist.linear.y
        linear.z = self._raw.twist.twist.linear.z
        return linear, ts

    def _callback(self, data):
        super(RosOdomDriver, self)._callback(data=data)
        position, _ = self.get_position()
        orientation, _ = self.get_orientation()

        _, _, z = self._transformer.euler_from_quaternion(
            orientation.x, orientation.y, orientation.z, orientation.w
        )

        self.curr_state.x = position.x
        self.curr_state.y = position.y
        self.curr_state.z = z

    def transform_goal(self, goal: BasePose, seq: int = 1):
        g = self.backend.msg_geometry_generator.PoseWithCovarianceStamped()
        g.header.seq = seq
        g.header.stamp = self.backend.now
        g.header.frame_id = self.mapframe_id

        q = self._transformer.quaternion_from_euler(0, 0, goal.z)
        g.pose.pose.position.x = goal.x
        g.pose.pose.position.y = goal.y
        g.pose.pose.position.z = 0.0

        g.pose.pose.orientation.x = q[0]
        g.pose.pose.orientation.y = q[1]
        g.pose.pose.orientation.z = q[2]
        g.pose.pose.orientation.w = q[3]
        return g

    def update(self, state: BasePose, seq: int = 1):

        _pose = self.transform_goal(goal=state, seq=seq)

        _dc = self.backend.msg_geometry_generator.PoseWithCovarianceStamped
        self.backend.publish(_pose,
                             data_class=_dc,
                             target=self.config.data.target)
