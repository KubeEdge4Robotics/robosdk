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

import abc
import asyncio
import inspect
from contextvars import ContextVar
from typing import Dict
from typing import Optional
from typing import Type

from pyee.asyncio import AsyncIOEventEmitter
from robosdk.common.class_factory import ClassFactory
from robosdk.common.class_factory import ClassType
from robosdk.common.exceptions import ComponentError
from robosdk.common.exceptions import RequiredParameterException
from robosdk.common.logger import logging
from robosdk.utils.util import singleton

_handler_context: ContextVar[Optional, "EventHandler"] = ContextVar(
    "_handler_context",
    default=None,
)


class EventBusBase(abc.ABC, AsyncIOEventEmitter):
    def __init__(self, event_name: str = None):
        super().__init__()
        self.event_name = event_name
        self.logger = logging.bind(
            instance=f"{self.event_name}Event", system=True
        )

    @abc.abstractmethod
    def close(self):
        ...

    @abc.abstractmethod
    async def run(self, parameter: Dict = None):
        ...


class EventHandlerValidator:
    EVENT_PARAMETER_COUNT = 2

    async def validate(
            self, event: Type[EventBusBase], parameter: Dict = None,
    ) -> None:
        if not issubclass(event, EventBusBase):
            raise ComponentError("Event must inherit BaseEvent")

        if parameter and not isinstance(parameter, Dict):
            raise ComponentError()

        signature = inspect.signature(event.run)
        func_parameters = signature.parameters
        if len(func_parameters) != self.EVENT_PARAMETER_COUNT:
            raise ComponentError()

        base_parameter = func_parameters.get("parameter")
        if base_parameter.default is not None and not parameter:
            raise RequiredParameterException(
                cls_name=base_parameter.__class__.__name__,
            )


class EventHandler:
    def __init__(self, validator: EventHandlerValidator):
        self.events: Dict[Type[EventBusBase], Dict] = {}
        self.validator = validator

    async def register(self, event: Type[EventBusBase], parameter: Dict = None):
        await self.validator.validate(event=event, parameter=parameter)
        self.events[event] = parameter

    async def _publish(self, run_at_once: bool = True) -> None:
        await self._run_at_once()
        if run_at_once:
            self.events.clear()

    async def _run_at_once(self) -> None:
        futures = []
        event: Type[EventBusBase]
        for event, parameter in self.events.items():
            task = asyncio.create_task(event().run(parameter=parameter))
            futures.append(task)

        await asyncio.gather(*futures)


@singleton
class EventManager:
    _event = {}
    logger = logging.bind(instance="EventManager", system=True)

    def register(self, event_tag: str, event: AsyncIOEventEmitter = None):
        if event is None:
            event = ClassFactory.get_cls(
                ClassType.EVENT, event_tag
            )()
        if not isinstance(event, AsyncIOEventEmitter):
            raise TypeError(
                f"event {event_tag} is not a AsyncIOEventEmitter"
            )
        self._event[event_tag] = event

    def emit(self, event_name: str, **kwargs):
        if kwargs.get("event_tag"):
            _event_tag = kwargs.pop("event_tag")
            if _event_tag in self._event:
                try:
                    self._event[_event_tag].emit(event_name, **kwargs)
                except Exception as e:
                    self.logger.error(
                        f"emit event {event_name} - {_event_tag} error: {e}"
                    )
        else:
            for _event_tag, event in self._event.items():
                try:
                    event.emit(event_name, **kwargs)
                except Exception as e:
                    self.logger.error(
                        f"emit event {event_name} - {_event_tag} error: {e}"
                    )
