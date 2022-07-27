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
from typing import ByteString
from typing import Union

import numpy as np
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.constant import ServiceState
from robosdk.common.fileops import FileOps
from robosdk.common.schema.stream import ImageStream
from robosdk.utils.lazy_imports import LazyImport

from .base import MonitorServer

__all__ = ("FileCameraServer", )


@ClassFactory.register(ClassType.CLOUD_ROBOTICS_ALG, "file_camera_server")
class FileCameraServer(MonitorServer):  # noqa
    """
    Serves video streams to clients in RTSP protocol by wrapping `GStreamer`
    """

    def __init__(self, logger=None, fourcc: str = "MJPG", **kwargs):
        super(FileCameraServer, self).__init__(logger=logger)
        self.cv2 = LazyImport("cv2")
        self._fourcc = self.cv2.VideoWriter_fourcc(*fourcc)
        self._video_dir = kwargs.get("video_save_url", "") or "/tmp"

    def add(self, stream: str, **kwargs):
        """
        Registers a new video stream to the server.
        """
        self.logger.info(f'Adding {stream} to mount {self._video_dir}')

        w = int(kwargs.get("width", "640"))
        h = int(kwargs.get("height", "480"))
        fps = int(kwargs.get("fps", "30"))

        tmp_dir = tempfile.mkdtemp()
        video_out = os.path.join(tmp_dir, f"{stream}.avi")
        process = self.cv2.VideoWriter(
            video_out, self.fourcc, fps, (w, h)
        )

        self.streams[stream] = ImageStream(
            fps=fps, width=w, height=h,
            bind_uri=video_out, process=process
        )

        self.state[stream] = ServiceState.PAUSE

    def remove(self, stream: str, **kwargs):
        if stream not in self.streams:
            self.logger.warning(f"{stream} not registered")
            return
        self._close_stream(stream)
        del self.streams[stream]

    def start(self):
        for stream in self.streams.keys():
            self.logger.info(f'Starting RTSPServer for {stream}')
            self._start_streaming(stream)
        self.should_exit = False

    def stop(self):
        self.should_exit = True
        for stream in self.streams.keys():
            self.logger.info(f'Stopping RTSPServer for {stream}')
            self.remove(stream)

    def streaming(self, stream: str, frame: Union[ByteString, np.ndarray],
                  **parameters):
        self.logger.debug(f"send data to channel {stream} from server")

        cls = self.streams[stream]
        if isinstance(frame, np.ndarray):
            frame = np.array(frame)
        else:
            w = (int(parameters["width"]) if "width" in parameters
                 else cls.width)
            h = (int(parameters["height"]) if "height" in parameters
                 else cls.height)
            frame = np.frombuffer(frame, np.uint8)
            try:
                frame = frame.reshape(h, w, -1)
            except ValueError:
                frame = self.cv2.imdecode(frame, self.cv2.IMREAD_COLOR)
        resized = self.cv2.resize(frame, (cls.width, cls.height),
                                  interpolation=self.cv2.INTER_LINEAR)
        if not cls.process or not cls.process.isOpened():
            self.logger.warning(
                f'Tried to write to `{stream}` but it is not opened'
            )
            return False
        cls.process.write(resized)
        return True

    def _start_streaming(self, stream: str):
        if stream not in self.streams:
            self.logger.warning(f"{stream} not registered")
            return

        state = self.state[stream]
        if state in [
            ServiceState.WARMUP,
            ServiceState.ERROR,
            ServiceState.RUNNING
        ]:
            self._close_stream(stream)

        cls = self.streams[stream]
        if not cls.process.isOpened():
            self.logger.warning('Could not open cv2.VideoWriter')
            self.state[stream] = ServiceState.ERROR
            return False
        state = ServiceState.RUNNING
        self.state[stream] = state

    def _close_stream(self, stream: str):
        if stream not in self.streams:
            self.logger.warning(f"{stream} not registered")
            return

        cls = self.streams[stream]
        if cls.process:
            cls.process.release()
            cls.process = None
        _base_uri = cls.bind_uri
        if os.path.isfile(_base_uri):
            _uri = os.path.join(self._video_dir, os.path.basename(_base_uri))
            _uri = FileOps.upload(_base_uri, _uri, clean=True)
            os.unlink(os.path.dirname(_base_uri))
            self.streams[stream].bind_uri = _uri
        self.state[stream] = ServiceState.STOPPED

    def __repr__(self) -> str:
        return f'< FileCameraServer streams=[{", ".join(self.urls())}] >'
