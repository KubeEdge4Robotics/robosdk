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
from datetime import datetime
from datetime import timedelta
from typing import List

import aiohttp
from robosdk.common.config import BaseConfig
from robosdk.common.constant import RoboArtisan
from robosdk.common.constant import RoboArtisanCloudAPI
from robosdk.common.exceptions import CloudError
from robosdk.common.logger import logging


class CloudAPIProxy:
    _ENDPOINT_NAME = "IAM_ENDPOINT"
    _DOMAIN_NAME = "IAM_DOMAIN"
    __timeout__ = 10
    __update_token_period__ = 60

    def __init__(
            self,
            service_name: RoboArtisan,
            token: str = "",
            project_id: str = "",
            region: str = "default",
            resource: str = "HuaweiCloud",
    ):
        self.logger = logging.bind(
            instance=f"roboartisan_{service_name.name}", system=True
        )
        self.config = BaseConfig
        self.cloud = RoboArtisanCloudAPI[resource]

        self.service_name = service_name
        self._token = token.strip()
        self._project_id = project_id.strip()
        self.__session__ = aiohttp.ClientSession(
            headers={"Content-Type": "application/json"},
            timeout=aiohttp.ClientTimeout(total=self.__timeout__),
            connector=aiohttp.TCPConnector(verify_ssl=False),
        )
        self._region = region.strip()
        self._should_exit = False

    async def run(self):
        raise NotImplementedError

    def update_token(self, token: str = "", project_id: str = ""):
        raise NotImplementedError

    async def close(self):
        await self.__session__.close()
        self._should_exit = True

    @property
    def server_uri(self) -> str:
        server_uri = self.cloud.get(self.service_name, "").strip()
        region = self.config.get(self._DOMAIN_NAME, self._region).strip()
        if not server_uri:
            server_uri = self.config.get(self._ENDPOINT_NAME, "").strip()

        return server_uri.format(region=region, project_id=self._project_id)

    def __str__(self):
        return self.service_name.value


class CloudAuthProxy(CloudAPIProxy):

    def __init__(self):
        self.__token__ = None
        self.__project_id__ = None
        self.__token_expires__ = None
        self.__token_lock__ = asyncio.Lock()
        self._all_registry_event: List[CloudAPIProxy] = []
        super(CloudAuthProxy, self).__init__(RoboArtisan.base)

    def register_event(self, event: CloudAPIProxy):
        self._all_registry_event.append(event)

    def update_event_token(self):
        for event in self._all_registry_event:
            self.logger.debug(f"Update event token: {event}")
            event.update_token(
                token=self.__token__,
                project_id=self.__project_id__
            )

    def update_token(self, token: str = "", project_id: str = ""):
        """ not recommend to use this method, use _update_token instead """
        if token:
            self.__token__ = token
            self.__token_expires__ = datetime.utcnow() + timedelta(
                seconds=self.__update_token_period__)

        if project_id:
            self.__project_id__ = project_id

    @property
    def token(self):
        return self.__token__

    @property
    def project_id(self):
        return self.__project_id__

    async def run(self):
        while 1:
            if self._should_exit:
                break
            async with self.__token_lock__:
                check = await self._update_token()
                if check or (not self.project_id):
                    self.__project_id__ = await self.get_project_id(
                        token=self.token
                    )
                    check = True
            if check:
                self.update_event_token()
            await asyncio.sleep(self.__update_token_period__)

    async def _update_token(self):
        if (
                self.__token__ and self.__token_expires__ and
                datetime.utcnow() < self.__token_expires__
        ):
            return False
        iam_server = self.server_uri
        region = self.config.get(self._DOMAIN_NAME, "cn-south-1").strip()

        name = self.config.get("username", "").strip()
        password = self.config.get("password", "").strip()
        domain = self.config.get("domain", "").strip()
        self.logger.debug(f"Update token by {iam_server} - {name} @ {domain}")
        if not (name and password):
            raise CloudError("username or password not set", 401)

        try:
            self.__token__, self.__token_expires__ = await self.get_token(
                name=name,
                password=password,
                domain=domain,
                project_id=region
            )

        except Exception as e:
            self.logger.error(f"Update token failed: {e}")
        return True

    async def get_token(
            self, name, password, domain, project_id
    ):
        """ auth with username/password """
        data = {
            "auth": {
                "identity": {
                    "methods": ["password"],
                    "password": {
                        "user": {
                            "name": name,
                            "password": password,
                            "domain": {
                                "name": domain
                            }
                        }
                    }
                },
                "scope": {
                    "project": {
                        "name": project_id,
                    }
                }
            }
        }
        _url = f"{self.server_uri}/auth/tokens"
        resp = await self.__session__.post(
            _url, json=data
        )
        if resp.status != 201:
            _text = await resp.text()
            self.logger.debug(f"Call {_url} fail: {data} => {_text}")
            raise CloudError(f"auth failed, status code: {resp.status}")
        token = resp.headers.get("X-Subject-Token")
        token_detail = await resp.json()
        token_expires_at = datetime.strptime(
            token_detail['token']['expires_at'],
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        return token, token_expires_at

    async def get_project_id(self, token: str = ""):
        """ get project id from huawei cloud api """
        if not token:
            return
        iam_server = self.server_uri
        region = self.config.get(self._DOMAIN_NAME, "cn-south-1").strip()
        _url = f"{iam_server}/projects"
        self.logger.debug(f"Get project id by {_url} - {region}")
        _headers = {
            "Content-Type": "application/json;charset=utf8",
            "X-Auth-Token": token
        }
        data = {
            "enabled": "true",
            "name": region
        }
        resp = await self.__session__.get(
            _url,
            params=data,
            headers=_headers
        )
        if resp.status != 200:
            _text = await resp.text()
            self.logger.debug(f"Call {_url} fail: {data} => {_text}")
            raise CloudError(
                f"auth failed, status code: {resp.status}", resp.status)
        res = await resp.json()
        projects = res.get("projects", [])
        self.logger.debug(f"Get project id by {_url} - {region} - {projects}")
        if len(projects):
            return projects[0].get("id")
        return
