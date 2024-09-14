from typing import AsyncIterator, List, Optional, Union
from urllib import parse

from . import base_youtube, extract, helpers, innertube, net, thumbnail, video


class VideoInfo:
    def __init__(self, raw: dict, net_obj: net.SessionRequest, it: innertube.InnerTube):
        self.is_playable: Optional[bool] = raw["isPlayable"]
        self.title: Optional[str] = None
        self.video_id: Optional[str] = None
        self.index: Optional[str] = None
        self.thumbnails: thumbnail.ThumbnailQuery = None
        self.lenght: Optional[str] = None
        self.lenght_accessibility: Optional[str] = None
        self.owner_id: Optional[str] = None
        self.owner_name: Optional[str] = None
        self.owner_url: Optional[str] = None
        if self.is_playable:
            self.title = helpers.get_text_by_runs(raw["title"])
            self.video_id = raw["videoId"]
            self.thumbnails = thumbnail.ThumbnailQuery(raw["thumbnail"]["thumbnails"], net_obj)
            self.index = raw["index"]["simpleText"]
            self.lenght = raw["lengthText"]["simpleText"]
            self.lenght_accessibility = raw["lengthText"]["accessibility"]["accessibilityData"]["label"]
            self.owner_name = helpers.get_text_by_runs(raw["shortBylineText"])
            self.owner_id = raw["shortBylineText"]["runs"][0]["navigationEndpoint"][
                "browseEndpoint"]["browseId"]
            self.owner_url = "https://youtube.com" + raw["shortBylineText"]["runs"][0]["navigationEndpoint"][
                "commandMetadata"]["webCommandMetadata"]["url"]
        
    def __repr__(self)->str:
        return f"<youtube_client_async.playlist.VideoInfo video_id=\"{self.video_id}\" >"


class ShortInfo:
    def __init__(self, raw: dict, net_obj: net.SessionRequest, it: innertube.InnerTube):
        self.video_id: str = raw["videoId"]
        self.title: str = raw["headline"]["simpleText"]
        self.thumbnails: thumbnail.ThumbnailQuery = thumbnail.ThumbnailQuery(raw["thumbnail"]["thumbnails"],net_obj)
        self.view_count: str = raw["viewCountText"]["simpleText"]
        self.view_count_accessibility: str = raw["viewCountText"]["accessibility"]["accessibilityData"]["label"]

    def __repr__(self) -> str:
        return f"<youtube_client_async.playlist.ShortInfo video_id=\"{self.video_id}\" >"


class VideoInfoFromPlaylistGetter:
    def __init__(self, first_raw: dict, net_obj: net.SessionRequest, it: innertube.InnerTube):
        self.net_obj: net.SessionRequest = net_obj
        self.it: innertube.InnerTube = it
        self.continuation_token: Optional[str] = None
        if len(first_raw) > 0:
            last_el = first_raw[-1]
            if "continuationItemRenderer" in last_el:
                self.continuation_token = last_el["continuationItemRenderer"][
                    "continuationEndpoint"]["continuationCommand"]["token"]
                del first_raw[-1]
        self.current_continuation_token: Optional[str] = self.continuation_token
        self.f: bool = True
        self.current_item: List[VideoInfo] = [
            VideoInfo(x["playlistVideoRenderer"], self.net_obj, self.it) for x in first_raw
        ]

    def __aiter__(self) -> AsyncIterator[List[VideoInfo]]:
        return self

    async def __anext__(self) -> List[VideoInfo]:
        if self.f:
            self.f = False
            return self.current_item
        if self.current_continuation_token is None:
            raise StopAsyncIteration()
        raw = await self.it.browse(continuation=self.current_continuation_token)
        content = raw["onResponseReceivedActions"][0]["appendContinuationItemsAction"]["continuationItems"]
        continuation_token: Optional[str] = None
        if len(content) > 0:
            last_el = content[-1]
            if "continuationItemRenderer" in last_el:
                continuation_token = last_el["continuationItemRenderer"]["continuationEndpoint"]["continuationCommand"]["token"]
                del content[-1]
        self.current_continuation_token = continuation_token
        return [VideoInfo(x["playlistVideoRenderer"], self.net_obj, self.it) for x in content]


class ShortInfoFromPlaylistGetter:
    def __init__(self, first_raw: dict, continuation: Optional[str], net_obj: net.SessionRequest, it: innertube.InnerTube):
        
        self.net_obj: net.SessionRequest = net_obj
        self.it: innertube.InnerTube = it
        self.continuation_token: Optional[str] = continuation
        self.current_continuation_token: Optional[str] = self.continuation_token
        self.f: bool = True
        self.current_item: List[VideoInfo] = [
            ShortInfo(
                x["richItemRenderer"]["content"]["reelItemRenderer"],
                self.net_obj,
                self.it)
            for x in first_raw
        ]

    def __aiter__(self) -> AsyncIterator[List[ShortInfo]]:
        return self

    async def __anext__(self) -> List[ShortInfo]:
        if self.f:
            self.f = False
            return self.current_item
        if self.current_continuation_token is None:
            raise StopAsyncIteration()
        raw = await self.it.browse(continuation=self.current_continuation_token)
        content = raw["onResponseReceivedActions"][0]["appendContinuationItemsAction"]["continuationItems"]
        continuation_token: str = None
        if len(content) > 0:
            last_el = content[-1]
            if "continuationItemRenderer" in last_el:
                continuation_token = last_el["continuationItemRenderer"]["continuationEndpoint"]["continuationCommand"]["token"]
                del content[-1]
        self.current_continuation_token = continuation_token
        return [
            ShortInfo(
                x["richItemRenderer"]["content"]["reelItemRenderer"],
                self.net_obj,
                self.it
            )
            for x in content
        ]


