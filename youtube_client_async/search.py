from abc import ABC
from typing import Iterable, List, Optional, Tuple, TypeVar, Union

from . import (
    channel,
    chapter,
    extract,
    helpers,
    innertube,
    net,
    playlist,
    short,
    thumbnail,
    video,
)


class SearchResultInfo(ABC):
    def __init__(self, raw:str):
        self.url: str = "https://youtube.com"+raw["navigationEndpoint"][
            "commandMetadata"]["webCommandMetadata"]["url"]

class PlayableBaseSearchInfo(SearchResultInfo, ABC):
    def __init__(self, raw: str):
        super().__init__(raw)

        self.description_snippet: str = None
        self.title: str = None
        self.video_id: str = raw["videoId"]
        try:
            try:
                self.description_snippet = helpers.get_text_by_runs(raw["detailedMetadataSnippets"][0]["snippetText"])
            except KeyError:
                self.description_snippet = helpers.get_text_by_runs(raw["descriptionSnippet"]["snippetText"])
        except KeyError:
            self.description_snippet = None
        try:
            try:
                self.title = helpers.get_text_by_runs(raw["title"])
            except KeyError:
                self.title = raw["title"]["simpleText"]
        except KeyError:
            self.title = raw["headline"]["simpleText"]


class SearchChapter(chapter.ChapterBase):
    def __init__(self, raw, net_obj: net.SessionRequest, it: innertube.InnerTube):
        super().__init__()
        self.title: str = helpers.get_text_by_runs(raw["title"])
        self.time_description: str = helpers.get_text_by_runs(raw["timeDescription"])
        self.thumbnails: thumbnail.ThumbnailQuery = thumbnail.ThumbnailQuery(raw["thumbnail"]["thumbnails"],net_obj)
        self.url: str = "https://youtube.com" + raw["onTap"]["commandMetadata"]["webCommandMetadata"]["url"]


class SearchVideoInfo(PlayableBaseSearchInfo):
    def __init__(self, raw: str, net_obj: net.SessionRequest, it: innertube.InnerTube):
        super().__init__(raw)
        self.thumbnails: thumbnail.ThumbnailQuery = thumbnail.ThumbnailQuery(raw["thumbnail"]["thumbnails"],net_obj)
        self.owner_name: str = helpers.get_text_by_runs(raw["longBylineText"])
        self.owner_id: str = raw["longBylineText"]["runs"][0]["navigationEndpoint"]["browseEndpoint"]["browseId"]
        self.owner_url: str = "https:/youtube.com"+raw["longBylineText"]["runs"][0][
            "navigationEndpoint"]["browseEndpoint"]["canonicalBaseUrl"]
        self.owner_thumbnais: thumbnail.ThumbnailQuery = thumbnail.ThumbnailQuery(
            raw["channelThumbnailSupportedRenderers"]["channelThumbnailWithLinkRenderer"][
                "thumbnail"]["thumbnails"],
            net_obj
        )
        self.published_time_text: Optional[str] = None
        try:
            self.published_time_text = raw["publishedTimeText"]["simpleText"]
        except KeyError:
            self.published_time_text = None
        self.lenght: str = raw["lengthText"]["simpleText"]
        self.view_count: str = raw["viewCountText"]["simpleText"]
        self.owner_is_vereficated: bool = False
        try:
            self.owner_is_vereficated = raw["ownerBadges"][0]["metadataBadgeRenderer"][
                "style"] in ["BADGE_STYLE_TYPE_VERIFIED", "BADGE_STYLE_TYPE_VERIFIED_ARTIST"]
        except KeyError:
            self.owner_is_vereficated = False
        self.chapters: Optional[List[SearchChapter]] = None
        try:
            self.chapters = [
                SearchChapter(x["macroMarkersListItemRenderer"], net_obj, it)
                for x in raw["expandableMetadata"][
                    "expandableMetadataRenderer"]["expandedContent"]["horizontalCardListRenderer"]["cards"]
            ]
        except KeyError:
            self.chapters = None

    def __repr__(self) -> str:
        return f"<VideoSearchResult {self.video_id} title=\"{self.title[:100]}\"/>"


