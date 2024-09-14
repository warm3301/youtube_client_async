from dataclasses import dataclass
from typing import List, NamedTuple, Optional
from urllib import parse

from . import chapter, comment, extract, helpers, innertube, net, playable, thumbnail


def get_video_url(id: str) -> str:
    return f"https://youtube.com/watch?v={id}"


def get_video_embed_url(id: str) -> str:
    return f"https://www.youtube.com/embed/{id}"


def get_video_id(url: str) -> str:
    parsed_url = parse.urlparsel(url)
    parsed_query = parse.parse_qs(parsed_url.query)
    return extract.video_id(parsed_url, parsed_query)


class License(NamedTuple):
    name: str
    url: str


class VideoCategory:
    def __init__(self, raw, net_obj: net.SessionRequest):
        self.raw = raw
        self.net_obj: net.SessionRequest = net_obj
        self.title: str = helpers.get_text_by_runs(raw["title"]) if "runs" in raw["title"] else raw["title"]["simpleText"]
        self.url: str = "https://youtube.com" + raw["endpoint"]["commandMetadata"]["webCommandMetadata"]["url"]
        self.browse_id: str = raw["endpoint"]["browseEndpoint"]["browseId"]

    @property
    def thumbnails(self) -> thumbnail.ThumbnailQuery:
        return thumbnail.ThumbnailQuery(self.raw["thumbnail"]["thumbnails"],self.net_obj)

    def __repr__(self) -> str:
        return f"<VideoCategory {self.title}/>"


@dataclass(frozen=True)
class MusicMetadata:
    title: str
    # orientation:str
    # sizingRule:str
    subtitle: str
    secondary_subtitle: str
    thumbnail: thumbnail.Thumbnail
    # all_info:Optional[str]
    owner_id: str

    def __repr__(self) -> str:
        return f"<youtube_client_async.video.MusicMetadata {self.subtitle} \"{self.title}\" />"


class ShortUseVideo:
    def __init__(self, raw, net_obj: net.SessionRequest):
        self.raw = raw
        self.net_obj: net_obj = net_obj

    @property
    def title(self) -> str:
        try:
            try:
                return helpers.get_text_by_runs(self.raw["title"])
            except KeyError:
                return self.raw["title"]["simpleText"]
        except KeyError:
            return self.raw["headline"]["simpleText"]

    @property
    def thumbnails(self) -> thumbnail.ThumbnailQuery:
        return thumbnail.ThumbnailQuery(self.raw["thumbnail"]["thumbnails"], self.net_obj)

    @property
    def reel_thumbnails(self) -> thumbnail.ThumbnailQuery:
        return thumbnail.ThumbnailQuery(
            self.raw["navigationEndpoint"]["reelWatchEndpoint"]["thumbnail"]["thumbnails"],
            self.net_obj
        )

    @property
    def view_count(self) -> str:
        return self.raw["viewCountText"]["simpleText"]

    @property
    def id(self) -> str:
        return self.raw["navigationEndpoint"]["reelWatchEndpoint"]["videoId"]

    @property
    def url(self) -> str:
        return "https://youtube.com" + self.raw["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"]

    @property
    def video_type(self) -> Optional[str]:
        try:
            return self.raw["videoType"]
        except KeyError:
            return None

    def __repr__(self) -> str:
        return f"<Short what use video  \"{self.title}\"/>"

    # lenght via accessibility accessibilityData label


