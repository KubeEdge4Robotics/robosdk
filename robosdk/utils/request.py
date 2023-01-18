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

"""Common encapsulation of service requests"""
import asyncio
import json
from typing import Dict

import aiohttp
from aiohttp.typedefs import StrOrURL

__all__ = ("AsyncRequest", )


class Response:

    def __init__(self, content, response):
        self.content = content
        self.response = response

    def raw(self):
        return self.response

    def text(self, encoding="utf-8"):
        return self.content.decode(encoding)

    @property
    def json(self):
        return json.loads(self.text())

    def __repr__(self):
        return f"<Response [status {self.response.status}]>"

    def __getattr__(self, item):
        try:
            return super().__getattribute__(item)
        except AttributeError:
            return getattr(self.response, item, None)

    __str__ = __repr__


class AsyncRequest:
    def __init__(self, token: str = "", proxies: str = "", **parameter):
        header = parameter.get("headers", {})
        if token:
            header[aiohttp.hdrs.AUTHORIZATION] = token
        parameter["headers"] = header

        # if os.getenv("http_proxy", "") or os.getenv("https_proxy", ""):
        #     parameter["trust_env"] = True
        self._loop = asyncio.get_event_loop()
        self._client = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(verify_ssl=False), **parameter)
        self._tasks = []
        self._result = []
        self._proxies = proxies

    def set_header(self, headers: Dict):
        self._client.headers.update(headers)

    def set_cookies(self, cookies: Dict):
        self._client._cookie_jar.update_cookies(cookies)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.close()

    async def _request(self, method: str, str_or_url: StrOrURL, **parameter):
        async with self._client.request(
                url=str_or_url, method=method,
                proxy=self._get_proxy(), **parameter
        ) as resp:
            self._result.append(
                Response(await resp.read(), resp)
            )

    def async_get(self, url: StrOrURL, *,
                  allow_redirects: bool = True, **kwargs):
        """Perform HTTP GET request."""
        self.add(method=aiohttp.hdrs.METH_GET, url=url,
                 allow_redirects=allow_redirects, **kwargs)

    def async_options(
            self, url: StrOrURL, *, allow_redirects: bool = True, **kwargs
    ):
        """Perform HTTP OPTIONS request."""
        self.add(method=aiohttp.hdrs.METH_OPTIONS, url=url,
                 allow_redirects=allow_redirects, **kwargs)

    def async_head(self, url: StrOrURL, *,
                   allow_redirects: bool = True, **kwargs):
        """Perform HTTP HEAD request."""
        self.add(method=aiohttp.hdrs.METH_HEAD, url=url,
                 allow_redirects=allow_redirects, **kwargs)

    def async_post(self, url: StrOrURL, *, data=None, **kwargs):
        """Perform HTTP POST request."""
        self.add(method=aiohttp.hdrs.METH_POST, url=url,
                 data=data, **kwargs)

    def async_put(self, url: StrOrURL, *, data=None, **kwargs):
        """Perform HTTP PUT request."""
        self.add(method=aiohttp.hdrs.METH_PUT, url=url,
                 data=data, **kwargs)

    def async_patch(self, url: StrOrURL, *, data=None, **kwargs):
        """Perform HTTP PATCH request."""
        self.add(
            method=aiohttp.hdrs.METH_PATCH, url=url, data=data, **kwargs
        )

    def _get_proxy(self):
        return self._proxies or None

    async def async_download(self, url: StrOrURL, dst_file: str,
                             method: str = "GET", **parameter):
        import aiofiles

        async with asyncio.Semaphore(1):
            async with self._client.request(url=url, method=method,
                                            proxy=self._get_proxy(),
                                            **parameter) as resp:
                content = await resp.read()

            if resp.status != 200:
                raise aiohttp.ClientError(
                    f"Download failed: [{resp.status}]")

            async with aiofiles.open(dst_file, "+wb") as f:
                await f.write(content)
            self._result.append(Response(dst_file, resp))

    def download(self, url: StrOrURL, dst_file: str,
                 method: str = "GET", **parameter):
        self._result = []
        self._loop.run_until_complete(
            self.async_download(url=url, dst_file=dst_file,
                                method=method, **parameter)
        )
        return self._result[-1] if self._result else None

    def delete(self, url: StrOrURL, **kwargs):
        """Perform HTTP DELETE request."""
        self.add(method=aiohttp.hdrs.METH_DELETE, url=url, **kwargs)

    def add(self, url: str, method: str = "GET", **parameter):
        self._tasks.append(
            asyncio.ensure_future(
                self._request(str_or_url=url, method=method, **parameter)
            )
        )

    def request(self, url: str, method: str = "GET", **parameter):
        self._result = []
        self._loop.run_until_complete(
            self._request(str_or_url=url, method=method, **parameter)
        )
        return self._result[-1] if self._result else None

    def run(self):
        self._result = []
        self._loop.run_until_complete(asyncio.wait(self._tasks))
        return self._result

    async def async_ping(self, url):
        async with self._client.get(url, proxy=self._get_proxy()) as resp:
            assert not str(resp.status).startswith(("4", "5"))

    def ping(self, url):
        self._loop.run_until_complete(
            self.async_ping(url=url)
        )


def test_async_request():
    a = AsyncRequest()
    a.async_get("https://www.baidu.com")
    a.async_post("https://www.weibo.com")
    a.async_put("https://www.huawei.com")
    r = list(sorted([d.status for d in a.run()]))
    assert r == [200, 200, 405]
