from abc import ABC
from enum import Enum
from functools import cached_property
from typing import AsyncIterator, List, Optional, TypeVar, Union, overload
from urllib import parse

from . import (
    base_info,
    base_youtube,
    exceptions,
    extract,
    helpers,
    innertube,
    net,
    playlist,
    post,
    thumbnail,
)


class ChannelTabNotFoundError(exceptions.YoutubeClientError):
    def __init__(self, searching_tab_arg, searching_method, tabs):
        super().__init__(
            f"search tab {searching_tab_arg} by {searching_method} not found in tabs in channel"
        )


class GetterPlayableFromChannelSortedType(Enum):
    new = 0
    popular = 1
    oldest = 2


class GetterPlaylistsFromChannelSortedType(Enum):
    create_date = 0
    update_date = 1


class VideoSortItem:
    def __init__(self, title: str, selected: bool, token: str):
        self.title: str = title
        self.selected: bool = selected
        self.token: str = token

    def __repr__(self) -> str:
        return (
            "<youtube_client_async.channel.VideoSortItem"
            f"{' selected ' if self.selected else ' '}"
            f'title="{self.title}" token="{self.token}"'
        )


VideoSortItemQueryT = TypeVar("VideoSortItemQueryT", bound="VideoSortItemQuery")


class VideoSortItemQuery:
    def __init__(self, raw):
        self.raw = raw
        self.items: List[VideoSortItem] = [
            VideoSortItem(
                x["chipCloudChipRenderer"]["text"]["simpleText"],
                x["chipCloudChipRenderer"]["isSelected"],
                x["chipCloudChipRenderer"]["navigationEndpoint"][
                    "continuationCommand"]["token"],
            )
            for x in raw
        ]
        self.current_index = 0

    def get_by_sorted_type(
        self, sorted_type: GetterPlayableFromChannelSortedType
    ) -> VideoSortItem:
        return self.items[int(sorted_type.value)]

    @property
    def selected(self) -> Optional[VideoSortItem]:
        for item in self.items:
            if item.selected:
                return item
        return None

    @property
    def selected_index(self) -> int:
        """return -1 if does't exit"""
        for i, item in enumerate(self.items):
            if item.selected:
                return i
        return -1

    @overload
    def __getitem__(self, i: slice) -> VideoSortItemQueryT:
        pass

    @overload
    def __getitem__(self, i: int) -> VideoSortItem:
        pass

    def __getitem__(self, i: Union[slice, int]) -> Union[VideoSortItemQueryT, VideoSortItem]:
        if isinstance(i, slice):
            return VideoSortItemQuery(self.raw[i])
        return self.items[i]

    def __len__(self) -> int:
        return len(self.items)

    def __repr__(self) -> str:
        return f"<youtube_client_async.channel.VideoSortItemQuery {str(self.items)} >"

    def __iter__(self) -> VideoSortItemQueryT:
        self.current_index = 0
        return self

    def __next__(self) -> VideoSortItem:
        if self.current_index >= len(self.items):
            raise StopIteration()
        val = self.items[self.current_index]
        self.current_index += 1
        return val


class ShortInfo:
    def __init__(self, raw, net_obj: net.SessionRequest, it: innertube.InnerTube):
        self.net_obj: net.SessionRequest = net_obj
        self.it: innertube.InnerTube = it
        rir = raw["onTap"]["innertubeCommand"]
        self.title: str = raw["overlayMetadata"]["primaryText"]["content"]
        self.videw_count: str = raw["overlayMetadata"]["secondaryText"]["content"]
        self.thumbnail:thumbnail.ThumbnailQuery(
            raw["thumbnail"]["sources"] + rir["reelWatchEndpoint"]["thumbnail"]["thumbnails"],
            net_obj)
        self.accessibility_text: str = raw["accessibilityText"]
        self.video_id: str = rir["reelWatchEndpoint"]["videoId"]
        self.url: str = "https://youtube.com" + rir["commandMetadata"]["webCommandMetadata"]["url"]
    
    def __repr__(self) -> str:
        return f"<youtube_client_async \"{self.title}\" >"


