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

import asyncio
import fractions
import json
import os
from signal import SIGINT
from signal import SIGTERM
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

import numpy as np
import socketio
from aiortc import RTCConfiguration
from aiortc import RTCDataChannel
from aiortc import RTCIceServer
from aiortc import RTCPeerConnection
from aiortc import RTCSessionDescription
from aiortc.mediastreams import MediaStreamTrack
from aiortc.mediastreams import VideoStreamTrack
from aiortc.sdp import candidate_from_sdp
from av import AudioFrame
from av import VideoFrame  # noqa
from robosdk.cloud_robotics.edge_base import ClientBase
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.config import BaseConfig
from robosdk.common.constant import InternalConst
from robosdk.common.constant import RoboControlMode
from robosdk.common.constant import ServiceConst
from robosdk.common.logger import logging
from robosdk.utils.queue import BaseQueue


class CameraStreamTrack(VideoStreamTrack):
    kind = "video"

    def __init__(self, name: str,
                 listen_track: MediaStreamTrack = None,
                 frame_rate: int = 30,
                 frames_queue_size: int = 20):
        super().__init__()
        self.logger = logging.bind(
            instance=f"{name}.{self.kind}_track",
            system=True
        )
        self.listen_track = listen_track
        self._frames_queue = BaseQueue(
            queue_maxsize=frames_queue_size,
            keep_when_full=True
        )
        self._timestamp: int = 0
        ptime = 1 / frame_rate
        if self.kind == "video":
            tb = InternalConst.VIDEO_CLOCK_RATE.value
        else:
            tb = InternalConst.AUDIO_CLOCK_RATE.value
        self._time_base = fractions.Fraction(1, tb)
        self._present_clock = int(ptime * tb)
        self._wait_time = (1 / frame_rate) / 1000

    def add(self, frames: List):
        if self.readyState != 'live':
            return False
        if not len(frames):
            return False
        for f in frames:
            f.time_base = self._time_base
            f.pts = self._timestamp
            try:
                self._frames_queue.put(f)
            except Exception as err:
                self.logger.debug(f'Failed to add {self.kind} frame: {err}')

            finally:
                self._timestamp += self._present_clock
        return True

    async def recv(self):
        if self.listen_track:
            return await self.listen_track.recv()
        frame = None  # noqa
        while 1:
            while self._frames_queue.empty():
                await asyncio.sleep(self._wait_time)

            try:
                frame = self._frames_queue.get()
            except Exception as err:
                self.logger.debug(f'Failed to get {self.kind} frame: {err}')
            else:
                break
        return frame


class AudioStreamsTrack(CameraStreamTrack):
    kind = "audio"

    def __init__(self, name: str,
                 listen_track: MediaStreamTrack = None, ):
        super().__init__(name=name,
                         frame_rate=InternalConst.AUDIO_CLOCK_RATE.value,
                         listen_track=listen_track)


