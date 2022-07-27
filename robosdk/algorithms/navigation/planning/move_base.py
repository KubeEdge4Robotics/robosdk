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
import os.path
import threading
from importlib import import_module

import numpy as np
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.config import BaseConfig
from robosdk.common.config import Config
from robosdk.common.constant import ActionStatus
from robosdk.common.schema.pose import BasePose
from robosdk.common.schema.pose import PoseSeq
from robosdk.utils.lazy_imports import LazyImport
from robosdk.utils.util import parse_kwargs

from .base import MovePlanner

__all__ = ("RosMoveBase",)


@ClassFactory.register(ClassType.NAVIGATION, alias="ros_move_base")
class RosMoveBase(MovePlanner):  # noqa

    HealthyState = [
        ActionStatus.PENDING,
        ActionStatus.RECALLING,
        ActionStatus.RECALLED
    ]
    AbnormalState = [
        ActionStatus.PREEMPTED,
        ActionStatus.ABORTED,
        ActionStatus.REJECTED,
        ActionStatus.PREEMPTING,
        ActionStatus.LOST
    ]
    CompleteState = [
        ActionStatus.ACTIVE,
        ActionStatus.SUCCEEDED
    ]

    def __init__(self, logger=None):
        super(RosMoveBase, self).__init__(logger=logger)
        base_sampling = self.alg_config.sampling.name or "odom"
        action_spec = self.alg_config.target.action or "move_base"

        self.base_sampling = None
        if base_sampling:
            self._initial_base_sampling(base_sampling)
        self._action_num = 0
        self.action_lib = LazyImport("actionlib")
        self.action_msg = LazyImport("actionlib_msgs.msg")
        self.move_base_msgs = LazyImport("move_base_msgs.msg")
        self.curr_goal = BasePose()
        self.move_base_ac = self.action_lib.SimpleActionClient(
            action_spec, self.move_base_msgs.MoveBaseAction
        )
        self.logger.debug("Waiting for the server")
        self.cancel()
        self.move_base_ac.wait_for_server()

    def _initial_base_sampling(self, base_sampling):
        sampling_cfg = self.alg_config.sampling.config or "odom"

        sampling_cfg = os.path.join(
            BaseConfig.CONFIG_PATH,
            base_sampling, f"{sampling_cfg}.yaml"
        )
        sensor_cfg = Config(sampling_cfg)
        sensor_cfg.update_obj(self.alg_config.sampling.data)
        try:
            _ = import_module(f"robosdk.sensors.{base_sampling.lower()}")
        except (ModuleNotFoundError, AttributeError):
            self.logger.error(f"Non-existent sensor driver: "
                              f"`robosdk.sensors.{base_sampling.lower()}`")
        try:
            driver_cls = ClassFactory.get_cls(
                ClassType.SENSOR, sensor_cfg['driver']['name'])

            self.base_sampling = driver_cls(
                name=base_sampling, config=sensor_cfg)
            self.base_sampling.connect()
        except Exception as err:  # noqa
            self.logger.error(
                f"Initial sensor driver {base_sampling} failure : {err}")
            self.base_sampling = None
        # See also : robosdk.sensors.odom.OdometryBase

    @staticmethod
    def _get_absolute_pose(goal: BasePose, base: BasePose):
        nx = base.x + goal.x * np.cos(base.z) - goal.y * np.sin(base.z)
        ny = base.y + goal.x * np.sin(base.z) + goal.y * np.cos(base.z)
        nz = base.z + goal.z
        return BasePose(x=nx, y=ny, z=nz)

    def get_location(self, **kwargs) -> BasePose:
        if self.base_sampling and hasattr(self.base_sampling, "get_curr_state"):
            vw = parse_kwargs(self.base_sampling.get_curr_state, **kwargs)
            return self.base_sampling.get_curr_state(**vw)
        return BasePose()

    def navigate_to_goal(self, pose_goal):
        self._action_num += 1

        map_frame = self.alg_config.target.map_frame or "map"

        goal = self.move_base_msgs.MoveBaseGoal()
        goal.target_pose.header.frame_id = map_frame
        goal.target_pose.header.stamp = self.backend.now
        goal.target_pose.header.seq = self._action_num
        goal.target_pose.pose.position.x = pose_goal.x
        goal.target_pose.pose.position.y = pose_goal.y
        goal.target_pose.pose.orientation.w = pose_goal.z
        self.move_base_ac.send_goal(goal)
        self.move_base_ac.wait_for_result()
        state = self.move_base_ac.get_state()
        return self._convert_state_val(state)

    def goto(self,
             goal: BasePose,
             async_run: bool = False,
             start: BasePose = None,
             **kwargs
             ) -> ActionStatus:
        if start is None and self.base_sampling:
            start = self.get_location(**kwargs)
        seq: PoseSeq = PoseSeq(
            position=start, next=goal
        )
        if async_run:
            threading.Thread(
                target=self.track_trajectory,
                args=(seq, ), daemon=True,
                kwargs=kwargs
            ).start()
            return ActionStatus.PENDING
        return self.track_trajectory(seq, **kwargs)

    def track_trajectory(self,
                         plan: PoseSeq,
                         min_gap: float = .15,
                         **kwargs) -> ActionStatus:
        target = plan.next

        while 1:
            curr_point = self.get_location(**kwargs)
            if curr_point - target <= abs(min_gap):
                target = plan.next
            if target is None:
                self.logger.info("Path planning execute complete")
                return ActionStatus.ACTIVE
            curr_goal = self._get_absolute_pose(target, curr_point)
            rsl = self.goto_absolute(curr_goal)
            # rsl = self.navigate_to_goal(target)
            if rsl in self.HealthyState:
                continue
            if rsl in self.AbnormalState:
                self.logger.error(f"Path planning execute failure: {rsl.name}")
                return rsl
        self.logger.info("Path planning execute complete")
        return ActionStatus.SUCCEEDED

    def goto_absolute(self,
                      target: BasePose,
                      async_run: bool = False,
                      **kwargs
                      ) -> ActionStatus:
        self.logger.info(f"try to send goal {target} to robot")
        self._action_num += 1
        self.goal_lock.acquire()
        self.curr_goal = target
        if self.base_sampling:
            target = self.base_sampling.transform_goal(
                self.curr_goal, seq=self._action_num)
            goal = self.move_base_msgs.MoveBaseGoal(target_pose=target)
            self.move_base_ac.send_goal(goal)
        state = self.move_base_ac.get_state()

        if not async_run:
            wait = self.move_base_ac.wait_for_result()
            if not wait:
                self.logger.error(
                    "Robot stuck or not able to reach pick up pose!")
                state = self.action_msg.GoalStatus.PREEMPTED
                self.cancel()
            else:
                self.logger.info("Robot Pick up pose reached.")
                state = self.action_msg.GoalStatus.SUCCEEDED
        self.goal_lock.release()

        return self._convert_state_val(state)

    def _convert_state_val(self, state) -> ActionStatus:
        #  PENDING     = 0   # The goal has yet to be processed
        #  ACTIVE      = 1   # The goal is currently being processed
        #  PREEMPTED   = 2   # The goal received a cancel request after started
        #                       executing and has since completed its execution
        #  SUCCEEDED   = 3   # The goal was achieved successfully
        #  ABORTED     = 4   # The goal was aborted during execution due
        #                      to some failure
        #  REJECTED    = 5   # The goal was rejected without being processed,
        #                      because the goal was unattainable or invalid
        #  PREEMPTING  = 6   # The goal received a cancel request after started
        #                      executing and has not yet completed execution
        #  RECALLING   = 7   # The goal received a cancel request before started
        #                      executing, but the action server has not yet
        #                      confirmed that the goal is canceled
        #  RECALLED    = 8   # The goal received a cancel request before started
        #                      executing and was successfully cancelled
        #  LOST        = 9   # An action client can determine that a goal is
        #                      LOST. This should not be sent over the wire by
        #                      an action server

        _map = {
            self.action_msg.GoalStatus.PENDING: ActionStatus.PENDING,
            self.action_msg.GoalStatus.ACTIVE: ActionStatus.ACTIVE,
            self.action_msg.GoalStatus.PREEMPTED: ActionStatus.PREEMPTED,
            self.action_msg.GoalStatus.SUCCEEDED: ActionStatus.SUCCEEDED,
            self.action_msg.GoalStatus.ABORTED: ActionStatus.ABORTED,
            self.action_msg.GoalStatus.REJECTED: ActionStatus.REJECTED,
            self.action_msg.GoalStatus.PREEMPTING: ActionStatus.PREEMPTING,
            self.action_msg.GoalStatus.RECALLING: ActionStatus.RECALLING,
            self.action_msg.GoalStatus.RECALLED: ActionStatus.RECALLED,
            self.action_msg.GoalStatus.LOST: ActionStatus.LOST,
        }
        return _map.get(state, ActionStatus.UNKONWN)

    @property
    def state(self) -> ActionStatus:
        return self._convert_state_val(self.move_base_ac.get_state())

    def cancel(self):
        self.logger.warning("Goal Cancel")

        stop_id = self.action_msg.GoalID()
        try:
            self.backend.publish(
                data=stop_id, data_class=self.action_msg.GoalID,
                name=self.config.data.target)
        except Exception as err:
            self.logger.debug(f"Cancel goal failure: {err}")
            self.move_base_ac.cancel_all_goals()