class PlaylistInfo:
    def __init__(self, raw, net_obj: net.SessionRequest, it: innertube.InnerTube):
        self.net_obj: net.SessionRequest = net_obj
        self.it: innertube.InnerTube = it
        self.playlist_id: str = raw["playlistId"]
        self.title: str = helpers.get_text_by_runs(raw["title"])
        self.url: str = (
            "https://youtube.com"
            + raw["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"]
        )
        self.video_count_text: Optional[str] = (
            raw["videoCountText"]["runs"][0]["text"]
            if "videoCountText" in raw
            else None
        )

    def __repr__(self) -> str:
        return f'<youtube_client_async.channel.PlaylistInfo id="{self.playlist_id}" >'

    async def get_playlist_obj(self) -> playlist.Playlist:
        return await playlist.get_playlist(self.url, self.net_obj, self.it)


class StreamInfo:
    def __init__(self, raw, net_obj: net.SessionRequest, it: innertube.InnerTube):
        self.video_id: str = raw["videoId"]
        self.title: str = helpers.get_text_by_runs("title")
        self.description_snippet: Optional[str] = None
        try:
            self.description_snippet = helpers.get_text_by_runs(raw["descriptionSnippet"])
        except KeyError:
            self.description_snippet = None
        self.published_time: str = raw["publishedTimeText"]["simpleText"]
        self.length_text: Optional[str] = None
        self.lenght_text_accessibility: Optional[str] = None
        try:
            self.length_text = raw["lengthText"]["simpleText"]
            self.lenght_text_accessibility = raw["lengthText"]["accessibility"][
                "accessibilityData"
            ]["label"]
        except KeyError:
            pass
        self.view_count: Optional[str] = None
        try:
            self.view_count = raw["viewCountText"]["simpleText"]
        except KeyError:
            self.view_count = None
        self.view_count_short: Optional[str] = None
        try:
            self.view_count_short = raw["shortViewCountText"]["simpleText"]
        except KeyError:
            self.view_count_short = None
        self.url: str = (
            "https://youtube.com"
            + raw["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"]
        )
        self.thumbnails: thumbnail.ThumbnailQuery = thumbnail.ThumbnailQuery(
            raw["thumbnail"]["thumbnails"], net_obj
        )

    def __repr__(self) -> str:
        return f'<youtube_client_async.channel.LiveInfo id="{self.video_id}" >'


class BaseTabContent(ABC):
    def __init__(self, net_obj: net.SessionRequest, it: innertube.InnerTube):
        self.net_obj: net.SessionRequest = net_obj
        self.it: innertube.InnerTube = it


class TabHomeContent(BaseTabContent):
    def __init__(self, raw, net_obj: net.SessionRequest, it: innertube.InnerTube):
        super().__init__(net_obj, it)
        raw = raw["sectionListRenderer"]["contents"]