class RoboRTCPeerConnection:
    def __init__(self, logger, name: str = ""):
        self.logger = logger
        self._basename = name
        if (
                BaseConfig.ICE_SERVER_URLS and
                os.path.isfile(BaseConfig.ICE_SERVER_URLS)
        ):
            try:
                with open(BaseConfig.ICE_SERVER_URLS) as fin:
                    z = [RTCIceServer(json.load(fin))]
            except:  # noqa
                z = None
            self.pc = RTCPeerConnection(
                RTCConfiguration(z)
            )
        else:
            self.pc = RTCPeerConnection()
        self.on("connectionstatechange", self.connectionstatechange)
        self.on("datachannel", self.connectiondatachannel)
        self.on("iceconnectionstatechange", self.iceconnectionstatechange)
        self.on("track", self.ontrack)
        self.channels: Dict[str, Union[MediaStreamTrack, RTCDataChannel]] = {}

    def on(self, event: str, callback: Optional = None):
        self.logger.debug(f"RTC add event registered: {event}")
        self.pc.on(event, callback)
        return True

    @property
    def state(self):
        return getattr(self.pc, "iceConnectionState", "")

    def listen(self, channel: str, event: str, callback: Optional = None):
        if channel not in self.channels:
            return False
        self.logger.debug(f"RTC add event registered to {channel}: {event}")
        self.channels[channel].on(event, callback)
        return True

    def add_track(self, name: str, track: MediaStreamTrack) -> MediaStreamTrack:
        self.logger.debug(f"[Event: addTrack] {name}")
        if name in self.channels:
            return self.channels[name]
        self.pc.addTrack(track)
        self.channels[name] = track
        return track

    def add_stream(
            self, name: str,
            video_enable: bool = True,
            audio_enable: bool = False
    ) -> List[MediaStreamTrack]:
        self.logger.debug("[Event: addStream]")
        streams = []
        if video_enable:
            video = self.add_track(f"{name}.video", CameraStreamTrack(name))
            streams.append(video)
        if audio_enable:
            audio = self.add_track(f"{name}.audio", AudioStreamsTrack(name))
            streams.append(audio)
        return streams

    def add_data_channel(self, name: str) -> RTCDataChannel:
        self.logger.debug("[Event: addDataChannel]")
        if name in self.channels:
            return self.channels[name]
        dc = self.pc.createDataChannel(name)
        self.channels[name] = dc
        return dc

    async def create_offer(self) -> Dict:
        self.logger.debug('[Event: setLocalDescription]')
        session_description = await self.pc.createOffer()
        await self.pc.setLocalDescription(session_description)
        return {
            "sdp": self.pc.localDescription.sdp,
            "type": self.pc.localDescription.type
        }

    async def set_remote_sdp(self, sdp, kind="answer"):
        self.logger.debug(f'[Event: setRemoteDescription] {kind}')
        await self.pc.setRemoteDescription(
            RTCSessionDescription(sdp=sdp, type=kind))
        if kind == "offer":
            answer = await self.pc.createAnswer()
            await self.pc.setLocalDescription(answer)
            return {
                "sdp": self.pc.localDescription.sdp,
                "type": self.pc.localDescription.type
            }
        return

    async def add_ice_candidate(self, sdp: str):
        self.logger.debug("[Event: loadIceCandidate]")
        json_msg = json.loads(sdp)
        candidate = candidate_from_sdp(json_msg["candidate"])
        candidate.sdpMid = json_msg["sdpMid"]
        candidate.sdpMLineIndex = json_msg["sdpMLineIndex"]
        await self.pc.addIceCandidate(candidate)

    async def connectiondatachannel(self, datachannel):
        self.logger.debug(f"Connection datachannel {datachannel}")
        # datachannel.on_message(self._test_data)

    async def iceconnectionstatechange(self):
        self.logger.debug("[Event: iceconnectionstatechange]")
        # if self.pc.iceConnectionState == "failed":
        #     await self.close()

    async def connectionstatechange(self):
        self.logger.debug(
            "[Event: connectionstatechange] "
            f"Connection state is {self.pc.connectionState}")
        if self.pc.connectionState == "closed":
            await self.close()
        if self.pc.connectionState == "connected":
            pass

    async def ontrack(self, track: MediaStreamTrack):
        if self._basename:
            name = f"{self._basename}.{track.kind}"
        else:
            name = str(track.id)
        self.logger.debug(
            f"[Event: Received track : {name}] "
            f"Connection state is {self.pc.connectionState}")

        if track.kind == "video":
            self.add_track(name, CameraStreamTrack(
                name=name, listen_track=track))
        elif track.kind == "audio":
            self.add_track(name, AudioStreamsTrack(
                name=name, listen_track=track))

    async def close(self):
        self.logger.warning('[Event: Closing peer connection]')
        try:
            await self.pc.close()
        except:  # noqa
            pass


