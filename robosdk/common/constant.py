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
"""System const variable"""

from enum import Enum


class Compression(Enum):
    """
    Allowable compression types
    """
    NONE = 'none'
    BZ2 = 'bz2'
    LZ4 = 'lz4'


class RoboControlMode(Enum):
    Auto = 0
    Lock = 1
    Remote = 2


class BackendStats(Enum):
    CLOSED = "closed"
    CONNECTED = "connected"
    CONNECTING = "connecting"
    ABNORMAL = "abnormal"


class RemoteCommandCode(Enum):
    UP = "W"
    LEFT = "A"
    DOWN = "S"
    RIGHT = "D"

    @classmethod
    def has_value(cls, value) -> bool:
        return value in cls._value2member_map_


class InternalConst(Enum):
    DATA_QUEUE_MAX = 300
    DATA_DUMP_TIMEOUT = 15
    VIDEO_CLOCK_RATE = 9000
    AUDIO_CLOCK_RATE = 16000


class ServiceConst(Enum):
    SocketDefaultPort = 5540
    SocketTimeout = 5
    SocketMsgMax = 500 * 1024 * 1024

    APICallTryTimes = 3
    APICallTryHold = 15


class ServiceStatusCode(Enum):
    Normal = 0

    InternalServerError = 20000
    PermissionAuthError = 21001
    AuthTokenNotFound = 21002


class ServiceState(Enum):
    STOPPED = 0
    RUNNING = 1
    PAUSE = 2
    WARMUP = 3
    ERROR = -1


class PgmItem(Enum):
    UNKNOWN = -1
    FREE = 0
    OBSTACLE = 100


class PgmColor(Enum):
    UNKNOWN = [255, 255, 255]
    FREE = [24, 39, 52]
    OBSTACLE = [0, 255, 225]
    ROBOT = [255, 0, 128]
    LASER = [0, 255, 0]
    TEXT = [0, 0, 0]
    WAYPOINT = [128, 255, 0]
    MARKER = [200, 0, 200]


class MsgChannelItem(Enum):
    CONNECT_INTERVAL = 5
    GET_MESSAGE_TIMEOUT = 10


class ActionStatus(Enum):
    PENDING = 0
    ACTIVE = 1
    PREEMPTED = 2
    SUCCEEDED = 3
    ABORTED = 4
    REJECTED = 5
    PREEMPTING = 6
    RECALLING = 7
    RECALLED = 8
    LOST = 9
    UNKONWN = 99


class GaitType(Enum):
    LIEON = 0
    STAND = 1
    HOLD = 2
    TROT = 3
    FALL = 10
    UPSTAIR = 11
    UNKONWN = 99


class Motion(Enum):
    StepVel = .25
    ForceTimes = 10


DateTimeFormat = "%y%m%d%H:%M"
