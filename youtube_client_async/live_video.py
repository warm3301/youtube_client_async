from dataclasses import dataclass
from typing import AsyncIterator, Dict, List, Optional, Tuple, Union
from urllib import parse

from . import extract, helpers, innertube, net, thumbnail, video


def get_live_url(id: str) -> str:
    return f"https://youtube.com/watch?v={id}"


def get_live_embed_url(id: str) -> str:
    return f"https://www.youtube.com/embed/{id}"


def get_live_id(url: str) -> str:
    parsed_url = parse.urlparse(url)
    parsed_query = parse.parse_qs(parsed_url.query)
    return extract.video_id(parsed_url, parsed_query)


@dataclass
class LiveMetadata:
    title: Optional[str] = None
    description: Optional[str] = None
    date: Optional[str] = None
    view_count: Optional[str] = None
    is_live: Optional[bool] = None

    def update(self, new: Dict):
        for key, value in new.items():
            if hasattr(self, key):
                setattr(self, key, value)


class LiveMetadataUpdater:
    def __init__(self, vid_id: str, net_obj: net.SessionRequest, it: innertube.InnerTube):
        self._vid_id: str = vid_id
        self._continuation: Optional[str] = None
        self.net_obj: net.SessionRequest = net_obj
        self.it: innertube.InnerTube = it

    async def _get_updated_info_with_token(self, continuation: str = None) -> Tuple[List[Dict[str, Union[str, bool]]], str]:
        """in [0] list of updated options in first name in second value. in [1] continuation."""
        params = dict()
        if continuation:
            params["continuation"] = continuation
        else:
            params["video_id"] = self._vid_id
        raw = await self.it.update_metadata(**params)
        res = {}
        for prop in raw["actions"]:
            if "updateViewershipAction" in prop:
                res["view_count"] = prop["updateViewershipAction"]["viewCount"]["videoViewCountRenderer"]["originalViewCount"]
                res["is_live"] = prop["updateViewershipAction"]["viewCount"]["videoViewCountRenderer"].get("isLive", False)
            elif "updateDateTextAction" in prop:
                res["date"] = prop["updateDateTextAction"]["dateText"]["simpleText"]
            elif "updateTitleAction" in prop:
                res["title"] = helpers.get_text_by_runs(prop["updateTitleAction"]["title"])
            elif "updateDescriptionAction" in prop and "description" in prop["updateDescriptionAction"]:
                res["description"] = helpers.get_text_by_runs(prop["updateDescriptionAction"]["description"])
        continuation = raw["continuation"]["timedContinuationData"]["continuation"]
        return res, continuation

    async def update(self, updated_data_class: Optional[LiveMetadata] = None) -> LiveMetadata:
        """update UPdatedLiveMetadata"""
        res, self._continuation, *_ = await self._get_updated_info_with_token(self._continuation)
        if updated_data_class:
            updated_data_class.update(res)
            return updated_data_class
        else:
            updated_data_class = LiveMetadata()
            updated_data_class.update(res)
            return updated_data_class


class LiveChatMessage:
    def __init__(self, raw, net_obj: net.SessionRequest):
        self.raw = raw
        self.net_obj: net.SessionRequest = net_obj
    
    @property
    def id(self) -> str:
        return self.raw["id"]

    @property
    def timestep_usec(self) -> str:
        return self.raw["timestampUsec"]

    @property
    def message(self) -> str:
        try:
            return "".join(x["text"] if "text" in x else x["emoji"]["emojiId"] for x in self.raw["message"]["runs"])
        except KeyError:
            return self.raw["message"]

    @property
    def author_name(self) -> str:
        return self.raw["authorName"]["simpleText"]

    @property
    def author_id(self) -> str:
        return self.raw["authorExternalChannelId"]

    @property
    def thumbnails(self) -> thumbnail.ThumbnailQuery:
        return thumbnail.ThumbnailQuery(self.raw["authorPhoto"]["thumbnails"], self.net_obj)

    def __repr__(self) -> str:
        return f"<LiveChatMessage \"{self.message}\" />"


class LiveChatResponse:
    def __init__(self, raw, net_obj: net.SessionRequest, it: innertube.InnerTube):
        self.raw = raw 
        self.net_obj: net.SessionRequest = net_obj
        self.it: innertube.InnerTube = it
        self._continuation_token: str = raw["continuationContents"]["liveChatContinuation"][
            "continuations"][0]["invalidationContinuationData"]["continuation"]

    @property
    def messages(self) -> List[LiveChatMessage]:
        res = list()
        actions = self.raw["continuationContents"]["liveChatContinuation"]
        if "actions" not in actions:
            return res
        actions = actions["actions"]
        for message_raw in actions:
            if "addChatItemAction" in message_raw:
                message_raw = message_raw["addChatItemAction"]["item"]
                if "liveChatTextMessageRenderer" in message_raw:
                    message_raw = message_raw["liveChatTextMessageRenderer"] # liveChatViewerEngagementMessageRenderer
                    res.append(LiveChatMessage(message_raw, self.net_obj))
        return res


class LiveChat:
    def __init__(self, continuation: str, net_obj: net.SessionRequest, it: innertube.InnerTube):
        self._continuation = continuation
        self.net_obj: net.SessionRequest = net_obj
        self.it: innertube.InnerTube = it

    async def get_response(self) -> LiveChatResponse:
        resp = await self.it.live_chat(self._continuation)
        res = LiveChatResponse(resp, self.net_obj, self.it)
        self._continuation = res._continuation_token
        return res

    def __aiter__(self) -> AsyncIterator[LiveChatResponse]:
        return self

    async def __anext__(self) -> LiveChatResponse:
        return await self.get_response()