class SignalingClient:

    def __init__(self, robot, name_space: str = "", data_func: Callable = None):
        self.instance = f"{robot.robot_name}.{name_space}"
        self._room_name = name_space
        self.logger = logging.bind(
            instance=f"{self.instance}RTCPeerConnection",
            system=True
        )
        self._sio = socketio.AsyncClient()
        self.robot = robot
        self._channels: Dict = {}
        self._data_func = data_func

    @property
    def sid(self):
        return getattr(self._sio, "sid", None)

    def __str__(self):
        return self.instance

    async def async_run(self, socket_url: str = "http://127.0.0.1:5540/ws"):
        setattr(self.robot, "control_mode", RoboControlMode.Remote)
        self._sio.event(self.connect)
        self._sio.event(self.disconnect)
        self._sio.event(self.close)
        self._sio.on("room-clients", self.on_room_clients)
        self._sio.on("make-peer-call", self.on_peer_call)
        self._sio.on("peer-call-received", self.on_peer_call_received)
        self._sio.on("peer-call-answer-received", self.on_peer_call_answer)
        self._sio.on("ice-candidate-received", self.on_ice_candidate)
        while 1:
            try:
                await self._sio.connect(
                    socket_url,
                    wait_timeout=ServiceConst.SocketTimeout.value
                )
            except Exception as err:
                self.logger.error(f"Socket connect Err: {err}")
            else:
                break
        self.logger.debug(f"Socket connect : {self.sid} - {self._room_name}")
        await self._sio.wait()

    async def connect(self):
        self.logger.debug("connection established")
        await self._sio.emit("join-room", {
            "name": self.instance, "room": self._room_name
        })

    async def disconnect(self):
        self.logger.debug("disconnect established")
        await self.close()

    async def close(self):
        self.logger.debug("close")
        await self._sio.disconnect()
        await asyncio.sleep(.1)
        await self._sio.reconnection()

    async def on_room_clients(self, clients):
        self.logger.debug(f"onRoomClientsEvent {clients}")
        if len(clients) > 1:
            await self._sio.emit("call-all")

    async def on_peer_call(self, ids: List):
        tasks = []
        for u in set(ids):
            if u == self._sio.sid:
                continue
            if u in self._channels:
                continue
            tasks.append(self.make_peer_call(u))
        if len(tasks):
            await asyncio.wait(tasks)

    async def on_peer_call_answer(self, data):
        from_id = data.get("fromId", "")
        answer = data.get("answer", {})
        _type = answer.get("type", "")
        if not (from_id and _type == "answer" and "sdp" in answer):
            self.logger.error(f"Invalid onPeerCallAnswerReceivedEvent: {data}")
            await self._remove_connection(from_id)
            return
        self.logger.debug(f"peer-call-answer-received, {answer}")
        await self.receive_peer_call_answer(from_id, answer["sdp"])

    async def receive_peer_call_answer(self, _id: str, sdp: str):
        if _id not in self._channels:
            self.logger.debug(
                f"receivePeerCallAnswer failed because {_id} is not found.")
            return
        await self._channels[_id].set_remote_sdp(sdp=sdp, kind="answer")

    async def _remove_connection(self, from_id):
        if from_id not in self._channels:
            return
        await self._channels[from_id].close()
        del self._channels[from_id]

    async def on_peer_call_received(self, data: Dict):
        from_id = data.get("fromId", "")
        offer: Dict = data.get("offer", {})
        _type = offer.get("type", "")
        if not (from_id and "sdp" in offer and _type == "offer"):
            self.logger.error(f"Invalid onPeerCallReceivedEvent: {data}")
            return
        await self.peer_call_received(from_id, offer["sdp"])

    async def make_peer_call(self, _id):
        self.logger.debug(f"makePeerCall (form {self.sid} to_id={_id})")
        if _id in self._channels:
            self.logger.debug(
                f"makePeerCall failed because {_id} is already connected.")
            return
        self.create_connection(_id)
        # text = {"toId": _id}
        num = len(self._channels[_id].channels)
        if num:
            self.logger.debug(f"makePeerCall create offer: {num}")
            offer = await self._channels[_id].create_offer()
            text = {"toId": _id, "type": "offer", "offer": offer}

            await self._sio.emit('call-peer', text)

    async def peer_call_received(self, _id: str, sdp: str):
        self.logger.debug(f"peer_call_received (from_id={_id})")
        if _id in self._channels:
            self.logger.warning(
                f"receivePeerCall failed because {_id} is already connected.")
            return
        self.create_connection(_id)

        answer = await self._channels[_id].set_remote_sdp(sdp, "offer")
        udata = {"toId": _id}
        if answer:
            udata["answer"] = answer
        await self._sio.emit("make-peer-call-answer", udata)

    def create_connection(self, from_id):
        raise NotImplementedError

    async def on_ice_candidate(self, data):
        from_id = data.get("fromId", "")
        candidate = data.get("candidate") or {}
        if not (from_id in self._channels and "candidate" in candidate):
            self.logger.error(f"Invalid onIceCandidateReceivedEvent: {data}")
            return
        self.logger.debug(f"ice-candidate-received, {data}")

        await self._channels[from_id].add_ice_candidate(
            json.dumps(candidate)
        )


