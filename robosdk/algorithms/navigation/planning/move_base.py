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
from importlib import import_module

import numpy as np

from robosdk.common.schema.pose import BasePose
from robosdk.common.schema.pose import PoseSeq
from robosdk.cloud_robotics.map_server import BaseMap
from robosdk.common.constant import ActionStatus
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.exceptions import SensorError
from robosdk.utils.lazy_imports import LazyImport
from robosdk.utils.util import parse_kwargs

from .base import MovePlanner

__all__ = ("MoveBasePlanner",)


@ClassFactory.register(ClassType.NAVIGATION, alias="ros_move_base")
class MoveBasePlanner(MovePlanner):  # noqa

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

    def __init__(self, robot,
                 map_server: BaseMap = None,
                 action_spec: str = "move_base",
                 base_localizer: str = "",
                 base_sampling: str = "odom",
                 **kwargs):
        self.robot = robot
        self.map_sc = map_server
        logger = self.robot.logger
        if not hasattr(self.robot, base_sampling):
            raise SensorError(
                f"fail while loading {base_sampling} as move_base sampling")
        super(MoveBasePlanner, self).__init__(logger=logger)

        self.base_sampling = getattr(self.robot, base_sampling)
        # See also : robosdk.sensors.odom.OdometryBase
        self._action_num = 0
        self.action_lib = LazyImport("actionlib")
        self.action_msg = LazyImport("actionlib_msgs.msg")
        self.move_base_msgs = LazyImport("move_base_msgs.msg")
        self.curr_goal = BasePose()

        self.localizer = None
        if len(base_localizer):
            _ = import_module("robosdk.algorithms.localize.mapping")
            localizer = ClassFactory.get_cls(ClassType.LOCALIZE, base_localizer)
            if localizer is not None and callable(localizer):
                all_k = parse_kwargs(localizer, **kwargs)
                self.localizer = localizer(**all_k)

        self.move_base_ac = self.action_lib.SimpleActionClient(
            action_spec, self.action_msg.MoveBaseAction
        )
        self.logger.debug("Waiting for the server")
        self.cancel()
        self.move_base_ac.wait_for_server()

    @staticmethod
    def _get_absolute_pose(goal: BasePose, base: BasePose):
        nx = base.x + goal.x * np.cos(base.z) - goal.y * np.sin(base.z)
        ny = base.y + goal.x * np.sin(base.z) + goal.y * np.cos(base.z)
        nz = base.z + goal.z
        return BasePose(x=nx, y=ny, z=nz)

    def get_location(self, **kwargs) -> BasePose:
        if self.localizer and hasattr(self.localizer, "get_curr_state"):
            parameter = parse_kwargs(self.localizer.get_curr_state, **kwargs)
            return self.localizer.get_curr_state(**parameter)
        return BasePose()

    def goto(self,
             goal: BasePose,
             async_run: bool = False,
             start: BasePose = None,
             plan_alg: str = "AStar",
             **kwargs
             ) -> ActionStatus:
        if start is None:
            start = self.get_location(**kwargs)

        path_planer = ClassFactory.get_cls(ClassType.NAVIGATION, plan_alg)

        if path_planer is not None and callable(path_planer):
            all_k = parse_kwargs(path_planer, **kwargs)
            all_k["start"] = start
            all_k["goal"] = goal
            all_k["world_map"] = self.map_sc
            all_k["logger"] = self.logger

            _planer = path_planer(**all_k)
            _param = parse_kwargs(_planer.planning, **kwargs)
            seq: PoseSeq = _planer.planning(**_param)
        else:
            seq: PoseSeq = PoseSeq(
                position=start, next=goal
            )
        if async_run:
            threading.Thread(
                target=self.track_trajectory,
                args=(seq, ),
                kwargs=kwargs
            ).start()
            return ActionStatus.PENDING
        return self.track_trajectory(seq, **kwargs)

    def track_trajectory(self,
                         plan: PoseSeq,
                         min_gap: float = .15,
                         **kwargs) -> ActionStatus:
        target = plan.copy()

        while 1:
            curr_point = self.get_location(**kwargs)
            if curr_point - target <= abs(min_gap):
                target = plan.next
            if target is None:
                self.logger.info("Path planning execute complete")
                return ActionStatus.ACTIVE
            curr_goal = self._get_absolute_pose(target.position, curr_point)
            rsl = self.goto_absolute(curr_goal)
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
        self.logger.info(
            f"try to send goal {target} to robot {self.robot.robot_name}")
        self._action_num += 1
        self.goal_lock.acquire()
        self.curr_goal = target
        goal = self.base_sampling.transform_goal(
            self.curr_goal, seq=self._action_num)
        self.move_base_ac.send_goal(goal)
        state = self.move_base_ac.get_state()

        if not async_run:
            wait = self.move_base_ac.wait_for_result()
            if not wait:
                self.logger.error(
                    "Robot stuck or not able to reach pick up pose!")
                state = self.action_msg.GoalStatus.SUCCEEDED
                self.cancel()
            else:
                self.logger.info("%s: Pick up pose reached.", self.node_name)
                state = self.action_msg.GoalStatus.PREEMPTED
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
            self.robot.backend.publish(
                stop_id, data_class=self.action_msg.GoalID,
                target=self.config.data.target)
        except Exception as err:
            self.logger.debug(f"Cancel goal failure: {err}")
            self.move_base_ac.cancel_all_goals()