class SearchShortInfo(PlayableBaseSearchInfo):
    def __init__(self, raw: str, net_obj: net.SessionRequest, it: innertube.InnerTube):
        super().__init__(raw)
        self.thumbnails: thumbnail.ThumbnailQuery = thumbnail.ThumbnailQuery(raw[
            "navigationEndpoint"]["reelWatchEndpoint"]["thumbnail"]["thumbnails"], net_obj)

    def __repr__(self) -> str:
        return f"<ShortSearchResult {self.video_id=} title=\"{self.title[:100]}\"/>"


class SearchPlaylistInfo(SearchResultInfo):
    def __init__(self, raw: str, net_obj: net.SessionRequest, it:innertube.InnerTube):
        super().__init__(raw)
        self.title: str = raw["title"]["simpleText"]
        self.playlist_id: str = raw["playlistId"]
        self.video_count: Optional[int] = raw.get("videoCount")
        self.thumbnails: thumbnail.ThumbnailQuery(raw["thumbnails"]["thumbnails"], net_obj)
        self._other_thumbnails: thumbnail.ThumbnailQuery(raw["thumbnailRenderer"][
            "playlistVideoThumbnailRenderer"]["thumbnail"]["thumbnails"])
        self.videos_first: List[PlayableBaseSearchInfo] = [
            PlayableBaseSearchInfo(x["childVideoRenderer"])#TODO Playable or video?
            for x in raw["videos"]
        ]

    def __repr__(self) -> str:
        return f"<PlaylistSearchResult {self.title=}/>"


class SearchChannelInfo(SearchResultInfo):
    def __init__(self, raw: str, net_obj: net.SessionRequest, it: innertube.InnerTube):
        super().__init__(raw)
        self.channel_id: str = raw["channelId"]
        self.name: str = raw["title"]["simpleText"]
        self.thumbnails: thumbnail.ThumbnailQuery = thumbnail.ThumbnailQuery(raw["thumbnail"]["thumbnails"], net_obj)
        self.video_count: str = raw["videoCountText"]["simpleText"]
        self.is_subscribed: bool = raw["subscriptionButton"]["subscribed"]
        #TODO subscirbers count

        self.is_vereficated: bool = False
        try:
            self.is_vereficated = raw["ownerBadges"][0]["metadataBadgeRenderer"][
                "style"] in ["BADGE_STYLE_TYPE_VERIFIED", "BADGE_STYLE_TYPE_VERIFIED_ARTIST"]
        except KeyError:
            self.is_vereficated = False

    def __repr__(self) -> str:
        return f"<ChannelSearchResult {self.name=}/>"


class SearchDidYouMeanInfo:
    def __init__(self, raw):
        self.correct_arr: List[Tuple[str, bool]] = [(x["text"], x.get("italics", False)) for x in raw["correctedQuery"]["runs"]]
        self.corrected_query: str = raw["correctedQueryEndpoint"]["searchEndpoint"]["query"]
        self.corrected_words: str = " ".join([x[0] for x in self.correct_arr if x[1]])
        self.initial_query: str = raw["originalQuery"]["simpleText"]

    def __repr__(self)->str:
        return f"<DidYouMean \"{self.initial_query=}\" \"{self.corrected_query=}\" >"


