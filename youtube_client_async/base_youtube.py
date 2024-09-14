import time
from abc import ABC
from typing import Optional
from urllib import parse

from . import extract, helpers, innertube, net


class BaseYoutube(ABC):
    """base class for accessing the youtube object by url"""
    def __init__(
        self,
        url: str,
        html: str,
        net_obj: net.SessionRequest,
        it: innertube.InnerTube,
        initial_data=None,
        ytcfg=None,
    ):

        self.url: str = url
        if not hasattr(self, "parsed_url"):
            self.parsed_url = parse.urlparse(url)
        if not hasattr(self, "parsed_query"):
            self.parsed_query = parse.parse_qs(self.parsed_url.query)
        self.html: str = html
        self.net_obj: net.SessionRequest = net_obj
        self.it: innertube.InnerTube = it
        self._initial_data: dict = initial_data
        self._ytcfg: dict = ytcfg

    @property
    def initial_data(self) -> dict:
        if self._initial_data:
            return self._initial_data
        html = self.html
        current_time = time.time()
        self._initial_data = extract.initial_data(html)
        delta_time = time.time() - current_time
        helpers.logger.info(f"extracted initial_data in {delta_time:.2f} seconds")
        return self._initial_data

    @property
    def ytcfg(self) -> dict:
        if self._ytcfg:
            return self._ytcfg
        html = self.html
        current_time = time.time()
        self._ytcfg = extract.get_ytcfg(html)
        delta_time = time.time() - current_time
        helpers.logger.info(f"extracted ytcfg in {delta_time:.2f} seconds")
        return self._ytcfg

    @property
    def logged_in(self) -> bool:
        return not self.initial_data["responseContext"][
            "mainAppWebResponseContext"]["loggedOut"]

    @property
    def res_lang(self) -> str:
        return helpers.get_from_dict(
            self.initial_data,
            "topbar|desktopTopbarRenderer|searchbox|fusionSearchboxRenderer|"
            + "config|webSearchboxConfig|requestLanguage",
        )

    def __repr__(self) -> str:
        return f"<youtube_client.BaseYoutube {self.url=} >"

    def __eq__(self, o: object) -> bool:
        return isinstance(o, BaseYoutube) and o.url == self.url


async def get_base_youtube(
    url: str,
    net_obj: net.SessionRequest,
    it: innertube.InnerTube,
    html: Optional[str] = None,
    initial_data: Optional[dict] = None,
    ytcfg: Optional[dict] = None,
) -> BaseYoutube:

    c_html = html if html else await net_obj.get_text(url)
    return BaseYoutube(url, c_html, net_obj, it, initial_data, ytcfg)
