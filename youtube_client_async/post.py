from abc import ABC
from typing import List, Optional, Union
from urllib import parse

from . import (
    base_info,
    base_youtube,
    comment,
    extract,
    helpers,
    innertube,
    net,
    thumbnail,
)


def get_url(id: str) -> str:
    return f"https://www.youtube.com/post/{id}"


def get_post_id(url: str) -> str:
    parsed_url = parse.urlparse(url)
    return extract.post_id(parsed_url)


class PostAttachment(ABC):
    pass


class ImagePostAttachment(PostAttachment):
    def __init__(self, raw: dict, net_obj: net.SessionRequest, it: innertube.InnerTube):
        self.content: thumbnail.ThumbnailQuery = thumbnail.ThumbnailQuery(raw, net_obj)

    def __repr__(self) -> str:
        return f"<youtube_client_async.post.ImageAttachment>"


class MultiImagePostAttachment(PostAttachment):
    def __init__(self, raw: dict, net_obj: net.SessionRequest, it: innertube.InnerTube):
        self.content: List[thumbnail.ThumbnailQuery] = [
            ImagePostAttachment(x["backstageImageRenderer"]["image"]["thumbnails"], net_obj, it)
            for x in raw
        ]

    def __repr__(self) -> str:
        return f"<youtube_client_async.post.MultiImageAttachment>"


class AnotherVideoPostAttachment(PostAttachment, base_info.VideoInfo):
    def __init__(self, raw: dict, net_obj: net.SessionRequest, it: innertube.InnerTube):
        base_info.VideoInfo.__init__(self, raw, net_obj, it)
        raw_th = raw["channelThumbnailSupportedRenderers"]["channelThumbnailWithLinkRenderer"]["thumbnail"]["thumbnails"]
        if "avatar" in raw:
            raw_th += raw["avatar"]["decoratedAvatarViewModel"]["avatar"]["avatarViewModel"]["image"]["sources"]
        self.owner_avatar: thumbnail.ThumbnailQuery = thumbnail.ThumbnailQuery(raw_th, net_obj)
        owner_navigation_item = raw["ownerText"]["runs"][0]["navigationEndpoint"]
        self.owner_id: str = owner_navigation_item["browseEndpoint"]["browseId"]
        self.owner_url: str = (
            "https://youtube.com"
            + owner_navigation_item["browseEndpoint"]["canonicalBaseUrl"]
        )
        self.owner_name: str = helpers.get_text_by_runs(raw["ownerText"])

    def __repr__(self) -> str:
        return f"<youtube_client_async.post.AnotherVideoAttachment>"


class SelfVideoPostAttachment(PostAttachment, base_info.VideoInfo):
    def __init__(self, raw: dict, net_obj: net.SessionRequest, it: innertube.InnerTube):
        base_info.VideoInfo.__init__(self, raw, net_obj, it)

    def __repr__(self) -> str:
        return f"<youtube_client_async.post.SelfVideoAttachment>"


class VideoErrorPostAttachment(PostAttachment):
    def __init__(self, raw: dict, net_obj: net.SessionRequest, it: innertube.InnerTube):
        self.content: str = raw["title"]["simpleText"]

    def __repr__(self) -> str:
        return f'<youtube_client_async.post.VideoErrorAttachment error="{self.content}" >'


def _get_attachment(raw: dict, net_obj: net.SessionRequest, it: innertube.InnerTube) -> PostAttachment:
    if "backstageImageRenderer" in raw:
        return ImagePostAttachment(raw["backstageImageRenderer"]["image"]["thumbnails"], net_obj, it)
    elif "postMultiImageRenderer" in raw:
        return MultiImagePostAttachment(raw["postMultiImageRenderer"]["images"], net_obj, it)
    elif "videoRenderer" in raw:
        vr = raw["videoRenderer"]
        if "ownerText" in vr:
            return AnotherVideoPostAttachment(vr, net_obj, it)
        elif "videoId" not in vr:
            return VideoErrorPostAttachment(vr, net_obj, it)
        else:
            return SelfVideoPostAttachment(vr, net_obj, it)
    else:
        helpers.logger.warning(f"not found post attachment {raw.keys()} return None")
        return None


