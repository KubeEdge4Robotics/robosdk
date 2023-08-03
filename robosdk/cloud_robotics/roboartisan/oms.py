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
from typing import Dict
from typing import List

from robosdk.cloud_robotics.roboartisan.base import CloudAPIProxy
from robosdk.common.constant import RoboArtisan
from robosdk.common.exceptions import CloudError
from robosdk.utils.util import genearteMD5


class RoboOMS(CloudAPIProxy):
    _page_size = 100
    __update_period__ = 60
    _ext_header = {
        "Content-Type": "application/json;charset=utf8",
        "X-Auth-Token": ""
    }

    def __init__(self):
        super().__init__(RoboArtisan.robooms)
        self._robot_data: List = []
        self._deployment_data: List = []

        self._robot_data_lock = asyncio.Lock()
        self._app_data_lock = asyncio.Lock()
        self._deployment_data_lock = asyncio.Lock()
        self._all_properties_map = {}

    def update_token(self, token: str = "", project_id: str = ""):
        if token:
            self._token = token.strip()
            self._ext_header["X-Auth-Token"] = self._token
        if project_id:
            self._project_id = project_id.strip()

    async def run(self):
        while 1:
            if self._should_exit:
                break
            if self._token and self._project_id:
                try:
                    async with self._deployment_data_lock:
                        self._deployment_data = await self.get_app_deployment()
                    async with self._robot_data_lock:
                        self._robot_data = await self.get_robots()
                except Exception as e:
                    self.logger.error(f"Update oms data failed: {e}")
                await asyncio.sleep(self.__update_period__)
            await asyncio.sleep(1)

    @property
    def robots(self):
        return self._robot_data

    @property
    def num_robots(self):
        return len(self._robot_data)

    @property
    def deployments(self):
        return {d["id"]: d for d in self._deployment_data if "id" in d}

    async def get_robot_properties(
            self,
            robot_id: str = "",
            robot_type: str = ""
    ) -> Dict:
        """ get robot properties """
        if not robot_type:
            robot = await self.get_robot(robot_id)
            robot_type = robot.get("type", "")
        if robot_type in self._all_properties_map:
            return self._all_properties_map[robot_type]
        return {}

    async def get_robots(self, offset: int = 0) -> List:
        """ get all robot """
        url = f"{self.server_uri}/roboinstances"
        data = {
            "limit": int(self._page_size),
            "offset": int(offset),
            "sort_key": "created_at",
            "sort_dir": "desc"
        }
        resp = await self.__session__.get(
            url,
            params=data,
            headers=self._ext_header
        )
        if resp.status != 200:
            _text = await resp.text()
            self.logger.debug(f"Call {url} fail: {data} => {_text}")
            raise CloudError("get oms instance failed", resp.status)
        res = await resp.json()
        all_robot = res.get("roboinstances", [])
        count = res.get("count", 0)

        for robot in all_robot:
            properties = await self.get_robot_properties(
                robot_id=robot.get("id", ""),
                robot_type=robot.get("type", "")
            )
            if "properties" not in robot:
                robot["properties"] = {}
            robot["properties"].update(properties)
        if count > offset + self._page_size:
            all_robot.extend(
                await self.get_robots(offset + self._page_size)
            )
        return all_robot

    async def get_robot(self, robot_id: str) -> Dict:
        """ get robot by id """
        url = f"{self.server_uri}/roboinstances/{robot_id}"
        resp = await self.__session__.get(
            url,
            headers=self._ext_header
        )
        if resp.status != 200:
            _text = await resp.text()
            self.logger.debug(f"Call {url} fail: => {_text}")
            raise CloudError("list robot failed", resp.status)

        return await resp.json()

    async def get_apps(self, name: str = "", offset: int = 0) -> List:
        """ get all app """
        url = f"{self.server_uri}/roboapps"
        data = {
            "name": name,
            "limit": int(self._page_size),
            "offset": int(offset),
            "sort_key": "created_at",
            "sort_dir": "desc"
        }
        resp = await self.__session__.get(
            url,
            params=data,
            headers=self._ext_header
        )
        if resp.status != 200:
            _text = await resp.text()
            self.logger.debug(f"Call {url} fail: {data} => {_text}")
            raise CloudError("get oms instance failed", resp.status)

        res = await resp.json()
        all_app = res.get("roboapps", [])
        count = res.get("page", {}).get("count", 0)
        if count > offset + self._page_size:
            all_app.extend(
                await self.get_apps(
                    name=name,
                    offset=offset + self._page_size
                )
            )
        return all_app

    async def get_app(self, app_id: str) -> Dict:
        """ get app by id """
        url = f"{self.server_uri}/roboapps/{app_id}"
        resp = await self.__session__.get(
            url,
            headers=self._ext_header
        )
        if resp.status != 200:
            _text = await resp.text()
            self.logger.debug(f"Call {url} fail: => {_text}")
            raise CloudError("get app failed", resp.status)

        return await resp.json()

    async def create_app(
            self, name: str,
            package_url: str,
            package_type: str = "image",
            package_arch: str = "arm64",
            ros_version: str = "ros1_melodic"
    ) -> str:
        """ create app """
        url = f"{self.server_uri}/roboapps"

        for app in await self.get_apps(name):
            if app.get("name") == name:
                if app.get("package_url") == package_url:
                    return app.get("id")
                await self.delete_app(app.get("id"))

        data = {
            "name": name,
            "package_arch": package_arch,
            "package_url": package_url,
            "package_type": package_type,
            "robo_suite": {
                "ros_version": ros_version
            },
            "tags": {}
        }

        resp = await self.__session__.post(
            url,
            json=data,
            headers=self._ext_header
        )
        if resp.status != 201:
            _text = await resp.text()
            self.logger.debug(f"Call {url} fail: {data} => {_text}")
            raise CloudError("create app failed", resp.status)

        res = await resp.json()
        return res.get("id")

    async def delete_app(self, app_id: str):
        """ delete app """
        url = f"{self.server_uri}/roboapps/{app_id}"
        try:
            await self.__session__.delete(
                url,
                headers=self._ext_header
            )
        except:  # noqa
            self.logger.error("delete app failed")

    async def get_app_versions(self, app_id: str) -> List:
        """ get app versions """
        url = f"{self.server_uri}/roboapps/{app_id}/versions"
        resp = await self.__session__.get(
            url,
            headers=self._ext_header
        )
        if resp.status != 200:
            _text = await resp.text()
            self.logger.debug(f"Call {url} fail: => {_text}")
            raise CloudError("get app versions failed", resp.status)

        res = await resp.json()
        all_versions = res.get("roboapps", [])
        return all_versions

    async def create_app_version(
            self, app_id: str,
            release_type: str = "release",
            release_version: str = "latest",
    ) -> str:
        """ create app version """
        exits_version = await self.get_app_versions(app_id)
        for app_data in exits_version:
            version = app_data.get("release_version", "")
            _type = app_data.get("release_type", "")
            if version != release_version:
                continue
            if _type == release_type:
                return version
            await self.delete_app_version(app_id, version)

        url = f"{self.server_uri}/roboapps/{app_id}/versions"
        data = {
            "release_type": release_type,
            "release_version": release_version
        }

        resp = await self.__session__.post(
            url,
            json=data,
            headers=self._ext_header
        )
        if resp.status != 201:
            _text = await resp.text()
            self.logger.debug(f"Call {url} fail: {data} => {_text}")
            raise CloudError("create app version failed", resp.status)

        return release_version

    async def delete_app_version(self, app_id: str, version: str):
        """ delete app version """
        url = f"{self.server_uri}/roboapps/{app_id}/versions/{version}"
        try:
            await self.__session__.delete(
                url,
                headers=self._ext_header
            )
        except:  # noqa
            self.logger.error("delete app version failed")

    async def get_app_deployment(self, offset: int = 0) -> List:
        """ get app deployment """
        url = f"{self.server_uri}/deployments"

        resp = await self.__session__.get(
            url,
            headers=self._ext_header
        )
        if resp.status != 200:
            _text = await resp.text()
            self.logger.debug(f"Call {url} fail: => {_text}")
            raise CloudError("get app deployment failed", resp.status)

        res = await resp.json()
        all_deployment = res.get("deployment_infos", [])
        count = res.get("count", 0)
        if count > offset + self._page_size:
            all_deployment.extend(
                await self.get_app_deployment(
                    offset=offset + self._page_size
                )
            )
        return all_deployment

    async def create_app_deployment(
            self,
            app_id: str,
            robot_id: str,
            version: str = "latest",
            resources=None,
            command: str = "",
            run_args: List = None,
            run_env: Dict = None,
            volumes: List = None,
            additional_properties: str = ""
    ):
        deploy_name = genearteMD5(f"{app_id}_{version}_{robot_id}")

        for deployment in self._deployment_data:
            if deployment.get("name", "") == deploy_name:
                status = deployment.get("status", "")
                self.logger.debug(
                    f"deployment {deploy_name} already exists, {status}"
                )
                await self.delete_app_deployment(deployment.get("id", ""))
        launch_config = {
            "host_network": True,
            "privileged": False,
            "additionalProperties": additional_properties,
        }
        if command:
            launch_config["command"] = command
        if volumes and isinstance(volumes, list):
            launch_config["volumes"] = volumes
        if run_env and isinstance(run_env, dict):
            launch_config["envs"] = run_env
        if run_args and isinstance(run_args, list):
            launch_config["args"] = run_args
        if resources and isinstance(resources, dict):
            r_limits = resources.get("limits", {})
            r_requests = resources.get("requests", {})
            resources = {}
            if r_limits:
                resources["limits"] = r_limits
            if r_requests:
                resources["requests"] = r_requests
            if resources:
                launch_config["resources"] = resources

        url = f"{self.server_uri}/deployments"

        data = {
            "name": deploy_name,
            "robot_id": robot_id,
            "description": "Deploy by teleop server, do not delete it",
            "robot_app_config": {
                "robot_app_id": app_id,
                "version": version,
                "launch_config": launch_config
            }
        }
        resp = await self.__session__.post(
            url,
            json={"deployment": data},
            headers=self._ext_header
        )
        if resp.status != 201:
            _text = await resp.text()
            self.logger.debug(f"Call {url} fail: {data} => {_text}")
            raise CloudError("create app deployment failed", resp.status)
        res = await resp.json()
        return res.get("id", "")

    async def delete_app_deployment(self, deployment_id: str):
        """ delete app deployment """
        url = f"{self.server_uri}/deployments/{deployment_id}"
        try:
            await self.__session__.delete(
                url,
                headers=self._ext_header
            )
            self._deployment_data = await self.get_app_deployment()
        except:  # noqa
            self.logger.error("delete app deployment failed")

    async def get_app_deployment_status(self, deployment_id: str):
        """ get app deployment status """

        url = f"{self.server_uri}/deployments/{deployment_id}"
        resp = await self.__session__.get(
            url,
            headers=self._ext_header
        )
        if resp.status != 200:
            _text = await resp.text()
            self.logger.debug(f"Call {url} fail: => {_text}")
            raise CloudError("get app deployment status failed", resp.status)
        res = await resp.json()
        self.logger.debug(f"get app deployment {deployment_id} status: {res}")
        return res.get("status", "failure")