class TabContinuationContentBase(BaseTabContent, ABC):
    def __init__(self, raw: dict, net_obj: net.SessionRequest, it: innertube.InnerTube):
        self.net_obj: net.SessionRequest = net_obj
        self.it: innertube.InnerTube = it

        self._raw: List[dict] = None
        if "richGridRenderer" in raw:
            self._raw = raw["richGridRenderer"]["contents"]
        elif "sectionListRenderer" in raw:
            self._raw = raw["sectionListRenderer"]["contents"][0][
                "itemSectionRenderer"]["contents"]
            if isinstance(self._raw, list) and "gridRenderer" in self._raw[0]:
                self._raw = self._raw[0]["gridRenderer"]["items"]
        else:
            raise NotImplementedError("dont know")
        self.continuation_token: Optional[str] = None
        last = self._raw[-1]
        if "continuationItemRenderer" in last:
            self.continuation_token = last["continuationItemRenderer"][
                "continuationEndpoint"]["continuationCommand"]["token"]
            del self._raw[-1]
        self.current_continuation_token: Optional[str] = self.continuation_token
        self.f = True

    async def __anext__(self) -> List[dict]:
        if self.f:
            self.f = False
            rv = self._raw
            self.__delattr__("_raw")
            return rv
        if self.current_continuation_token is None:
            raise StopAsyncIteration()
        raw = await self.it.browse(continuation=self.current_continuation_token)
        items_raw = None
        if "onResponseReceivedActions" in raw:
            items_raw = raw["onResponseReceivedActions"][-1]
            if "reloadContinuationItemsCommand" in items_raw:
                items_raw = items_raw["reloadContinuationItemsCommand"][
                    "continuationItems"]
            else:
                items_raw = items_raw["appendContinuationItemsAction"][
                    "continuationItems"]
        elif "onResponseReceivedEndpoints" in raw:
            items_raw = raw["onResponseReceivedEndpoints"][0][
                "appendContinuationItemsAction"]["continuationItems"]
        else:
            raise NotImplementedError("dont know")

        last = items_raw[-1]
        if "continuationItemRenderer" in last:
            self.current_continuation_token = last["continuationItemRenderer"][
                "continuationEndpoint"]["continuationCommand"]["token"]
            del items_raw[-1]
        else:
            self.current_continuation_token = None
        return items_raw


class TabPlayableContentBase(TabContinuationContentBase, ABC):
    def __init__(
        self,
        raw: dict,
        video_sort: GetterPlayableFromChannelSortedType,
        net_obj: net.SessionRequest,
        it: innertube.InnerTube,
    ):
        super().__init__(raw, net_obj, it)
        self.video_sort: GetterPlayableFromChannelSortedType = video_sort
        if "header" in raw["richGridRenderer"]:
            headers: List[dict] = raw["richGridRenderer"]["header"][
                "feedFilterChipBarRenderer"]["contents"]
            self.sorted_types: VideoSortItemQuery = VideoSortItemQuery(headers)
            if self.video_sort.value != self.sorted_types.selected_index:
                self.f = False
                self.current_continuation_token = self.sorted_types.get_by_sorted_type(
                    self.video_sort
                ).token
                helpers.logger.info(
                    (
                        "change continuation in TabPlayableContentBase "
                        f"from {self.sorted_types.selected.title} to {self.video_sort.name}"
                    )
                )
        else:
            helpers.logger.warning("not found headers in TabPlayableContentBase in richGridRenderer")


class TabVideosContent(TabPlayableContentBase):
    def __init__(
        self,
        raw: dict,
        video_sort: GetterPlayableFromChannelSortedType,
        net_obj: net.SessionRequest,
        it: innertube.InnerTube,
    ):
        super().__init__(raw, video_sort, net_obj, it)
        self._videos: List[base_info.VideoInfo] = [
            base_info.VideoInfo(
                x["richItemRenderer"]["content"]["videoRenderer"], self.net_obj, self.it
            )
            for x in self._raw
        ]

    def __aiter__(self) -> AsyncIterator[List[base_info.VideoInfo]]:
        return self

    async def __anext__(self) -> List[base_info.VideoInfo]:
        return [
            base_info.VideoInfo(
                x["richItemRenderer"]["content"]["videoRenderer"], self.net_obj, self.it
            )
            for x in await super().__anext__()
        ]


class TabShortsContent(TabPlayableContentBase):
    def __init__(
        self,
        raw: dict,
        video_sort: GetterPlayableFromChannelSortedType,
        net_obj: net.SessionRequest,
        it: innertube.InnerTube,
    ):
        super().__init__(raw, video_sort, net_obj, it)
        self._videos: List[ShortInfo] = [
            ShortInfo(
                x["richItemRenderer"]["content"]["shortsLockupViewModel"],
                self.net_obj,
                self.it,
            )
            for x in self._raw
        ]

    def __aiter__(self) -> AsyncIterator[List[ShortInfo]]:
        return self

    async def __anext__(self) -> List[ShortInfo]:
        return [
            ShortInfo(
                x["richItemRenderer"]["content"]["shortsLockupViewModel"],
                self.net_obj,
                self.it,
            )
            for x in await super().__anext__()
        ]

