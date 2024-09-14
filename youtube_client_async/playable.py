import time
from abc import ABC
from datetime import datetime
from functools import cached_property
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from . import (
    base_youtube,
    caption,
    chapter,
    comment,
    extract,
    helpers,
    innertube,
    net,
    stream,
    thumbnail,
)
from .helpers import get_from_dict


class PlayableBase(base_youtube.BaseYoutube, ABC):
    """objects contains video_id like video shorts live"""
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

        base_youtube.BaseYoutube.__init__(self, url, html, net_obj, it, initial_data, ytcfg)
        self._initial_player: Optional[dict] = initial_player
        self._js_obj: Optional[str] = js if js else None
        self._js_url_obj: Optional[str] = js_url if js_url else None
        self.video_id = extract.video_id(self.parsed_url, self.parsed_query)
        self._signature_timestamp = None
        self._web_initial_player = None
        self._ios_initial_player = None

    @property
    def initial_player(self):
        if self._initial_player:
            return self._initial_player
        html = self.html
        current_time = time.time()
        self._initial_player = extract.get_ytplayer_config(html)
        delta_time = time.time() - current_time
        helpers.logger.info(f"loaded initial_player in {delta_time:.2f} seconds")
        return self._initial_player

    def _get_js_url(self) -> str:
        if self._js_url_obj:
            return self._js_url_obj
        # if self.age_restricted:
        #     self._js_url = extract.js_url(self.embed_html)
        self._js_url_obj = extract.js_url(self.html)
        return self._js_url_obj

    async def _get_js(self) -> str:
        if self._js_obj:
            return self._js_obj
        self._js_obj = await self.net_obj.get_text(self._get_js_url())
        return self._js_obj

    @property
    def is_owner_view(self) -> bool:
        return get_from_dict(self.initial_player, "videoDetails|isOwnerViewing")

    @property
    def playability_status(self) -> str:
        return get_from_dict(self.initial_player, "playabilityStatus|status")

    @property
    def playable_in_embed(self) -> bool:
        return get_from_dict(self.initial_player, "playabilityStatus|playableInEmbed")

    @property
    def error_reason(self) -> Optional[str]:
        return self.initial_player["playabilityStatus"].get("reason")

    @property
    def embed_info(self) -> dict:
        """
        examle
        {
            "iframeUrl":"https://www.youtube.com/embed/4JfSdYQJaR4",
            "width":1280,
            "height":720
        }"""
        return get_from_dict(self.initial_player, "microformat|playerMicroformatRenderer|embed")

    @property
    def title(self) -> str:
        return get_from_dict(self.initial_player, "videoDetails|title")

    @property
    def description(self) -> str:
        return get_from_dict(self.initial_player, "videoDetails|shortDescription")

    @property
    def view_count(self) -> str:
        """view count in str not int"""
        return get_from_dict(self.initial_player, "microformat|playerMicroformatRenderer|viewCount")

    @property
    def is_shorts_eligible(self) -> bool:
        return self.initial_player["microformat"]["playerMicroformatRenderer"].get("isShortsEligible", False)

    @property
    def is_private(self) -> bool:
        return get_from_dict(self.initial_player, "videoDetails|isPrivate")

    @property
    def lenght(self) -> int:
        """Lenght of video in seconds"""
        return int(get_from_dict(self.initial_player, "videoDetails|lengthSeconds"))

    @property
    def owner_name(self) -> str:
        return get_from_dict(self.initial_player, "videoDetails|author")

    @property
    def owner_url(self) -> str:
        return get_from_dict(
            self.initial_player,
            "microformat|playerMicroformatRenderer|ownerProfileUrl"
        )

    @property
    def owner_id(self) -> str:
        return get_from_dict(
            self.initial_player,
            "microformat|playerMicroformatRenderer|externalChannelId",
        )

    @property
    def allow_rating(self) -> bool:
        return get_from_dict(self.initial_player, "videoDetails|allowRatings")

    @property
    def category(self) -> str:
        return get_from_dict(
            self.initial_player,
            "microformat|playerMicroformatRenderer|category"
        )

    @property
    def keywords(self) -> List[str]:
        return get_from_dict(
            self.initial_player,
            "videoDetails|keywords",
            default=[],
            throw_ex=False
        )

    @property
    def is_family_safe(self) -> bool:
        return get_from_dict(
            self.initial_player,
            "microformat|playerMicroformatRenderer|isFamilySafe"
        )

    @property
    def available_countries(self) -> List[str]:
        return get_from_dict(
            self.initial_player,
            "microformat|playerMicroformatRenderer|availableCountries",
            throw_ex=False,
            default=[],
        )

    # TODO here
    @property
    def is_unplugged_corpus(self) -> bool:
        return get_from_dict(
            self.initial_player,
            "videoDetails|isUnpluggedCorpus"
        )

    @property
    def is_crawlable(self) -> bool:
        return get_from_dict(self.initial_player, "videoDetails|isCrawlable")

    @property
    def is_unlisted(self) -> bool:
        return get_from_dict(
            self.initial_player,
            "microformat|playerMicroformatRenderer|isUnlisted"
        )

    @property
    def has_ypc_metadata(self) -> bool:
        return get_from_dict(
            self.initial_player,
            "microformat|playerMicroformatRenderer|hasYpcMetadata"
        )

    @property
    def publish_date(self) -> datetime:
        text = get_from_dict(
            self.initial_player,
            "microformat|playerMicroformatRenderer|publishDate"
        )
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S%z")

    @property
    def upload_date(self) -> datetime:
        text = get_from_dict(
            self.initial_player,
            "microformat|playerMicroformatRenderer|uploadDate"
        )
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S%z")

    @property
    def was_live(self) -> bool:
        return "liveBroadcastDetails" in self.initial_player["microformat"]["playerMicroformatRenderer"]

    @property
    def is_live_content(self) -> bool:
        return self.initial_player["videoDetails"]["isLiveContent"]

    @property
    def is_live_now(self) -> bool:
        return self.initial_player["videoDetails"].get("isLive", False)

    @property
    def start_live(self) -> Optional[datetime]:
        if self.was_live:
            text = self.initial_player["microformat"]["playerMicroformatRenderer"]["liveBroadcastDetails"].get("startTimestamp")
            if text:
                return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S%z")
        return None

    @property
    def end_live(self) -> Optional[datetime]:
        if self.was_live:
            text = self.initial_player["microformat"]["playerMicroformatRenderer"]["liveBroadcastDetails"].get("endTimestamp")
            if text:
                return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S%z")
        return None

    @property
    def thumbnails(self) -> Optional[thumbnail.ThumbnailQuery]:
        raw = get_from_dict(self.initial_player, "videoDetails|thumbnail|thumbnails")
        try:
            raw += self.initial_player["microformat"]["playerMicroformatRenderer"][
                "thumbnail", "thumbnails"]
        except KeyError:
            pass

        if raw and len(raw) == 0:
            return None
        return thumbnail.ThumbnailQuery(raw, self.net_obj)

    @property
    def has_captions(self) -> bool:
        return "captions" in self.initial_player

    @property
    def translation_languages(self) -> Dict[str, str]:
        translationLanguages = dict()
        cap = self.initial_player.get("captions")
        if cap is None:
            return dict()
        for x in get_from_dict(cap, "playerCaptionsTracklistRenderer|translationLanguages"):
            try:
                translationLanguages[x["languageCode"]] = x["languageName"]["simpleText"]
            except KeyError:
                translationLanguages[x["languageCode"]] = helpers.get_text_by_runs(x["languageName"])
        return translationLanguages

    async def get_captions(self) -> Optional[caption.CaptionQuery]:
        ip = None
        if self._web_initial_player:
            ip = self._web_initial_player
        else:
            self._web_initial_player = await innertube.InnerTube(
                self.net_obj,
                "WEB",
                self.it.use_oauth,
                self.it.use_oauth,
                self.it.token_file,
                self.it.gl,
                self.it.hl
            ).player(self.video_id)
            ip = self._web_initial_player
        cap = ip.get("captions")
        captions = []
        if cap is None:
            return None
        for x in get_from_dict(cap, "playerCaptionsTracklistRenderer|captionTracks"):
            captions.append(caption.Caption(x, self.translation_languages, self.net_obj))
        if len(captions) == 0:
            return None
        return caption.CaptionQuery(captions, self.translation_languages)

    async def _get_signature_timestamp(self) -> dict:
        """WEB clients need to be signed with a signature timestamp.

        The signature is found inside the player's base.js.

        :rtype: Dict
        """
        if not self._signature_timestamp:
            self._signature_timestamp = {
                'playbackContext': {
                    'contentPlaybackContext': {
                        'signatureTimestamp': extract.signature_timestamp(await self._get_js())
                    }
                }
            }
        return self._signature_timestamp

    async def get_streams(self) -> stream.StreamQuery:
        # self.it.innertube_context.update(await self._get_signature_timestamp())
        # new_player_info = await self.it.player(self.video_id)
        ip = None
        if self._ios_initial_player:
            ip = self._ios_initial_player
        else:
            self._ios_initial_player = await innertube.InnerTube(
                self.net_obj,
                "IOS",
                self.it.use_oauth,
                self.it.use_oauth,
                self.it.token_file,
                self.it.gl,
                self.it.hl
            ).player(self.video_id)
            ip = self._ios_initial_player

        stream_manifest = extract.apply_descrambler(ip["streamingData"])

        extract.apply_signature(stream_manifest, ip, await self._get_js(), self._get_js_url())
        stream_objs = [stream.Stream(s_raw, self.lenght, self.title, self.net_obj) for s_raw in stream_manifest]
        return stream.StreamQuery(stream_objs)