class SearchPostInfo(SearchResultInfo):
    def __init__(self, raw: str, net_obj: net.SessionRequest, it: innertube.InnerTube):
        super().__init__(raw)
        self.post_id: str = raw["postId"]
        self.owner_name: str = helpers.get_text_by_runs(raw["authorText"])
        self.owner_id: str = raw["authorEndpoint"]["browseEndpoint"]["browseId"]
        self.owner_url: str = "https:/youtube.com"+raw["authorEndpoint"]["browseEndpoint"]["canonicalBaseUrl"]
        self.content: str = helpers.get_text_by_runs(raw["contentText"])
        self.published_time_text: str = helpers.get_text_by_runs(raw["publishedTimeText"])
        self.vote_count: str = raw["voteCount"]["simpleText"]
        self.like_is_toggled: bool = raw["actionButtons"][
            "commentActionButtonsRenderer"]["likeButton"]["toggleButtonRenderer"]["isToggled"]
        self.like_is_dissabled: bool = raw["actionButtons"][
            "commentActionButtonsRenderer"]["likeButton"]["toggleButtonRenderer"]["isDisabled"]
        self.dislike_is_toggled: bool = raw["actionButtons"]["commentActionButtonsRenderer"][
            "dislikeButton"]["toggleButtonRenderer"]["isToggled"]
        self.dislike_is_dissabled: bool = raw["actionButtons"]["commentActionButtonsRenderer"][
            "dislikeButton"]["toggleButtonRenderer"]["isDisabled"]
        self.attachment: Optional[thumbnail.ThumbnailQuery] = None
        if "backstageAttachment" in raw:
            self.attachment = thumbnail.ThumbnailQuery(raw["backstageAttachment"][
                "backstageImageRenderer"]["image"]["thumbnails"],
                net_obj)

    def __repr__(self) -> str:
        return f"<PostResult {self.post_id=}/>"


def _get_obj(
    x_raw,
    net_obj: net.SessionRequest,
    it: innertube.InnerTube
    ) -> Union[
        SearchDidYouMeanInfo,
        SearchVideoInfo,
        List[SearchPostInfo],
        SearchPlaylistInfo,
        SearchChannelInfo,
        List[SearchShortInfo],
        List[SearchVideoInfo],
        None]:

    obj = None
    if "videoRenderer" in x_raw:
        r = x_raw["videoRenderer"]
        obj = SearchVideoInfo(r, net_obj, it)
    elif "reelShelfRenderer" in x_raw:  # shorts list
        obj = []
        for short in x_raw["reelShelfRenderer"]["items"]:
            r = short["reelItemRenderer"]
            so = SearchShortInfo(r, net_obj, it)  # url=f"https://youtube.com/shorts/{r['videoId']}"
            obj.append(so)
    elif "radioRenderer" in x_raw:
        r = x_raw["radioRenderer"]
        obj = SearchPlaylistInfo(r, net_obj, it)  # url=f"https://youtube.com/watch?list={r['playlistId']}"
        # obj.title = r["title"]["simpleText"]
    elif "channelRenderer" in x_raw:
        r = x_raw["channelRenderer"]
        obj = SearchChannelInfo(r, net_obj, it)  # url="https://youtube.com"+r["navigationEndpoint"]["browseEndpoint"]["canonicalBaseUrl"]
        # obj.name = r["title"]["simpleText"]
    elif "shelfRenderer" in x_raw:  # people also watched
        r = x_raw["shelfRenderer"]["content"]
        obj = []
        if "verticalListRenderer" in r:
            for video_raw in r["verticalListRenderer"]["items"]:
                if "videoRenderer" in video_raw:
                    r = video_raw["videoRenderer"]
                    video = SearchVideoInfo(r, net_obj, it)  # r["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"] #TODO get url
                    # video.title = " ".join([x["text"] for x in r["title"]["runs"]])
                    # video.id =r["videoId"]
                    obj.append(video)
                else:
                    helpers.logger.warning(f"while search not found video renderer {video_raw}")
                    obj.append(None)
        if "horizontalListRenderer" in r:
            for post_raw in r["horizontalListRenderer"]["items"]:
                if "postRenderer" in post_raw:
                    obj.append(SearchPostInfo(post_raw["postRenderer"], net_obj, it))
                else:
                    helpers.logger.warning(f"while search not found postrenderer {post_raw}")
                    obj.append(None)
    elif "playlistRenderer" in x_raw:
        r = x_raw["playlistRenderer"]
        obj = SearchPlaylistInfo(r, net_obj, it)  # url="https://youtube.com"+r["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"]
    elif "backgroundPromoRenderer" in x_raw and x_raw["backgroundPromoRenderer"]["icon"]["iconType"] == "EMPTY_SEARCH":
        raise Exception("Empty search")
    elif "didYouMeanRenderer" in x_raw:  # TODO move up
        obj = SearchDidYouMeanInfo(x_raw["didYouMeanRenderer"])
    elif "showingResultsForRenderer" in x_raw:
        obj = SearchDidYouMeanInfo(x_raw["showingResultsForRenderer"])
    else:
        helpers.logger.warning(f"while search not found video renderer {x_raw}")
        return None
    return obj