class Playlist(base_youtube.BaseYoutube):
    def __init__(
        self,
        url: str,
        html: str,
        net_obj: net.SessionRequest,
        it: innertube.InnerTube,
        initial_data=None,
        ytcfg=None,
        base_url: str = None
    ):
        self.base_url = base_url
        self.parsed_url = parse.urlparse(base_url)
        self.parsed_query = parse.parse_qs(self.parsed_url.query)
        self.playlist_id_from_url: str = extract.playlist_id(self.parsed_url, self.parsed_query)
        self.video_id_inline_pl_url: Optional[str] = extract.playlist_video_id(self.parsed_url, self.parsed_query)
        
        self.video_url_inline_pl_url: Optional[str] = (
            video.get_video_url(self.video_id_inline_pl_url)
            if self.video_id_inline_pl_url
            else None
        )
        self.contains_video: bool = self.video_id_inline_pl_url is not None
        super().__init__(url, html, net_obj, it, initial_data, ytcfg)

    @property
    def _header(self) -> dict:
        return self.initial_data["header"]["playlistHeaderRenderer"]

    @property
    def title(self) -> str:
        return self._header["title"]["simpleText"]

    @property
    def playlist_id(self) -> str:
        return self._header["playlistId"]

    @property
    def video_count(self) -> str:
        return helpers.get_text_by_runs(self._header["numVideosText"])

    @property
    def descirption(self):
        return self._header["descriptionText"]

    @property
    def owner_name(self) -> str:
        return helpers.get_text_by_runs(self._header["ownerText"])

    @property
    def owner_id(self) -> str:
        return self._header["ownerEndpoint"]["browseEndpoint"]["browseId"]

    @property
    def owner_url(self) -> str:
        return "https://youtube.com" + self._header["ownerEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"]

    @property
    def owner_thumbnail(self) -> thumbnail.ThumbnailQuery:
        return thumbnail.ThumbnailQuery(self.initial_data["sidebar"]["playlistSidebarRenderer"]["items"][1][
            "playlistSidebarPrimaryInfoRenderer"]["playlistSidebarSecondaryInfoRenderer"]["videoOwner"][
            "videoOwnerRenderer"]["thumbnail"]["thumbnails"],
            self.net_obj)

    @property
    def view_count(self) -> str:
        return self._header["viewCountText"]["simpleText"]

    @property
    def is_editable(self) -> bool:
        return self._header["isEditable"]

    @property
    def can_delete(self) -> bool:
        try:
            return self._header["editableDetails"]["canDelete"]
        except KeyError:
            return False

    @property
    def privacy_status(self) -> str:
        return self._header["privacy"]

    @property
    def banner(self) -> thumbnail.ThumbnailQuery:
        return thumbnail.ThumbnailQuery(self._header["playlistHeaderBanner"][
            "heroPlaylistThumbnailRenderer"]["thumbnail"]["thumbnails"],
            self.net_obj)

    @property
    def update_date(self) -> Optional[str]:
        try:
            return helpers.get_text_by_runs(self.initial_data["sidebar"][
                "playlistSidebarRenderer"]["items"][0][
                "playlistSidebarPrimaryInfoRenderer"]["stats"][2])# TODO test
        except IndexError:
            return None

    def get_videos_getter(self) -> Union[VideoInfoFromPlaylistGetter, ShortInfoFromPlaylistGetter]:
        s = self.initial_data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"][0]["tabRenderer"][
            "content"]["sectionListRenderer"]["contents"][0]["itemSectionRenderer"]["contents"][0]
        if "richGridRenderer" in s:
            continuation = self.initial_data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"][0]["tabRenderer"][
                "content"]["sectionListRenderer"]["contents"]
            if len(continuation) > 1:
                continuation = continuation[1]["continuationItemRenderer"]["continuationEndpoint"][
                    "continuationCommand"]["token"]
            else:
                continuation = None
            return ShortInfoFromPlaylistGetter(s["richGridRenderer"]["contents"], continuation, self.net_obj, self.it)
        else:
            return VideoInfoFromPlaylistGetter(s["playlistVideoListRenderer"]["contents"], self.net_obj, self.it)


async def get_playlist(
    url: str,
    net_obj: net.SessionRequest,
    it: innertube.InnerTube,
    html: Optional[str] = None,
    initial_data: Optional[dict] = None,
    ytcfg: Optional[dict] = None,
) -> Playlist:

    parsed_url = parse.urlparse(url)
    parsed_query = parse.parse_qs(parsed_url.query)
    pqs = parsed_query
    try:
        del pqs["v"]
    except KeyError:
        pass
    try:
        del pqs["index"]
    except KeyError:
        pass
    try:
        del pqs["pp"]
    except KeyError:
        pass
    curl = extract.generate_url_by_query(parsed_url, pqs, "/playlist")
    c_html = html if html else await net_obj.get_text(curl)
    return Playlist(curl, c_html, net_obj, it, initial_data, ytcfg, url)