# TODO sort
class TabCommunityContent(TabContinuationContentBase):
    def __init__(self, raw: dict, net_obj: net.SessionRequest, it: innertube.InnerTube):
        super().__init__(raw, net_obj, it)

    def __aiter__(self) -> AsyncIterator[List[post.Post]]:
        return self

    async def __anext__(self) -> List[post.Post]:
        dn = await super().__anext__()
        return [
            post.Post(
                x["backstagePostThreadRenderer"]["post"]["backstagePostRenderer"],
                self.net_obj,
                self.it,
            )
            for x in dn
        ]

# TODO sort
class TabPlaylistsContent(TabContinuationContentBase):
    def __init__(
        self,
        raw: dict,
        playlist_sort: GetterPlaylistsFromChannelSortedType,
        net_obj: net.SessionRequest,
        it: innertube.InnerTube,
    ):
        super().__init__(raw, net_obj, it)

    def __aiter__(self) -> AsyncIterator[List[PlaylistInfo]]:
        return self

    async def __anext__(self) -> List[PlaylistInfo]:
        dn = await super().__anext__()
        try:
            return [
                PlaylistInfo(x["gridPlaylistRenderer"], self.net_obj, self.it)
                for x in dn
            ]
        except KeyError:
            print(dn[0]["gridRenderer"]["items"][-1])


class TabLiveStreamsContent(TabPlayableContentBase):
    def __init__(
        self,
        raw: dict,
        sort_type: GetterPlayableFromChannelSortedType,
        net_obj: net.SessionRequest,
        it: innertube.InnerTube,
    ):
        super().__init__(raw, sort_type, net_obj, it)
        self._videos: List[StreamInfo] = [
            StreamInfo(
                x["richItemRenderer"]["content"]["videoRenderer"],
                self.net_obj,
                self.it,
            )
            for x in self._raw
        ]

    def __aiter__(self) -> AsyncIterator[List[StreamInfo]]:
        return self

    async def __anext__(self) -> List[StreamInfo]:
        return [
            StreamInfo(
                x["richItemRenderer"]["content"]["videoRenderer"],
                self.net_obj,
                self.it,
            )
            for x in await super().__anext__()
        ]


class TabSearchContent(BaseTabContent):
    def __init__(self, raw: dict, net_obj: net.SessionRequest, it: innertube.InnerTube):
        super().__init__(net_obj, it)


class Tab:
    def __init__(self, raw: dict, net_obj: net.SessionRequest):
        self.net_obj: net.SessionRequest = net_obj
        tab = (
            raw["tabRenderer"] 
            if "tabRenderer" in raw
            else raw["expandableTabRenderer"]
        )
        self.title: str = tab["title"]
        self.selected: bool = tab.get("selected", False)
        self.content: Optional[dict] = tab.get("content")
        self.url: str = (
            "https://youtube.com"
            + tab["endpoint"]["commandMetadata"]["webCommandMetadata"]["url"]
        )
        # TODO default IT BROWSE?
        self.path = parse.urlparse(self.url).path

    async def get_content(self) -> dict:
        if self.content:
            return self.content
        initial_data = extract.initial_data(await self.net_obj.get_text(self.url))
        initial_data = initial_data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"]
        ntc = None
        for x in initial_data:
            tab = x["tabRenderer"] if "tabRenderer" in x else x["expandableTabRenderer"]
            curl = tab["endpoint"]["commandMetadata"]["webCommandMetadata"]["url"]
            _cls = curl.split("/")[-1]
            url = self.url
            ls = url.split("/")[-1]
            if _cls.lower() == ls.lower():
                ntc = tab["content"]
        if ntc is None:
            raise ChannelTabNotFoundError(self.url, "end of url", initial_data)
        self.content = ntc
        return ntc

    def __repr__(self) -> str:
        return (
            f'<youtube_client_async.channel.Tab "{self.title}"'
            f"{' has content ' if self.content else ' '}>"
        )