class VideoBase(playable.PlayableBase):
    """Class for video on youtube"""

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

        super().__init__(
            url,
            html,
            net_obj,
            it,
            initial_player,
            initial_data,
            ytcfg,
            js_url,
            js
        )

        self.watch_url = get_video_url(self.video_id)
        self.embed_url = get_video_embed_url(self.video_id)
        self.playlist_id: str = None
        try:
            self.playlist_id = extract.playlist_id(self.parsed_url, self.parsed_query)
        except:
            pass
        if self.playlist_id is None:
            helpers.logger.info(f"can't extract id {self.url}")

    def __repr__(self) -> str:
        return f"<youtube_client_async.BaseYoutubePlayable {self.url=} >"

    @property
    def time_from_url(self) -> int:
        """get time from arg in url named 't' in seconds"""
        return extract.time_from_url(self.parsed_query)

    @property
    def autoplay_enabled(self) -> Optional[bool]:
        ant = self.initial_data["playerOverlays"]["playerOverlayRenderer"].get("autonavToggle")
        if ant is None:
            return None
        return ant["autoplaySwitchButtonRenderer"]["enabled"]

    @property
    def _primary_renderer(self) -> dict:
        return self.initial_data["contents"]["twoColumnWatchNextResults"]["results"][
            "results"]["contents"][0]["videoPrimaryInfoRenderer"]

    @property
    def tags(self) -> Optional[str]:
        try:  # url | is geotag
            return helpers.get_text_by_runs(self._primary_renderer["superTitleLink"])
        except KeyError:
            return None

    @property
    def _rating_buttons(self) -> dict:
        return self._primary_renderer["videoActions"]["menuRenderer"][
            "topLevelButtons"][0]["segmentedLikeDislikeButtonViewModel"]

    @property
    def _default_like_view_model(self) -> dict:
        return self._rating_buttons["likeButtonViewModel"]["likeButtonViewModel"][
            "toggleButtonViewModel"]["toggleButtonViewModel"]["defaultButtonViewModel"]["buttonViewModel"]

    @property
    def likes_count(self) -> str:
        return self._default_like_view_model["accessibilityText"]

    @property
    def like_status(self) -> str:
        return self._rating_buttons["likeButtonViewModel"]["likeButtonViewModel"]["likeStatusEntity"]["likeStatus"]

    @property
    def like_is_disabled(self) -> str:
        return self._rating_buttons["likeButtonViewModel"]["likeButtonViewModel"][
            "toggleButtonViewModel"]["toggleButtonViewModel"]["isTogglingDisabled"]

    @property
    def money_hand(self) -> bool:
        try:
            return (
                self.initial_player["paidContentOverlay"]["paidContentOverlayRenderer"][
                    "icon"]["iconType"]== "MONEY_HAND"
            )
        except KeyError:
            return False

    @property
    def _chan_info(self) -> dict:
        return self.initial_data["contents"]["twoColumnWatchNextResults"]["results"][
            "results"]["contents"][1]["videoSecondaryInfoRenderer"]

    @property
    def owner_subscribers_count(self) -> Optional[str]:
        try:
            return self._chan_info["owner"]["videoOwnerRenderer"][
                "subscriberCountText"]["simpleText"]
        except KeyError:
            return None

    @property
    def owner_is_vereficated(self) -> bool:
        try:
            return self._chan_info["owner"]["videoOwnerRenderer"]["badges"][0][
                "metadataBadgeRenderer"]["style"] in [
                "BADGE_STYLE_TYPE_VERIFIED",
                "BADGE_STYLE_TYPE_VERIFIED_ARTIST",
            ]
        except:
            return False

    @property
    def owner_thumbnails(self) -> thumbnail.ThumbnailQuery:
        return thumbnail.ThumbnailQuery(
            self._chan_info["owner"]["videoOwnerRenderer"]["thumbnail"]["thumbnails"],
            self.net_obj,
        )

    @property
    def is_subscribed(self) -> bool:
        try:
            return self._chan_info["subscribeButton"]["subscribeButtonRenderer"][
                "subscribed"
            ]
        except:
            return False

    @property
    def subscribe_button_is_enabled(self) -> bool:
        return self._chan_info["subscribeButton"]["subscribeButtonRenderer"]["enabled"]

    @property
    def subscribe_type(self) -> str:
        return self._chan_info["subscribeButton"]["subscribeButtonRenderer"]["type"]

    @property
    def subscribe_show_preferences(self) -> bool:
        return self._chan_info["subscribeButton"]["subscribeButtonRenderer"]["showPreferences"]

    @property
    def _notification(self) -> dict:
        return self._chan_info["subscribeButton"]["subscribeButtonRenderer"][
            "notificationPreferenceButton"]["subscriptionNotificationToggleButtonRenderer"]

    @property
    def notification_current_state(self) -> int:
        return self._notification["currentStateId"]

    @property
    def _categories(self)->List[VideoCategory]:
        categories = []
        mrkr = self.initial_data["contents"]["twoColumnWatchNextResults"]["results"]["results"]["contents"][1]["videoSecondaryInfoRenderer"][
            "metadataRowContainer"]["metadataRowContainerRenderer"]
        if not "rows" in mrkr:
            return categories
        mrkr = mrkr["rows"][0]
        if not "richMetadataRowRenderer" in mrkr:
            return categories
        for raw in mrkr["richMetadataRowRenderer"]["contents"]:
            categories.append(VideoCategory(raw["richMetadataRenderer"],self.net_obj))
        return categories

    @property
    def creative_commons(self) -> Optional[License]:
        """Return tuple info about licence and url to full information
        If licence of video is not creative commons function return None

        Returns:
            Optional[Tuple[str,str]]: first is text, second is url.
        """
        mrkr = self.initial_data["contents"]["twoColumnWatchNextResults"]["results"][
            "results"]["contents"][1]["videoSecondaryInfoRenderer"]["metadataRowContainer"][
            "metadataRowContainerRenderer"]
        if "rows" not in mrkr:
            return None
        for row in mrkr["rows"]:
            try:
                value = row["metadataRowRenderer"]["contents"][0]["runs"][0]
                return License(
                    name=value["text"],
                    url=value["navigationEndpoint"]["urlEndpoint"]["url"],
                )
            except KeyError:
                return None
    


