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
from typing import ByteString
from typing import Union

import numpy as np
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.constant import ServiceState
from robosdk.common.schema.stream import ImageStream
from robosdk.utils.lazy_imports import LazyImport
from robosdk.utils.queue import BaseQueue
from robosdk.utils.util import parse_kwargs

from .base import MonitorServer

__all__ = ("RTSPCameraServer", )


try:
    import gi  # noqa

    gi.require_version('Gst', '1.0')
    gi.require_version('GstRtspServer', '1.0')
    from gi.repository import GLib  # noqa
    from gi.repository import Gst
    from gi.repository import GstRtspServer
except ImportError:
    pass  # avoid error when `ClassFactory` loading
else:
    class _RTSPFactory(GstRtspServer.RTSPMediaFactory):
        def __init__(self,
                     logger,
                     fps: int = 30,
                     width: int = 640,
                     height: int = 480,
                     **properties):
            super(_RTSPFactory, self).__init__(**properties)
            self.number_frames = 0
            self.curr_frame = None
            self.logger = logger
            self.fps = fps
            self.width = width
            self.height = height
            self.duration = 1 / self.fps * Gst.SECOND
            self.pipeline = "".join(
                ['appsrc name=source is-live=true block=true ',
                 'format=GST_FORMAT_TIME caps=video/x-raw,',
                 f'format=BGR,width={width},height={height},',
                 f'framerate={fps}/1 ! videoconvert ! video/x-raw,format=I420',
                 ' ! x264enc speed-preset=ultrafast tune=zerolatency ! ',
                 'rtph264pay config-interval=1 name=pay0 pt=96']
            )

        def write(self, frame: ByteString):
            self.curr_frame = frame

        def release(self):
            self.curr_frame = None

        def on_need_data(self, src, length):  # noqa
            if self.curr_frame is None:
                return

            data = self.curr_frame.tostring()
            buf = Gst.Buffer.new_allocate(None, len(data), None)
            buf.fill(0, data)
            buf.duration = self.duration
            timestamp = self.number_frames * self.duration
            buf.pts = buf.dts = int(timestamp)
            buf.offset = timestamp
            self.number_frames += 1
            retval = src.emit('push-buffer', buf)
            self.logger.debug(
                'frame push, frame {}, duration {} ns, durations {} s'.format(
                    self.number_frames,
                    self.duration,
                    self.duration / Gst.SECOND))
            if retval != Gst.FlowReturn.OK:
                self.logger.warning(f" Gstream flow warning: {retval}")

        def do_create_element(self, url):  # noqa
            return Gst.parse_launch(self.pipeline)

        def do_configure(self, rtsp_media):
            self.number_frames = 0
            appsrc = rtsp_media.get_element().get_child_by_name('source')
            appsrc.connect('need-data', self.on_need_data)


class _ThreadImageDataManage(threading.Thread):

    def __init__(self, streamer: Any, width: int, height: int):
        super(_ThreadImageDataManage, self).__init__()
        self.cv2 = LazyImport("cv2")
        self.queue = BaseQueue(keep_when_full=True)
        self._curr = np.random.rand(width, height, 3) * 255
        self.width = width
        self.height = height
        self.streamer = streamer

    @property
    def frame(self):
        return self._curr

    def run(self):
        while 1:
            frame = self.queue.get()
            if frame is None:
                frame = self.frame
            self.streamer.write(frame)

    def write(self, data: Union[ByteString, np.ndarray],
              width: int = None, height: int = None):
        if data is None:
            return
        if isinstance(data, np.ndarray):
            frame = np.array(data)
        else:
            w = int(width) if width else self.width
            h = int(height) if height else self.height
            frame = np.frombuffer(data)
            try:
                frame = frame.reshape(h, w, -1)
            except ValueError:
                frame = self.cv2.imdecode(frame, self.cv2.IMREAD_COLOR)
        frame = self.cv2.resize(
            frame, (self.width, self.height),
            interpolation=self.cv2.INTER_LINEAR
        )
        self.queue.put(frame)
        self._curr = frame

    def release(self):
        if self.streamer and hasattr(self.streamer, "release"):
            self.streamer.release()
        self.join(timeout=20)