class TabQuery:
    def __init__(self, tabs_raw: List[dict], net_obj: net.SessionRequest):
        self.net_obj: net.SessionRequest = net_obj
        self.tabs: List[Tab] = [Tab(x, self.net_obj) for x in tabs_raw]

        def has_content_str(tab: Tab):
            return " has content" if tab.content is not None else ""

        info_for_logger = "\n".join(
            [f"{x.title}{has_content_str(x)} = {x.url}" for x in self.tabs]
        )
        helpers.logger.info(f"find tabs on channel: \n{info_for_logger}")

    def get_by_name(self, name: str) -> Optional[Tab]:
        """Home|Videos|Shorts|Community|Search"""
        for x in self.tabs:
            if x.title.lower() == name.lower():
                return x
        raise ChannelTabNotFoundError(name, "by title", self.tabs)

    def get_by_end_url(self, end: str) -> Optional[Tab]:
        """featured|videos|shorts|community|search"""
        for x in self.tabs:
            if x.url.endswith(end):
                return x
        raise ChannelTabNotFoundError(end, "end of url", self.tabs)

    @property
    def selected(self) -> Optional[Tab]:
        for x in self.tabs:
            if x.selected:
                return x
        return None

    def __repr__(self) -> str:
        titles = ", ".join([f'"{x.title}"' for x in self.tabs])
        return f"<youtube_client_async.channel.TabQuery {titles} >"


class DefaultChannelUrl(Enum):
    featured = "/featured"
    videos = "/videos"
    shorts = "/shorts"
    streams = "/streams"
    releases = "/releases"
    playlist = "/playlists"
    community = "/community"