class Post:
    def __init__(self, raw: dict, net_obj: net.SessionRequest, it: innertube.InnerTube):
        self.post_id: str = raw["postId"]
        self.content: str = helpers.get_text_by_runs(raw["contentText"])
        self.author_name: str = helpers.get_text_by_runs(raw["authorText"])
        self.author_id: str = raw["authorEndpoint"]["browseEndpoint"]["browseId"]
        self.author_url: str = (
            "https://youtube.com"
            + raw["authorEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"]
        )
        self.author_thumbnails: thumbnail.ThumbnailQuery = thumbnail.ThumbnailQuery(
            raw["authorThumbnail"]["thumbnails"],
            net_obj
        )
        self.vote_count: str = raw["voteCount"]["simpleText"]
        self.vote_count_label: str = raw["actionButtons"]["commentActionButtonsRenderer"][
            "likeButton"]["toggleButtonRenderer"]["accessibility"]["label"]
        self.comments_count: Optional[str] = None
        try:
            self.comments_count = raw["actionButtons"]["commentActionButtonsRenderer"][
                "replyButton"]["buttonRenderer"]["text"]["simpleText"]
        except KeyError:
            pass
        self.published_time: str = helpers.get_from_dict(raw["publishedTimeText"])
        self.attachment: Optional[PostAttachment] = None
        if "backstageAttachment" in raw:
            self.attachment = _get_attachment(raw["backstageAttachment"], net_obj, it)

    def __repr__(self) -> str:
        return f"<youtube_client_async.post.Post {self.post_id} >"


class PostThread(base_youtube.BaseYoutube, Post):
    """contains comments continuation"""

    def __init__(
        self,
        url: str,
        net_obj: net.SessionRequest,
        it: innertube.InnerTube,
        html: str,
        initial_data: Optional[dict] = None,
        ytcfg: Optional[dict] = None,
    ):

        base_youtube.BaseYoutube.__init__(self, url, html, net_obj, it, initial_data, ytcfg)
        contents = self.initial_data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"][0][
            "tabRenderer"]["content"]["sectionListRenderer"]["contents"]
        post_content = contents[0]["itemSectionRenderer"]["contents"][0][
            "backstagePostThreadRenderer"]["post"]["backstagePostRenderer"]
        Post.__init__(self, post_content, self.net_obj, self.it)
        self.comment_continuation_token: Optional[str] = None
        if len(contents) > 0:
            self.comment_continuation_token = contents[1]["itemSectionRenderer"]["contents"][0][
                "continuationItemRenderer"]["continuationEndpoint"]["continuationCommand"]["token"]

    async def _get_comments_response(self, sort_by: comment.CommentSortedType = comment.CommentSortedType.top) -> comment.CommentResponseFirst:

        return await comment._get_comment_response(
            self.comment_continuation_token,
            sort_by,
            self.net_obj,
            self.it,
            comment.GetCommentMethod.browse,
        )

    async def get_comments_response_getter(self, sort_by: comment.CommentSortedType = comment.CommentSortedType.top) -> comment.CommentResponseGetter:
        fv = await self._get_comments_response(sort_by)
        return comment.CommentResponseGetter(
            fv, self.net_obj, self.it, comment.GetCommentMethod.browse
        )

    def __repr__(self) -> str:
        return f"<youtube_client_async.post.PostThread {self.post_id} >"


async def get_post(
    url: str,
    net_obj: net.SessionRequest,
    it: innertube.InnerTube,
    html: Optional[str] = None,
    initial_data: Optional[dict] = None,
    ytcfg: Optional[dict] = None,
) -> PostThread:

    c_html = html if html else await net_obj.get_text(url)
    return PostThread(url, net_obj, it, c_html, initial_data, ytcfg)
