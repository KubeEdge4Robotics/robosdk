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

import threading
from typing import Any
from typing import Tuple

import numpy as np
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.config import Config
from robosdk.common.schema.pose import BasePose
from robosdk.sensors.base import RosSensorBase
from robosdk.utils.lazy_imports import LazyImport

from .base import OdometryBase

__all__ = ("RosOdomDriver", "RosTFDriver")


class RosOdometryBase(OdometryBase):  # noqa

    def __init__(self, name, config: Config = None):
        super(RosOdometryBase, self).__init__(name=name, config=config)
        self._base_link = getattr(self.config.data, "base_link", "base_link")
        self._map_frame = getattr(self.config.data, "map_frame", "map")
        self._transformer = LazyImport("tf.transformations")

    @property
    def pose(self):
        raise NotImplementedError

    def get_position(self) -> Tuple[BasePose, Any]:
        raise NotImplementedError

    def get_orientation(self) -> Tuple[BasePose, Any]:
        raise NotImplementedError

    def _transfrom(self, value: str, sub_value: str):
        pose = BasePose()
        ts = self.sys_time
        v = getattr(self.pose, value, None)
        if not (v and hasattr(v, sub_value)):
            return pose, ts
        state = getattr(v, sub_value)
        pose.x = getattr(state, "x", 0)
        pose.y = getattr(state, "y", 0)
        pose.z = getattr(state, "z", 0)
        pose.w = getattr(state, "w", 0)
        return pose, ts

    def get_angular_velocity(self) -> Tuple[BasePose, Any]:
        return self._transfrom("twist", "angular")

    def get_linear_acceleration(self) -> Tuple[BasePose, Any]:
        return self._transfrom("twist", "linear")

    def quat2mat(self, data: np.ndarray, base_position: np.ndarray = None):
        position, _ = self.get_position()
        orientation, _ = self.get_orientation()
        rotation = self._transformer.quaternion_matrix((
            orientation.x,
            orientation.y,
            orientation.z,
            orientation.w,
        ))
        shape = data.shape
        s = 4 - shape[1]
        if s > 0:
            data = np.hstack((data, np.zeros((shape[0], s))))
        elif s < 0:
            data = data[..., : 4]
        points = rotation.dot(data.T).T
        points[..., 0] += position.x
        points[..., 1] += position.y
        points[..., 2] += position.z

        if base_position is not None:
            _local = rotation.T.dot((points - base_position).T).T
            points = _local[..., :shape[1]]
        return points

    def transform_goal(self, goal: BasePose, seq: int = 1):
        g = self.backend.msg_geometry_generator.PoseStamped()
        g.header.seq = seq
        g.header.stamp = self.backend.now
        g.header.frame_id = self._map_frame

        q = self._transformer.quaternion_from_euler(0, 0, goal.z)
        g.pose.position.x = goal.x
        g.pose.position.y = goal.y
        g.pose.position.z = 0.0

        g.pose.orientation.x = q[0]
        g.pose.orientation.y = q[1]
        g.pose.orientation.z = q[2]
        g.pose.orientation.w = q[3]
        return g

    def get_curr_state(self, **kwargs) -> BasePose:
        curr_state = BasePose()

        position, _ = self.get_position()
        orientation, _ = self.get_orientation()

        _, _, z = self._transformer.euler_from_quaternion((
            orientation.x,
            orientation.y,
            orientation.z,
            orientation.w
        ))

        curr_state.x = position.x
        curr_state.y = position.y
        curr_state.z = z

        return curr_state

    def set_curr_state(self, state: BasePose, seq: int = 1):

        _pose = self.transform_goal(goal=state, seq=seq)

        _dc = self.backend.msg_geometry_generator.PoseStamped
        self.backend.publish(data=_pose,
                             data_class=_dc,
                             name=self.config.data.target)


@ClassFactory.register(ClassType.SENSOR, alias="ros_odom_driver")
class RosOdomDriver(RosSensorBase, RosOdometryBase):  # noqa

    def __init__(self, name, config: Config = None):
        super(RosOdomDriver, self).__init__(name=name, config=config)

    @property
    def pose(self):
        return self._raw

    def get_position(self) -> Tuple[BasePose, Any]:
        return self._transfrom("pose", "position")

    def get_orientation(self) -> Tuple[BasePose, Any]:
        return self._transfrom("pose", "orientation")


@ClassFactory.register(ClassType.SENSOR, alias="ros_tf_driver")
class RosTFDriver(RosOdometryBase):  # noqa

    def __init__(self, name, config: Config = None):
        super(RosTFDriver, self).__init__(name=name, config=config)
        self._tf = LazyImport("tf2_ros")
        self._orientation = None
        self._position = None
        self._raw = None

    def get_position(self) -> Tuple[BasePose, Any]:
        pose = BasePose()
        ts = self.sys_time

        if self._position is None:
            return pose, ts
        pose.x = self._position.x
        pose.y = self._position.y
        pose.z = self._position.z
        return pose, ts

    def get_orientation(self) -> Tuple[BasePose, Any]:
        orientation = BasePose()
        ts = self.sys_time

        if not self._orientation:
            return orientation, ts
        orientation.x = self._orientation.x
        orientation.y = self._orientation.y
        orientation.z = self._orientation.z
        orientation.w = self._orientation.w
        return orientation, ts

    def _get_pose(self):
        while 1:
            buffer = self._tf.Buffer()
            _ = self._tf.TransformListener(buffer)
            trans = self.backend.msg_geometry_generator.TransformStamped()
            try:
                trans = buffer.lookup_transform(
                    self._map_frame, self._base_link,
                    self.backend.client.Time(0),
                    timeout=self.backend.client.Duration(10.)
                )
            except Exception as err:  # noqa
                self.logger.error(f"lookup Transform fail: {err}")
                self.backend.client.sleep(.1)
            self._position = trans.transform.translation
            self._orientation = trans.transform.rotation
            self._raw = trans

    @property
    def pose(self):
        return self._raw

    def connect(self):
        if self.has_connect:
            return
        self.has_connect = True
        threading.Thread(target=self._get_pose, daemon=True).start()