class Channel(base_youtube.BaseYoutube):
    def __init__(
        self,
        url: str,
        html: str,
        net_obj: net.SessionRequest,
        it: innertube.InnerTube,
        initial_data=None,
        ytcfg=None,
        default_tab:DefaultChannelUrl=DefaultChannelUrl.featured
    ):
        channel_url = "https://youtube.com" + extract.channel_id(url)
        self.featured_url = channel_url + "/featured"
        super().__init__(channel_url + default_tab.value, html, net_obj, it, initial_data, ytcfg)
        self.videos_url = channel_url + "/videos"
        self.shorts_url = channel_url + "/shorts"
        self.streams_url = channel_url + "/streams"
        self.playlists_url = channel_url + "/playlists"
        self.community_url = channel_url + "/community"
        self.releases_url = channel_url + "/releases"

    @cached_property
    def tabs_info(self) -> TabQuery:
        "Home|Videos|Shorts|Community|Search"
        return TabQuery(
            self.initial_data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"],
            self.net_obj,
        )

    @cached_property
    def selected_tab(self) -> Optional[Tab]:
        return self.tabs_info.selected

    def __repr__(self) -> str:
        return f"<Channel {self.url}/>"

    async def get_videos_tab(
        self,
        sort_type: GetterPlayableFromChannelSortedType = GetterPlayableFromChannelSortedType.new,
    ) -> TabVideosContent:
        videos_tab_info = self.tabs_info.get_by_end_url("videos")
        content = await videos_tab_info.get_content()
        return TabVideosContent(content, sort_type, self.net_obj, self.it)

    async def get_shorts_tab(
        self,
        sort_type: GetterPlayableFromChannelSortedType = GetterPlayableFromChannelSortedType.new,
    ) -> TabShortsContent:
        shorts_tab_info = self.tabs_info.get_by_end_url("shorts")
        content = await shorts_tab_info.get_content()
        return TabShortsContent(content, sort_type, self.net_obj, self.it)

    async def get_community_tab(self) -> TabCommunityContent:
        # TODO sort
        shorts_tab_info = self.tabs_info.get_by_end_url("community")
        content = await shorts_tab_info.get_content()
        return TabCommunityContent(content, self.net_obj, self.it)

    async def get_playlists_tab(self) -> TabPlaylistsContent:
        playlist_tab_info = self.tabs_info.get_by_end_url("playlists")
        content = await playlist_tab_info.get_content()
        return TabPlaylistsContent(content, GetterPlaylistsFromChannelSortedType.create_date, self.net_obj, self.it)

    # async def get_releases_tab(self) -> Tab

    async def get_live_streams_tab(
        self,
        sort_type: GetterPlayableFromChannelSortedType = GetterPlayableFromChannelSortedType.new,
    ) -> TabLiveStreamsContent:
        live_tab_info = self.tabs_info.get_by_end_url("streams")
        content = await live_tab_info.get_content()
        return TabLiveStreamsContent(content, sort_type, self.net_obj, self.it)

    async def get_search_tab(self) -> TabSearchContent:
        search_tab_info = self.tabs_info.get_by_end_url("search")
        return TabSearchContent(
            await search_tab_info.get_content(), self.net_obj, self.it
        )

    @property
    def _metadata_renderer(self) -> dict:
        return self.initial_data["metadata"]["channelMetadataRenderer"]

    @property
    def _microformat_renderer(self) -> dict:
        return self.initial_data["microformat"]["microformatDataRenderer"]

    @property
    def _page_header(self) -> dict:
        return self.initial_data["header"]["pageHeaderRenderer"]["content"][
            "pageHeaderViewModel"]

    @property
    def title(self) -> str:
        return self._metadata_renderer["title"]

    @property
    def description(self) -> str:
        return self._metadata_renderer["description"]

    @property
    def tags(self) -> List[str]:
        return self._microformat_renderer["tags"]

    @property
    def _rss_url(self) -> str:
        return self._metadata_renderer["rssUrl"]

    @property
    def external_id(self) -> str:
        return self._metadata_renderer["externalId"]

    @property
    def channel_url(self) -> str:
        return self._metadata_renderer["channelUrl"]

    @property
    def vanity_channel_url(self) -> str:
        return self._metadata_renderer["vanityChannelUrl"]

    @property
    def android_package(self) -> str:
        return self._microformat_renderer["androidPackage"]

    @property
    def ios_package(self) -> str:
        return self._microformat_renderer["iosAppStoreId"]

    @property
    def no_index(self) -> bool:
        return self._microformat_renderer["noindex"]

    @property
    def unlisted(self) -> bool:
        return self._microformat_renderer["unlisted"]

    @property
    def owner_urls(self) -> List[str]:
        return self._metadata_renderer["ownerUrls"]

    @property
    def avatar(self) -> thumbnail.ThumbnailQuery:
        raw = list(
            self._metadata_renderer["avatar"]["thumbnails"]
            + self._microformat_renderer["thumbnail"]["thumbnails"]
        )
        try:
            raw += self._page_header["image"]["decoratedAvatarViewModel"]["avatar"][
                "avatarViewModel"]["image"]["sources"]
        except KeyError:
            pass
        return thumbnail.ThumbnailQuery(raw, self.net_obj)

    @property
    def is_family_safe(self) -> bool:
        return self._metadata_renderer["isFamilySafe"]

    @property
    def available_countries(self) -> List[str]:
        """return available country codes [\"IN\",\"CA\",\"AF\"]"""
        return self._metadata_renderer["availableCountryCodes"]

    @property
    def android_app_url(self) -> str:
        return self._microformat_renderer["linkAlternates"][1]["hrefUrl"]

    @property
    def mobile_web_url(self) -> str:
        return self._microformat_renderer["linkAlternates"][0]["hrefUrl"]

    @property
    def ios_app_url(self) -> str:
        return self._microformat_renderer["linkAlternates"][2]["hrefUrl"]


async def get_channel(
    url: str,
    net_obj: net.SessionRequest,
    it: Optional[innertube.InnerTube],
    html: Optional[str] = None,
    initial_data: Optional[dict] = None,
    ytcfg: Optional[dict] = None,
    default_tab: DefaultChannelUrl = DefaultChannelUrl.featured
) -> Channel:

    c_html = html if html else await net_obj.get_text(url)
    return Channel(url, c_html, net_obj, it, initial_data, ytcfg, default_tab)