class Video(VideoBase):
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

        super().__init__(
            url,
            html,
            net_obj,
            it,
            initial_player,
            initial_data,
            ytcfg,
            js_url,
            js
        )
    
    @property
    def playback_mode(self) -> Optional[str]:
        mp = self.initial_player["playabilityStatus"].get("miniplayer")
        if mp is None:
            return None
        return mp["miniplayerRenderer"]["playbackMode"]

    @property
    def _comment_data(self) -> Optional[dict]:
        try:
            return self.initial_data["contents"]["twoColumnWatchNextResults"]["results"]["results"]["contents"][-2][
                "itemSectionRenderer"]["contents"][0]["commentsEntryPointHeaderRenderer"]
        except KeyError:
            return None
        except IndexError:
            return None

    @property
    def comment_teaser(self) -> Optional[comment.TeaserComment]:
        cd = self._comment_data
        if cd:
            return comment.TeaserComment(
                cd["contentRenderer"]["commentsEntryPointTeaserRenderer"],
                self.net_obj,
            )
        return None

    @property
    def comment_continuation_token(self) -> Optional[str]:
        try:
            return self.initial_data["contents"]["twoColumnWatchNextResults"]["results"][
                "results"]["contents"][-1]["itemSectionRenderer"]["contents"][0][
                "continuationItemRenderer"]["continuationEndpoint"][
                "continuationCommand"]["token"]
        except KeyError:
            return None
        except IndexError:
            return None

    @property
    def comment_count(self) -> Optional[str]:
        """this is not a specific value"""
        # .engagementPanels[-1].engagementPanelSectionListRenderer.header.
        # .engagementPanelTitleHeaderRenderer.contextualInfo.runs[0].text
        cd = self._comment_data
        if cd is None:
            return None
        try:
            return self._comment_data["commentCount"]["simpleText"]
        except KeyError:
            return None

    async def _get_comments_response(
        self, sort_by: comment.CommentSortedType = comment.CommentSortedType.top
    ) -> Optional[comment.CommentResponse]:

        cct = self.comment_continuation_token
        if cct is None:
            return None
        return await comment._get_comment_response(
            self.comment_continuation_token, sort_by, self.net_obj, self.it
        )

    async def get_comments_response_getter(
        self, sort_by: comment.CommentSortedType = comment.CommentSortedType.top
    ) -> Optional[comment.CommentResponseGetter]:
        fr = await self._get_comments_response(sort_by)
        if fr is None:
            return None
        return comment.CommentResponseGetter(fr, self.net_obj, self.it)

    def _find_engagement_panel(self, panel_id):
        for x in self.initial_data["engagementPanels"][1:]:
            if x["engagementPanelSectionListRenderer"].get("panelIdentifier") == panel_id:
                return x
        return None

    @property
    def chapters_is_generated(self) -> bool:
        return self._find_engagement_panel("engagement-panel-macro-markers-auto-chapters") is not None

    @property
    def chapters(self) -> List[chapter.Chapter]:
        chapters = []
        mkb = None
        try:
            mkb = self.initial_data["playerOverlays"]["playerOverlayRenderer"][
                "decoratedPlayerBarRenderer"]["decoratedPlayerBarRenderer"]["playerBar"][
                "multiMarkersPlayerBarRenderer"]
        except KeyError:
            return chapters
        generated_chapters = False
        # If description chapters is none, then search auto chapters
        en_panel = self._find_engagement_panel("engagement-panel-macro-markers-description-chapters")
        if en_panel is None:
            en_panel = self._find_engagement_panel("engagement-panel-macro-markers-auto-chapters")
            generated_chapters = True
        if en_panel is None:
            return chapters
        en_r = mkb["markersMap"][0]["value"]
        if "chapters" in en_r:
            en_r = en_r["chapters"]
        elif "markers" in en_r:
            en_r = mkb["markersMap"][1]["value"]["chapters"]
        else:
            raise NotImplementedError()
        for i, x in enumerate(en_r):
            cr = x["chapterRenderer"]
            chapter_panel = en_panel["engagementPanelSectionListRenderer"]["content"][
                "macroMarkersListRenderer"]["contents"][i + 1 if generated_chapters else i][
                "macroMarkersListItemRenderer"]
            ch = chapter.Chapter()
            ch.title = cr["title"]["simpleText"]
            ch.start_range_ms = cr["timeRangeStartMillis"]
            ch.time = chapter_panel["timeDescription"]["simpleText"]
            ch.thumbnails = thumbnail.ThumbnailQuery(cr["thumbnail"]["thumbnails"], self.net_obj)
            ch.time_description = chapter_panel["timeDescriptionA11yLabel"]
            chapters.append(ch)
        return chapters

    @property
    def explicit_lyrics(self) -> Optional[str]:
        try:
            return self.initial_data["contents"]["twoColumnWatchNextResults"][
                "results"]["results"]["contents"][1]["videoSecondaryInfoRenderer"][
                "metadataRowContainer"]["metadataRowContainerRenderer"][
                "rows"][0]["metadataRowRenderer"]["contents"][0]["simpleText"]  # "Explicit lyrics"
        except KeyError:
            return None
    @property
    def music_metadata(self) -> Optional[MusicMetadata]:
        hcvr = None
        for x in self._find_engagement_panel("engagement-panel-structured-description")["engagementPanelSectionListRenderer"][
            "content"]["structuredDescriptionContentRenderer"]["items"]:
            if "horizontalCardListRenderer" in x:
                hcvr = x["horizontalCardListRenderer"]
                break
        if hcvr == None or len(hcvr["cards"])==0 or "macroMarkersListItemRenderer" in hcvr["cards"][0]:
            return None
        _ = hcvr["header"]["richListHeaderRenderer"]["title"]["simpleText"] # music
        count = None
        try:
            count = hcvr["header"]["richListHeaderRenderer"]["subtitle"]["simpleText"] # count 1
        except KeyError:
            pass
        card = hcvr["cards"][0]["videoAttributeViewModel"]

        # orientation = card["orientation"]
        # sizingRule = card["sizingRule"]
        title = card["title"]
        subtitle = card["subtitle"]#TODO playlist id, url
        secondary_subtitle = card["secondarySubtitle"]["content"]
        thumb = thumbnail.Thumbnail({"url":card["image"]["sources"][0]["url"]},self.net_obj)
        owner_id = hcvr["footerButton"]["buttonViewModel"]["onTap"]["innertubeCommand"]["browseEndpoint"]["browseId"]
        #footerButton.buttonViewModel.titleFormatted.content 'music'
        owner_url = "https://youtube.com" + hcvr["footerButton"]["buttonViewModel"]["onTap"]["innertubeCommand"][
            "commandMetadata"]["webCommandMetadata"]["url"]

        # all_info = None
        # dmessages = card["overflowMenuOnTap"]["innertubeCommand"]["confirmDialogEndpoint"]["content"][
        #     "confirmDialogRenderer"]["dialogMessages"][0]
        # if dmessages and len(dmessages)>0:
        #     all_info = " ".join([x["text"] for x in  dmessages['runs']])
        return MusicMetadata(title, subtitle, secondary_subtitle, thumbnail, owner_id)

    @property
    def shorts_use_video(self)->List[ShortUseVideo]:
        res = []

        #find reelShelfRenderer
        rsr = None
        for x in self._find_engagement_panel("engagement-panel-structured-description")["engagementPanelSectionListRenderer"][
            "content"]["structuredDescriptionContentRenderer"]["items"]:
            if "reelShelfRenderer" in x:
                rsr = x["reelShelfRenderer"]
                break
        if rsr == None:
            return res
        for x in rsr["items"]:
            res.append(ShortUseVideo(x["reelItemRenderer"],self.net_obj))
        return res
    # can get about channel in engagement-panel-structured-description  videoDescriptionInfocardsSectionRenderer.creatorAboutButton


async def get_video(
    url: str,
    net_obj: net.SessionRequest,
    it: innertube.InnerTube,
    html: Optional[str] = None,
    initial_player: Optional[dict] = None,
    initial_data: Optional[dict] = None,
    ytcfg: Optional[dict] = None,
    js_url: Optional[str] = None,
    js: Optional[str] = None,
) -> Video:

    # If url is "https://www.youtube.com/shorts/{id}" it generic another initial_data,
    # that can descibe in other class
    parsed_url = parse.urlparse(url)
    if parsed_url.path.startswith("/shorts"):
        url = (
            get_video_url(extract.short_id(url)) + ""
            if not parsed_url.query
            else f"?{parsed_url.query}"
        )
    c_html = html if html else await net_obj.get_text(url)
    ip = await it.player(extract.video_id(parsed_url, parse.parse_qs(parsed_url.query))) if not initial_player else initial_player
    return Video(url, c_html, net_obj, it, ip, initial_data, ytcfg, js_url, js)
