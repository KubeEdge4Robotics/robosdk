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

from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.constant import PgmItem
from robosdk.common.schema.map import PgmMap
from robosdk.common.schema.pose import BasePose
from robosdk.common.schema.pose import PoseSeq

from .base import PathMaker

__all__ = ("AStar", )


@ClassFactory.register(ClassType.NAVIGATION)
class AStar(PathMaker):  # noqa
    """

    A* grid planning
    author: Atsushi Sakai(@Atsushi_twi)
            Nikos Kanargias (nkana@tee.gr)
    see https://github.com/AtsushiSakai/PythonRobotics/blob/master/PathPlanning/AStar/a_star.py  # noqa

    """

    def __init__(self,
                 world_map: PgmMap,
                 start: BasePose,
                 goal: BasePose):
        super(AStar, self).__init__(
            world_map=world_map, start=start, goal=goal)
        self.max_x, self.max_y = self.world.map_data.shape

    class Node:
        def __init__(self, x, y, cost, parent_index):
            self.x = x  # index of grid
            self.y = y  # index of grid
            self.cost = cost
            self.parent_index = parent_index

        def __str__(self):
            return str(self.x) + "," + str(self.y) + "," + str(
                self.cost) + "," + str(self.parent_index)

    def planning(self, step=0) -> PoseSeq:
        sx, sy = self.s_start.x, self.s_start.y
        gx, gy, angle = self.s_goal.x, self.s_goal.y, self.s_goal.z
        start_node = self.Node(self.calc_xy_index(sx),
                               self.calc_xy_index(sy), 0.0, -1)
        goal_node = self.Node(self.calc_xy_index(gx),
                              self.calc_xy_index(gy), 0.0, -1)

        open_set, closed_set = dict(), dict()
        open_set[self.calc_grid_index(start_node)] = start_node

        while 1:
            if len(open_set) == 0:
                break

            c_id = min(
                open_set,
                key=lambda o: (open_set[o].cost +
                               self.calc_heuristic(goal_node, open_set[o])))
            current = open_set[c_id]

            if current.x == goal_node.x and current.y == goal_node.y:
                goal_node.parent_index = current.parent_index
                goal_node.cost = current.cost
                break

            # Remove the item from the open set
            del open_set[c_id]

            # Add it to the closed set
            closed_set[c_id] = current

            # expand_grid search grid based on motion model
            for i, _ in enumerate(self.motion):
                node = self.Node(current.x + self.motion[i][0],
                                 current.y + self.motion[i][1],
                                 current.cost + self.motion[i][2], c_id)
                n_id = self.calc_grid_index(node)
                if (not self.verify_node(node)) or (n_id in closed_set):
                    continue

                if n_id not in open_set:
                    open_set[n_id] = node  # discovered a new node
                else:
                    if open_set[n_id].cost > node.cost:
                        # This path is the best until now. record it
                        open_set[n_id] = node

        return self.calc_final_path(
            goal_node, closed_set, angle=angle, step=step)

    def calc_final_path(self, goal_node, closed_set, angle=0.2, step=0):
        # generate final course

        rx, ry = [self.calc_grid_position(goal_node.x)], [
            self.calc_grid_position(goal_node.y)]
        parent_index = goal_node.parent_index
        while parent_index != -1:
            n = closed_set[parent_index]
            rx.append(self.calc_grid_position(n.x))
            ry.append(self.calc_grid_position(n.y))
            parent_index = n.parent_index
        prev = None
        first_node = None
        if len(rx) < 4 or step == 1:
            sequence = zip(reversed(rx), reversed(ry))
        elif step > 1:
            a1, b1 = rx[::-step], ry[::-step]
            if a1[-1] != rx[0]:
                a1.append(rx[0])
                b1.append(rx[0])
            sequence = zip(a1, b1)
        else:  # auto gen waypoint
            sequence = []
            prev = None
            for inx in range(len(rx) - 1, -1, -1):
                if (len(sequence) == 0) or (inx == 0):
                    prev = (rx[inx], ry[inx])
                    sequence.append(prev)
                    continue
                _x, _y = rx[inx], ry[inx]
                _x_n, _y_n = rx[inx - 1], ry[inx - 1]
                if ((_x_n - _x) != (_x - prev[0])) or (
                        (_y_n - _y) != (_y - prev[1])
                ):
                    sequence.append((_x, _y))
                prev = (_x, _y)
        for seq, node in enumerate(sequence):
            position = self.world.pixel2world(node[0], node[1], angle)
            curr = PoseSeq(
                seq=seq, point=node, position=position, prev=prev
            )
            if isinstance(prev, PoseSeq):
                prev.next = curr
            else:
                first_node = curr
            prev = curr
        return first_node

    @staticmethod
    def calc_heuristic(n1, n2):
        w = 1.0  # weight of heuristic
        d = w * math.hypot(n1.x - n2.x, n1.y - n2.y)
        return d

    @staticmethod
    def calc_grid_position(index, min_position=0):
        """
        calc grid position
        :param index:
        :param min_position:
        :return:
        """
        pos = index + min_position
        return pos

    @staticmethod
    def calc_xy_index(position, min_pos=0):
        return position - min_pos

    def calc_grid_index(self, node):
        return node.y * self.max_x + node.x

    def verify_node(self, node):
        px = self.calc_grid_position(node.x)
        py = self.calc_grid_position(node.y)

        if px <= 0:
            return False
        elif py <= 0:
            return False
        elif px >= self.max_x:
            return False
        elif py >= self.max_y:
            return False

        # collision check
        if self.world.map_data[node.x][node.y] == PgmItem.OBSTACLE.value:
            return False
