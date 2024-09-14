import asyncio
import json
import random
import re
import time
from functools import lru_cache
from typing import Dict, Optional
from urllib import parse

import aiohttp
import multidict
from aiohttp_retry import ExponentialRetry, RetryClient

from . import exceptions, helpers
from .helpers import logger

default_range_size = 9437184  # 9MB
languages = {"EN": "en-US,en"}
base_user_agent = "Mozilla/5.0"


class SessionRequest:
    __slots__ = (
        "raise_ex_if_status",
        "encoding",
        "session",
        "lang",
        "user_agent",
        "proxy",
        "timeout",
        "retry_options",
        "print_traffic"
    )

    def __init__(
        self,
        session: Optional[aiohttp.ClientSession] = None,
        lang: Optional[str] = None,
        user_agent: Optional[str] = None,
        raise_ex_if_status: bool = True,
        encoding: str = "utf-8",
        proxy: Optional[str] = None,
        retry_count: int = 3,
        timeout: int = 30,
        print_traffic: bool = False
    ):

        self.proxy = proxy
        self.raise_ex_if_status: bool = bool(raise_ex_if_status)
        self.encoding: str = encoding
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.retry_options = ExponentialRetry(attempts=retry_count)
        self.session: aiohttp.ClientSession = (
            session
            if session
            else RetryClient(
                timeout=self.timeout,
                retry_options=self.retry_options
            )
        )
        self.lang: str = lang if lang else languages["EN"]
        self.user_agent: str = user_agent if user_agent else base_user_agent
        self.print_traffic: bool = print_traffic

    async def __aenter__(self):
        await self.session.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()

    def _get_base_headers(self):
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": self.lang,
            "User-Agent": self.user_agent
        }

    async def _send(
        self,
        method: str,
        url: str,
        url_params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: Optional[int] = None
    ) -> aiohttp.ClientResponse:

        cheaders = self._get_base_headers()
        if headers:
            cheaders.update(headers)
        lm = method.lower()
        traffic_message = (
            f"{method} {url}\n"
            f"{url_params=}\n"
            f"{data=}\n"
            f"{headers=}\n"
        )
        if self.print_traffic:
            print(traffic_message)
        logger.info(traffic_message)
        resp = None
        if lm == "get":
            resp = await self.session.get(
                url, json=data, headers=cheaders, params=url_params, proxy=self.proxy, timeout=timeout
            )
        elif lm == "post":
            resp = await self.session.post(
                url, json=data, headers=cheaders, params=url_params, proxy=self.proxy, timeout=timeout
            )
        elif lm == "head":
            resp = await self.session.head(
                url, json=data, headers=cheaders, params=url_params, proxy=self.proxy, timeout=timeout
            )
        else:
            raise Exception(f"not supported method {method}. Only get post and head")
        logger.info(
            f"{lm} {url} status code {resp.status}, byte lenght {resp.headers.get('Content-Length',None)}"
        )
        
        if self.raise_ex_if_status:
            resp.raise_for_status()
        return resp

    async def _get_bytes_resp(
        self,
        method: str,
        url: str,
        url_params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> bytes:
        current_time = time.time()
        resp = await self._send(method, url, url_params, data, headers)
        result = await resp.content.read()
        delta_time = time.time() - current_time
        if not resp.closed:
            resp.close()
        logger.info(f"{method} {url}\ndownloaded bytes {len(result)} in {delta_time:.2f} sec")
        return result

    async def _get_text_resp(
        self,
        method: str,
        url: str,
        url_params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        encoding_resp: Optional[str] = None,
    ) -> str:

        current_time = time.time()
        resp = await self._send(method, url, url_params, data, headers)
        result = await resp.text(encoding_resp)
        delta_time = time.time() - current_time
        if not resp.closed:
            resp.close()
        logger.info(f"{method} {url}\ndownloaded text {len(result)=} in {delta_time:.2f} sec")
        return result

    async def _get_json_resp(
        self,
        method: str,
        url: str,
        url_params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> dict:

        current_time = time.time()
        resp_bytes = await self._get_bytes_resp(method, url, url_params, data, headers)
        result = json.loads(resp_bytes)
        delta_time = time.time() - current_time
        logger.info(f"{method} {url}\ndownload and parsed json in {delta_time:.2f} sec")
        return result

    async def _get_headers(
        self,
        method: str,
        url: str,
        url_params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> multidict.CIMultiDictProxy:

        current_time = time.time()
        resp = await self._send(method, url, url_params, data, headers)
        result = resp.headers
        delta_time = time.time() - current_time
        if not resp.closed:
            resp.close()
        logger.info(f"{method} {url} downloaded headers with status code {resp.status} in {delta_time:.2f} seconds")
        return result

    async def get_lenght(
        self,
        url: str,
        url_params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> Optional[int]:

        sv = (await self._get_headers("HEAD", url, url_params, data, headers)).get(
            "Content-Length", None
        )
        if sv is None:
            return None
        try:
            return int(sv)
        except Exception as e:
            logger.warning(f"get_lenght -> None {e}")
        return None

    async def get_text(
        self,
        url: str,
        url_params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        encoding_resp: Optional[str] = None,
    ) -> str:

        return await self._get_text_resp(
            "get", url, url_params, data, headers, encoding_resp
        )

    async def get_bytes(
        self,
        url: str,
        url_params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> bytes:

        return await self._get_bytes_resp("get", url, url_params, data, headers)

    async def get_json(
        self,
        url: str,
        url_params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> dict:

        return await self._get_json_resp("get", url, url_params, data, headers)

    async def post_text(
        self,
        url: str,
        url_params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        encoding_resp: Optional[str] = None,
    ) -> str:

        return await self._get_text_resp(
            "post", url, url_params, data, headers, encoding_resp
        )

    async def post_bytes(
        self,
        url: str,
        url_params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> bytes:

        return await self._get_bytes_resp("get", url, url_params, data, headers)

    async def post_json(
        self,
        url: str,
        url_params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> dict:

        return await self._get_json_resp("post", url, url_params, data, headers)

    async def seq_filesize(self, url):
        """Fetch size in bytes of file at given URL from sequential requests

        :param str url: The URL to get the size of
        :returns: int: size in bytes of remote file
        """
        total_filesize = 0
        # YouTube expects a request sequence number as part of the parameters.
        split_url = parse.urlsplit(url)
        base_url = f'{split_url.scheme}://{split_url.netloc}/{split_url.path}?'
        querys = dict(parse.parse_qsl(split_url.query))

        # The 0th sequential request provides the file headers, which tell us
        #  information about how the file is segmented.
        querys['sq'] = 0
        url = base_url + parse.urlencode(querys)
        response = await self._send("GET", url)

        response_value = response.read()
        # The file header must be added to the total filesize
        total_filesize += len(response_value)

        # We can then parse the header to find the number of segments
        segment_count = 0
        stream_info = response_value.split(b'\r\n')
        segment_regex = b'Segment-Count: (\\d+)'
        for line in stream_info:
            # One of the lines should contain the segment count, but we don't know
            #  which, so we need to iterate through the lines to find it
            try:
                segment_count = int(helpers.regex_search(segment_regex, line, 1))
            except exceptions.RegexMatchError:
                pass

        if segment_count == 0:
            raise exceptions.RegexMatchError('seq_filesize', segment_regex)

        # We make HEAD requests to the segments sequentially to find the total filesize.
        seq_num = 1
        while seq_num <= segment_count:
            # Create sequential request URL
            querys['sq'] = seq_num
            url = base_url + parse.urlencode(querys)

            total_filesize += await self.get_lenght(url)
            seq_num += 1
        return total_filesize