class SearchResponse:
    def __init__(self, raw, net_obj: net.SessionRequest, it: innertube.InnerTube):
        self.estimated_results: str = raw.get("estimatedResults")
        self.content: Iterable[
            Union[
                SearchDidYouMeanInfo,
                SearchVideoInfo,
                List[SearchPostInfo],
                SearchPlaylistInfo,
                SearchChannelInfo,
                List[SearchShortInfo],
                List[SearchVideoInfo],
                None
                ]
            ] = None
        raw_content = raw["onResponseReceivedCommands"][0]["appendContinuationItemsAction"]["continuationItems"]
        self.continuation: Optional[str] = None
        self.content = (_get_obj(x, net_obj, it) for x in raw_content[0]["itemSectionRenderer"]["contents"])
        try:
            self.continuation = raw_content[1]["continuationItemRenderer"]["continuationEndpoint"][
                "continuationCommand"]["token"]
        except KeyError:
            self.continuation = None
        except IndexError:
            self.continuation = None


class SearchResponseFirst:
    def __init__(self, raw, net_obj: net.SessionRequest, it: innertube.InnerTube):
        self.content: Iterable[
            Union[
                SearchDidYouMeanInfo,
                SearchVideoInfo,
                List[SearchPostInfo],
                SearchPlaylistInfo,
                SearchChannelInfo,
                List[SearchShortInfo],
                List[SearchVideoInfo],
                None
            ]
        ] = None
        self.continuation: Optional[str] = None
        self.refinements: Optional[List[str]] = raw.get('refinements')
        self.estimated_results: str = raw.get("estimatedResults")
        self._sub_menu_raw: dict = raw["contents"]["twoColumnSearchResultsRenderer"]["primaryContents"][
            "sectionListRenderer"]["subMenu"]
        self.content = (
            _get_obj(x, net_obj, it)
            for x in raw["contents"]["twoColumnSearchResultsRenderer"]["primaryContents"][
                "sectionListRenderer"]["contents"][0]["itemSectionRenderer"]["contents"]
        )
        try:
            self.continuation = raw["contents"]["twoColumnSearchResultsRenderer"]["primaryContents"][
                "sectionListRenderer"]["contents"][1]["continuationItemRenderer"]["continuationEndpoint"][
                "continuationCommand"]["token"]
        except KeyError:
            self.continuation = None
        except IndexError:
            self.continuation = None


SearchType = TypeVar("SearchType", bound="Search")
class Search():
    def __init__(self, query: str, net_obj: net.SessionRequest, it: innertube.InnerTube, continuaion: Optional[str] = None):
        self.query: str = query
        self.net_obj: net.SessionRequest = net_obj
        self.it: innertube.InnerTube = it
        self.continuation = continuaion
        self.current_continuation = self.continuation
        self.f = True

    def __aiter__(self) -> SearchType:
        return self

    async def __anext__(self) -> Union[SearchResponseFirst, SearchResponse]:
        crf = None
        if self.f:
            self.f = False
            crf = SearchResponseFirst(await self.it.search(self.query), self.net_obj, self.it)
        else:
            crf = SearchResponse(await self.it.search(None, self.current_continuation), self.net_obj, self.it)
        self.current_continuation = crf.continuation
        return crf

def get_search(query:str, net_obj:net.SessionRequest, it:innertube.InnerTube) -> Search:
    return Search(query, net_obj, it)