class LiveVideo(video.VideoBase):
    def __init__(
        self,
        url: str,
        html: str,
        net_obj: net.SessionRequest,
        it: innertube.InnerTube,
        initial_player: Optional[dict] = None,
        initial_data: Optional[dict] = None,
        ytcfg: Optional[dict] = None,
        js_url: Optional[str] = None,
        js: Optional[str] = None,
    ):
        super().__init__(url, html, net_obj, it, initial_player, initial_data, ytcfg, js_url, js)

    def _current_live_chat_contnuation(self) -> str:
        return self.initial_data["contents"]["twoColumnWatchNextResults"]["conversationBar"]["liveChatRenderer"][
            "continuations"][0]["reloadContinuationData"]["continuation"]

    def _get_live_chat_continuation(self, index=0) -> str:
        """index=0 - top chat
        index=1 - live chat"""
        return self.initial_data["contents"]["twoColumnWatchNextResults"]["conversationBar"]["liveChatRenderer"][
            "header"]["liveChatHeaderRenderer"]["viewSelector"]["sortFilterSubMenuRenderer"]["subMenuItems"][index][
            "continuation"]["reloadContinuationData"]["continuation"]

    @property
    def metadata_updater(self) -> LiveMetadataUpdater:
        return LiveMetadataUpdater(self.video_id, self.net_obj, self.it)

    def get_live_chat(self, index=0) -> LiveChat:
        """index=0 - top chat
        index=1 - live chat"""
        return LiveChat(self._get_live_chat_continuation(index), self.net_obj, self.it)

    @property
    def is_dvr_enabled(self) -> bool:
        return self.initial_player["videoDetails"]["isLiveDvrEnabled"]

    @property
    def live_chunk_readahead(self) -> Optional[int]:
        return self.initial_player["videoDetails"]["liveChunkReadahead"]

    @property
    def is_low_latency(self) -> bool:
        return self.initial_player["videoDetails"]["isLowLatencyLiveStream"]

    @property
    def latency_class(self) -> str:
        return self.initial_player["videoDetails"]["latencyClass"]


class Premiere(LiveVideo):
    def __init__(
        self,
        url: str,
        html: str,
        net_obj: net.SessionRequest,
        it: innertube.InnerTube,
        initial_player: Optional[dict] = None,
        initial_data: Optional[dict] = None,
        ytcfg: Optional[dict] = None,
        js_url: Optional[str] = None,
        js: Optional[str] = None,
    ):

        super().__init__(url, html, net_obj, it, initial_player, initial_data, ytcfg, js_url, js)
    
    @property
    def is_not_started_yet(self) -> bool:
        return "offlineSlate" in self.initial_player["playabilityStatus"]["liveStreamability"]["liveStreamabilityRenderer"]
    
    @property
    def wait_start_stream_after(self) -> str:
        return self.initial_player["playabilityStatus"]["liveStreamability"]["liveStreamabilityRenderer"]["offlineSlate"][
            "liveStreamOfflineSlateRenderer"]["subtitleText"]["simpleText"]
    
    @property
    def wait_stream_time(self) -> str:
        return self.initial_player["playabilityStatus"]["liveStreamability"]["liveStreamabilityRenderer"]["offlineSlate"][
            "liveStreamOfflineSlateRenderer"]["mainText"]["runs"][-1]["text"]

    @property
    def wait_stream_thumbnails(self) -> thumbnail.ThumbnailQuery:
        return thumbnail.ThumbnailQuery(self.initial_player["playabilityStatus"]["liveStreamability"][
            "liveStreamabilityRenderer"]["offlineSlate"]["liveStreamOfflineSlateRenderer"][
            "thumbnail"]["thumbnails"], self.net_obj)

    @property
    def wait_stream_scheduled_start_time(self) -> str:
        return self.initial_player["playabilityStatus"]["liveStreamability"]["liveStreamabilityRenderer"]["offlineSlate"][
            "liveStreamOfflineSlateRenderer"]["scheduledStartTime"]

async def get_live_video(
    url: str,
    net_obj: net.SessionRequest,
    it: innertube.InnerTube,
    html: Optional[str] = None,
    initial_player: Optional[dict] = None,
    initial_data: Optional[dict] = None,
    ytcfg: Optional[dict] = None,
    js_url: Optional[str] = None,
    js: Optional[str] = None,
) -> LiveVideo:

    # If url is "https://www.youtube.com/shorts/{id}" it generic another initial_data
    parsed_url = parse.urlparse(url)
    if parsed_url.path.startswith("/shorts"):
        url = (
            video.get_video_url(extract.short_id(url)) + ""
            if not parsed_url.query
            else f"?{parsed_url.query}"
        )
    c_html = html if html else await net_obj.get_text(url)
    return LiveVideo(url, c_html, net_obj, it, initial_player, initial_data, ytcfg, js_url, js)


async def get_premiere(
    url: str,
    net_obj: net.SessionRequest,
    it: innertube.InnerTube,
    html: Optional[str] = None,
    initial_player: Optional[dict] = None,
    initial_data: Optional[dict] = None,
    ytcfg: Optional[dict] = None,
    js_url: Optional[str] = None,
    js: Optional[str] = None,
) -> Premiere:

    # If url is "https://www.youtube.com/shorts/{id}" it generic another initial_data,
    # that can descibe in other class
    parsed_url = parse.urlparse(url)
    if parsed_url.path.startswith("/shorts"):
        url = (
            video.get_video_url(extract.short_id(url)) + ""
            if not parsed_url.query
            else f"?{parsed_url.query}"
        )
    c_html = html if html else await net_obj.get_text(url)
    return Premiere(url, c_html, net_obj, it, initial_player, initial_data, ytcfg, js_url, js)
