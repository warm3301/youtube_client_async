from typing import Optional

from . import comment, extract, helpers, innertube, net, playable, video


def get_short_id(url: str) -> str:
    return extract.short_id(url)


class Short(playable.PlayableBase):
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
        self.video_watch_url: str = video.get_video_url(self.video_id)
        self.embed_url: str = video.get_video_embed_url(self.video_id)

    async def get_playable_object(self) -> video.Video:
        return await video.get_video(self.url, self.net_obj, self.it)

    @property
    def comment_count(self) -> Optional[str]:
        try:
            return helpers.get_text_by_runs(self.initial_data["engagementPanels"][0][
                        "engagementPanelSectionListRenderer"]["header"][
                        "engagementPanelTitleHeaderRenderer"]["contextualInfo"])
        except KeyError:
            return None

    async def _get_comments_response(
        self, sort_by: comment.CommentSortedType = comment.CommentSortedType.top
    ) -> Optional[comment.CommentResponse]:

        continuation: str = self.initial_data["engagementPanels"][0][
            "engagementPanelSectionListRenderer"]["header"][
            "engagementPanelTitleHeaderRenderer"]["menu"]["sortFilterSubMenuRenderer"][
            "subMenuItems"][sort_by.value]["serviceEndpoint"]["continuationCommand"]["token"]
        if continuation is None:
            return None
        return await comment._get_comment_response(
            continuation,
            sort_by,
            self.net_obj,
            self.it,
            comment.GetCommentMethod.browse,
            False,
        )

    async def get_comments_response_getter(
        self, sort_by: comment.CommentSortedType = comment.CommentSortedType.top
    ) -> Optional[comment.CommentResponseGetterWithoutFirstInfo]:
        """Always CommentResponse not CommentResponseFirst"""

        fr = await self._get_comments_response(sort_by)
        if fr:
            return None
        return comment.CommentResponseGetterWithoutFirstInfo(
            fr, self.net_obj, self.it, comment.GetCommentMethod.browse
        )


async def get_short(
    url: str,
    net_obj: net.SessionRequest,
    it: innertube.InnerTube,
    html: Optional[str] = None,
    initial_player: Optional[dict] = None,
    initial_data: Optional[dict] = None,
    ytcfg: Optional[dict] = None,
    js_url: Optional[str] = None,
    js: Optional[str] = None
) -> Short:

    c_html = html if html else await net_obj.get_text(url)
    return Short(url, c_html, net_obj, it, initial_player, initial_data, ytcfg, js_url, js)


async def get_video_short(
    url: str,
    net_obj: net.SessionRequest,
    it: innertube.InnerTube,
    html: Optional[str] = None,
    initial_player: Optional[dict] = None,
    initial_data: Optional[dict] = None,
    ytcfg: Optional[dict] = None,
    js_url: Optional[str] = None,
    js: Optional[str] = None
) -> video.Video:

    return await video.get_video(url, net_obj, it, html, initial_player, initial_data, ytcfg, js_url, js)