@ClassFactory.register(ClassType.CLOUD_ROBOTICS_ALG, alias="rtsp_camera_server")
class RTSPCameraServer(MonitorServer):  # noqa
    """
    Serves video streams to clients in RTSP protocol by wrapping `GStreamer`
    """

    def __init__(self, logger=None, **kwargs,):
        super(RTSPCameraServer, self).__init__(logger=logger)

        host = kwargs.get("host", "") or "0.0.0.0"
        port = str(kwargs.get("port", "")) or "5000"
        self.gst_server = GstRtspServer.RTSPServer()
        self.gst_server.set_address(host)
        self.gst_server.set_service(port)
        self.gst_server.connect("client-connected", self.on_server_connect)
        self._port = int(port)
        self._host = host
        self._loop = GLib.MainLoop()
        Gst.init(None)

    def on_server_connect(self, arg1, client):  # noqa
        ip = client.get_connection().get_ip()
        self.logger.info(f"RTSP subscribe from {ip}")
        client.connect('closed', self.on_server_disconnect)

    def on_server_disconnect(self, client):
        ip = client.get_connection().get_ip()
        self.logger.info(f"RTSP disconnected with {ip}")

    def add(self, stream: str, **kwargs):
        """
        Registers a new video stream to the server.
        """
        self.logger.info(f'Adding pipeline to mount point "{stream}"')

        w = int(kwargs.get("width", "640"))
        h = int(kwargs.get("height", "480"))
        fps = int(kwargs.get("fps", "30"))
        factory = _RTSPFactory(
            logger=self.logger, width=w, height=h, fps=fps
        )

        factory.set_shared(True)
        self.gst_server.get_mount_points().add_factory(f"/{stream}", factory)
        uri = f'rtsp://{self._host}:{self._port}/{stream}'
        self.streams[stream] = ImageStream(
            fps=fps, width=w, height=h,
            bind_uri=uri, process=factory
        )

        self.state[stream] = ServiceState.PAUSE

    def remove(self, stream: str, **kwargs):
        if stream not in self.streams:
            self.logger.warning(f"{stream} not registered")
            return
        mounts = self.gst_server.get_mount_points()
        mounts.remove_factory(stream)
        self._close_stream(stream)
        del self.streams[stream]

    def start(self):
        for stream in self.streams.keys():
            self.logger.info(f'Starting RTSPServer for {stream}')
            self._start_streaming(stream)
        self.gst_server.attach()
        self.should_exit = False
        _t = threading.Thread(
            name="RTSPServerThread",
            target=self._loop.run,
        )
        _t.start()

    def stop(self):
        super(RTSPCameraServer, self).stop()
        self._loop.quit()

    def _check_stream_process(self, stream: str):
        if stream not in self.streams:
            return False
        cls = self.streams[stream]

        if not (cls.process and hasattr(cls.process, 'write')):
            return False
        return True

    def streaming(self, stream: str, frame: Union[ByteString, np.ndarray],
                  **parameters):
        self.logger.debug(f"send data to channel {stream} from server")
        if not self._check_stream_process(stream):
            self.logger.warning(
                f'Tried to write to `{stream}` but it is not opened'
            )
        vark = parse_kwargs(self.streams[stream].process.write, **parameters)
        self.streams[stream].process.write(frame, **vark)
        return True

    def _start_streaming(self, stream: str):

        state = self.state[stream]
        if state in [
            ServiceState.WARMUP,
            ServiceState.ERROR,
            ServiceState.RUNNING
        ]:
            self._close_stream(stream)

        if not self._check_stream_process(stream):
            self.logger.warning('Could not open RTSP VideoWriter')
            self.state[stream] = ServiceState.ERROR
            return False

        cls = self.streams[stream]
        self.streams[stream].process = _ThreadImageDataManage(
            streamer=cls.process, width=cls.width, height=cls.height
        )
        self.streams[stream].process.setDaemon(True)
        state = ServiceState.RUNNING
        self.state[stream] = state
        self.streams[stream].process.start()

    def _close_stream(self, stream: str):
        if stream not in self.streams:
            self.logger.warning(f"{stream} not registered")
            return

        cls = self.streams[stream]
        if cls.process and hasattr(cls.process, "release"):
            cls.process.release()
            cls.process = None
        self.state[stream] = ServiceState.STOPPED

    def __repr__(self) -> str:
        return f'< RTSPServer streams=[{", ".join(self.urls())}] >'