class ThreadStreamClientManage(SignalingClient):

    def __init__(self, robot,
                 name_space: str = "",
                 data_func: Optional[Callable] = None,
                 kind: str = "stream",
                 video_enable: bool = True,
                 audio_enable: bool = False):
        SignalingClient.__init__(self,
                                 robot=robot,
                                 data_func=data_func,
                                 name_space=name_space)
        self.audio_enable = audio_enable
        self.video_enable = video_enable
        self._kind = kind

    def create_connection(self, from_id):
        pc = RoboRTCPeerConnection(logger=self.logger, name=self._room_name)
        if self._kind == "stream":
            track: List[MediaStreamTrack] = pc.add_stream(
                name=self._room_name,
                video_enable=self.video_enable,
                audio_enable=self.audio_enable)

            for u in track:
                @u.on("ended")
                def _end_track():
                    self.logger.debug(f"Track: {u.kind} ended")

        async def pc_connectionstatechange():
            await pc.connectionstatechange()
            if self._data_func:
                while pc.pc.connectionState == "connected":
                    if self._kind == "stream":
                        sample: List = self._data_func()
                        video, audio = sample[:2]
                        if video is not None:
                            self.send_frame(video, self._room_name)
                        if audio is not None:
                            self.send_frame(
                                audio, self._room_name,
                                formats="s16", kind="audio"
                            )
                    else:
                        video, audio = [], []
                        if self.video_enable:
                            video = await self.recv_frame(self._room_name)
                        if self.audio_enable:
                            audio = await self.recv_frame(self._room_name,
                                                          kind="audio")
                        self._data_func(video, audio)
                    await asyncio.sleep(.1)

        pc.on("connectionstatechange", pc_connectionstatechange)

        self._channels[from_id] = pc

    async def recv_frame(self,
                         room_name: str,
                         from_id: str = "",
                         kind: str = "video"):
        room_name = f"{room_name}.{kind}"
        if from_id not in self._channels:
            channels: List[CameraStreamTrack] = [
                c.channels[room_name] for c in self._channels.values()
                if room_name in c.channels
            ]
        elif room_name in self._channels[from_id].channels:
            channels: List[CameraStreamTrack] = [
                self._channels[from_id].channels[room_name]
            ]
        else:
            return []
        frames = []
        for c in channels:
            if c.kind != kind:
                continue
            frame = await c.recv()
            if frame is not None:
                frames.append(frame.to_ndarray())
        return frames

    def send_frame(self,
                   frame: np.ndarray,
                   room_name: str,
                   to_id: str = "",
                   formats: str = "bgr24",
                   kind: str = "video"):
        room_name = f"{room_name}.{kind}"
        if to_id not in self._channels:
            channels: List[CameraStreamTrack] = [
                c.channels[room_name] for c in self._channels.values()
                if room_name in c.channels
            ]
        elif room_name in self._channels[to_id].channels:
            channels: List[CameraStreamTrack] = [
                self._channels[to_id].channels[room_name]
            ]
        else:
            return
        if kind == "video" and self.video_enable:
            frame = VideoFrame.from_ndarray(frame, format=formats)
        elif kind == "audio" and self.audio_enable:
            frame = AudioFrame.from_ndarray(
                frame.reshape((1, -1)),
                format=formats, layout='mono')  # noqa
        else:
            return
        for c in channels:
            if c.kind != kind:
                continue
            rsl = c.add([frame])
            if not rsl:
                self.logger.warning(f"failure to send [{kind}] frame")


class ThreadDatachannelClientManage(SignalingClient):

    def __init__(self, robot,
                 name_space: str = "",
                 data_func: Optional[Callable] = None,
                 message_callback: Optional[Callable] = None):
        SignalingClient.__init__(self,
                                 robot=robot,
                                 name_space=name_space,
                                 data_func=data_func
                                 )
        self._callback = message_callback
        self._ready_send = False

    def create_connection(self, from_id):
        self._channels[from_id] = RoboRTCPeerConnection(
            logger=self.logger, name=self._room_name)
        dc: RTCDataChannel = self._channels[from_id].add_data_channel(
            self._room_name
        )

        self._channels[from_id].on("ondatachannel", self.ondatachannel)

        async def send_pings():
            if not self._data_func:
                return
            while True:
                status_dict: List[Dict] = self._data_func()
                for s in status_dict:
                    dc.send(json.dumps(s))
                await asyncio.sleep(.1)

        @dc.on("open")
        def _send_data():
            self._ready_send = True
            asyncio.ensure_future(send_pings())

        @dc.on("closed")
        def _close_data():
            self._ready_send = False

        @dc.on("message")
        def _get_data(data):
            self.logger.info(f"{dc.label} Recieved from client: {data}")
            msg = json.loads(data)
            if self._callback:
                self._callback(msg)

    async def ondatachannel(self, channel: RTCDataChannel):
        self.logger.debug(f"[Event: Received channel {channel.id}]")

        @channel.on("message")
        def on_message(data):
            self.logger.info(f"{channel.label} Recieved from client: {data}")
            msg = json.loads(data)
            if self._callback:
                self._callback(msg)


@ClassFactory.register(ClassType.CLOUD_ROBOTICS, "webrtc_control_robot")
class ControlRTCRobot(ClientBase):  # noqa
    def __init__(self, robot, name: str = "control", **kwargs, ):
        super(ControlRTCRobot, self).__init__(name=name, **kwargs)
        is_ssl = kwargs.get("ssl", "")
        if not self.uri.startswith("http"):
            self.uri = f"https://{self.uri}" if is_ssl else f"http://{self.uri}"
        self.robot = robot
        self._workers: Dict[str, SignalingClient] = {}
        self.loop = asyncio.get_event_loop()

    def connect(self, **kwargs):
        pass

    def close(self):
        workers = []
        for n, w in self._workers.items():
            self.logger.warning(f"closing worker {n}")
            main_task = asyncio.ensure_future(
                w.disconnect(), loop=self.loop
            )
            workers.append(main_task)
        self.loop.run_forever()

    def add_worker(self,
                   name_space: str = "",
                   data_func: Callable = None,
                   **kwargs):

        kind = kwargs.get("kind", "datachannel")
        if kind in ("stream", "remote"):
            audio_enable = True if kwargs.get("audio_enable", "") else False
            stream = ThreadStreamClientManage(
                robot=self.robot,
                name_space=name_space,
                kind=kind,
                audio_enable=audio_enable,
                data_func=data_func
            )
        else:
            message_callback: Callable = kwargs.get("message_callback", None)
            stream = ThreadDatachannelClientManage(
                robot=self.robot,
                name_space=name_space,
                data_func=data_func,
                message_callback=message_callback
            )
        self._workers[name_space] = stream

    def run(self):

        workers = []
        for n, w in self._workers.items():
            main_task = asyncio.ensure_future(
                w.async_run(self.uri), loop=self.loop
            )
            for signal in [SIGINT, SIGTERM]:
                self.loop.add_signal_handler(signal, main_task.cancel)
            workers.append(main_task)

        self.loop.run_forever()
