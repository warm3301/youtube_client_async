"""getter comments info"""
import base64
import json
from collections.abc import Sequence
from enum import Enum
from functools import cached_property
from typing import AsyncIterator, Iterator, List, Optional, TypeVar, Union, overload

from . import helpers, innertube, net, thumbnail


def _generate_comment_continuation(video_id):
    """
    Generates initial comment section continuation token from given video id
    """
    token = f'\x12\r\x12\x0b{video_id}\x18\x062\'"\x11"\x0b{video_id}0\x00x\x020\x00B\x10comments-section'
    return base64.b64encode(token.encode()).decode()


class CommentSortedType(Enum):
    top = 0
    new = 1


class GetCommentMethod(Enum):
    next = 0
    browse = 1


class TeaserComment:
    def __init__(self, raw, net_obj: net.SessionRequest):
        self.net_obj: net.SessionRequest = net_obj
        self.owner_name: str = raw["teaserAvatar"]["accessibility"][
            "accessibilityData"]["label"]
        self.content: str = raw["teaserContent"]["simpleText"]
        self.thumbnails: thumbnail.ThumbnailQuery = thumbnail.ThumbnailQuery(
            raw["teaserAvatar"]["thumbnails"], self.net_obj
        )

    def __repr__(self) -> str:
        return f"<youtube_client_async.comment.TeaserComment \"{self.owner_name}\" : \"{self.content[:50]}\" >"


class CommentSortItem:
    def __init__(self, title: str, selected: bool, token: str):
        self.title = title
        self.selected = selected
        self.token = token

    def __repr__(self) -> str:
        return (
            f"<youtube_client_async.comment.CommentSort"
            f"{' selected ' if self.selected else ' '}"
            'title="{self.title}" token="{self.token}"'
        )


CommentSortedItemsQueryT = TypeVar(
    "CommentSortedItemsQueryT", bound="CommentSortedItemsQuery"
)


class CommentSortedItemsQuery:
    def __init__(self, raw):
        self.raw = raw
        self.items: List[CommentSortItem] = [
            CommentSortItem(
                x["title"],
                x["selected"],
                x["serviceEndpoint"]["continuationCommand"]["token"],
            )
            for x in raw
        ]
        self.current_index = 0

    def get_by_sorted_type(self, sorted_type: CommentSortedType) -> CommentSortItem:
        return self.items[sorted_type]

    @property
    def selected(self) -> Optional[CommentSortItem]:
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
    def __getitem__(self, i: slice) -> CommentSortedItemsQueryT:
        pass

    @overload
    def __getitem__(self, i: int) -> CommentSortItem:
        pass

    def __getitem__(self, i: Union[slice, int]) -> Union[CommentSortedItemsQueryT, CommentSortItem]:
        if isinstance(i, slice):
            return CommentSortedItemsQuery(self.raw[i])
        return self.items[i]

    def __len__(self) -> int:
        return len(self.items)

    def __repr__(self) -> str:
        return f"<youtube_client_async.comment.CommentSortedItemsQuery {str(self.items)} >"

    def __iter__(self) -> CommentSortedItemsQueryT:
        self.current_index = 0
        return self

    def __next__(self) -> CommentSortItem:
        if self.current_index >= len(self.items):
            raise StopIteration()
        val = self.items[self.current_index]
        self.current_index += 1
        return val


class CommentRendererViewModel:
    def __init__(self, raw):
        cvm = raw["commentViewModel"] if "commentViewModel" in raw else raw
        self.comment_id: str = cvm["commentId"]
        self.pinned_text: Optional[str] = cvm.get("pinned_text")

    def __hash__(self):
        return hash(self.comment_id)

    def __eq__(self, other):
        return self.comment_id == other.comment_id


class CommentThreadRendererViewModel(CommentRendererViewModel):
    def __init__(self, raw):
        self._raw2 = raw
        self.comment_thread_renderer = None
        if "commentThreadRenderer" in self._raw2:
            super().__init__(
                self._raw2["commentThreadRenderer"]["commentViewModel"][
                    "commentViewModel"
                ]
            )
        else:
            raise NotImplementedError("not excepted")

    @property
    def _comment_view_model(self) -> dict:
        return self._raw2["commentThreadRenderer"]["commentViewModel"][
            "commentViewModel"]

    @property
    def _comment_replies_renderer(self) -> Optional[dict]:
        return self._raw2["commentThreadRenderer"]["replies"]["commentRepliesRenderer"]

    @property
    def _replies_token(self) -> Optional[str]:
        try:
            return self._comment_replies_renderer["contents"][0][
                "continuationItemRenderer"]["continuationEndpoint"][
                "continuationCommand"]["token"]
        except KeyError:
            return None

    @property
    def replies_view_count(self) -> str:
        return helpers.get_text_by_runs(self._comment_replies_renderer["viewReplies"]["buttonRenderer"]["text"])

    @property
    def replies_hide_count(self) -> str:
        return helpers.get_text_by_runs(self._comment_replies_renderer["hideReplies"]["buttonRenderer"]["text"])

    def __hash__(self):
        return hash(self.comment_id)

    def __eq__(self, other):
        return self.comment_id == other.comment_id


class CommentEntityPayload:
    def __init__(self, raw):
        self._raw = raw

    @property
    def key(self) -> str:
        return self._raw["key"]

    @property
    def replyLevel(self) -> int:
        return self._raw["properties"]["replyLevel"]

    @property
    def authorButtonA11y(self) -> str:
        return self._raw["properties"]["authorButtonA11y"]

    @property
    def innerBadgeA11y(self) -> str:
        return self._raw["author"]["innerBadgeA11y"]

    @property
    def comment_id(self) -> str:
        return self._raw["properties"]["commentId"]

    @property
    def published_time(self) -> str:
        return self._raw["properties"]["publishedTime"]

    @property
    def content(self) -> str:
        return self._raw["properties"]["content"]["content"]


class CommentSurfaceEntityPayload:
    pass


class EmojiCategory:
    def __init__(self, raw):
        self._raw = raw

    def __repr__(self) -> str:
        return f"<Emoji category {self.title} count={len(self._raw['emojiIds'])}/>"

    @property
    def category_id(self) -> str:
        return self._raw["categoryId"]

    @property
    def title(self) -> str:
        return self._raw["title"]["simpleText"]

    @property
    def category_type(self) -> str:
        return self._raw["categoryType"]

    @property
    def is_lazy_load(self) -> bool:
        return self._raw.get("imageLoadingLazy", False)

    @property
    def content(self) -> List[str]:
        return self._raw["emojiIds"]


class EmojiInfo:
    def __init__(self, raw, net_obj=net.SessionRequest):
        self.raw = raw
        self.net_obj = net_obj

    def __repr__(self) -> str:
        return self.content

    @property
    def id(self) -> str:
        return self.raw["emoji"]["emojiId"]

    @property
    def content(self) -> str:
        return self.raw["text"]

    @property
    def search_terms(self) -> Optional[str]:
        if "searchTerms" in self.raw["emoji"]:
            return self.raw["emoji"]["searchTerms"]
        return None

    @property
    def shortcuts(self) -> List[str]:
        return self.raw["emoji"]["shortcuts"]

    @property
    def images(self) -> thumbnail.ThumbnailQuery:
        return thumbnail.ThumbnailQuery(
            self.raw["emoji"]["image"]["thumbnails"], self.net_obj
        )


class Comment:
    def __init__(
        self,
        renderer,
        entity,
        net_obj: net.SessionRequest,
        it: net.SessionRequest,
        comment_method: GetCommentMethod = GetCommentMethod.next,
    ):
        self._comment_method: GetCommentMethod = comment_method
        self.net_obj: net.SessionRequest = net_obj
        self.it: innertube.InnerTube = it
        self._renderer: CommentRendererViewModel = renderer
        self._entity: CommentEntityPayload = entity

    @property
    def content(self) -> str:
        return self._entity.content

    @property
    def comment_id(self) -> str:
        return self._entity.comment_id

    @property
    def published_time(self) -> str:
        return self._entity.published_time

    @property
    def author_id(self) -> str:
        return self._entity._raw["author"]["channelId"]

    @property
    def author_dispay_name(self) -> str:
        return self._entity._raw["author"]["displayName"]

    @property
    def avatarThumbnailUrl(self) -> str:
        return self._entity._raw["author"]["avatarThumbnailUrl"]

    @property
    def isVerified(self) -> bool:
        return self._entity._raw["author"]["isVerified"]

    @property
    def isCurrentUser(self) -> bool:
        return self._entity._raw["author"]["isCurrentUser"]

    @property
    def isCreator(self) -> bool:
        return self._entity._raw["author"]["isCreator"]

    @property
    def author_url(self) -> str:
        return self._entity._raw["author"]["channelCommand"]["innertubeCommand"][
            "browseEndpoint"]["browseId"]

    @property
    def author_canonicalBaseUrl(self) -> str:
        return self._entity._raw["author"]["channelCommand"]["innertubeCommand"][
            "browseEndpoint"]["canonicalBaseUrl"]

    @property
    def isArtist(self) -> bool:
        return self._entity._raw["author"]["isArtist"]

    @property
    def likeCountLiked(self) -> str:
        return self._entity._raw["toolbar"]["likeCountLiked"]

    @property
    def likeCountNotliked(self) -> str:
        return self._entity._raw["toolbar"]["likeCountNotliked"]

    @property
    def heartActiveTooltip(self) -> Optional[str]:
        return self._entity._raw["toolbar"].get("heartActiveTooltip")

    def __repr__(self) -> str:
        return f'<youtube_client_async.Comment id="{self.comment_id} " >'


class CommentResponseBase:
    def __init__(
        self,
        raw: dict,
        net_obj: net.SessionRequest,
        it: innertube.InnerTube,
        comment_method: GetCommentMethod = GetCommentMethod.next,
    ):
        self._comment_method: GetCommentMethod = comment_method
        self.raw: dict = raw
        self.net_obj: net.SessionRequest = net_obj
        self.it: innertube.InnerTube = it
        self.continuation_token: str = None
        self._raw_comments: List = None
        items = None
        if "onResponseReceivedEndpoints" in raw:
            items = raw["onResponseReceivedEndpoints"][-1]
            if "reloadContinuationItemsCommand" in items:
                items = items["reloadContinuationItemsCommand"]
                if "continuationItems" in items:
                    items = items["continuationItems"]  # default
            elif "appendContinuationItemsAction" in items:
                items = items["appendContinuationItemsAction"]
                if "continuationItems" in items:
                    items = items["continuationItems"]  # after continuation
            else:
                raise NotImplementedError(items.keys())
        else:
            raise NotImplementedError()
        cir = None
        try:
            cir = items[-1].get("continuationItemRenderer")
            if cir is not None:
                try:
                    self.continuation_token = cir["continuationEndpoint"][
                        "continuationCommand"]["token"]
                except KeyError:
                    self.continuation_token = cir["button"]["buttonRenderer"]["command"][
                        "continuationCommand"]["token"]
                self._raw_comments = items[0:-1]
            else:
                self._raw_comments = items
        except KeyError:
            self._raw_comments = list()
            helpers.logger.warning(f"not found items in comments {items}")
            self.continuation_token = None


class RepliesResponse(CommentResponseBase, Sequence):
    def __init__(
        self,
        raw: dict,
        net_obj: net.SessionRequest,
        it: innertube.InnerTube,
        get_comment_method: GetCommentMethod = GetCommentMethod.next,
    ):
        super().__init__(raw, net_obj, it, get_comment_method)
        self._renderers = {
            renderer["commentViewModel"]["commentId"]: CommentRendererViewModel(
                renderer
            )
            for renderer in self._raw_comments
        }
        self._entity_contents = dict()
        if "frameworkUpdates" in self.raw:
            self._entity_contents = {
                entity["payload"]["commentEntityPayload"]["properties"][
                    "commentId"
                ]: CommentEntityPayload(entity["payload"]["commentEntityPayload"])
                for entity in self.raw["frameworkUpdates"]["entityBatchUpdate"]["mutations"]
                if "payload" in entity and "commentEntityPayload" in entity["payload"]
            }
        else:
            helpers.logger.warning(f"not found frameworkUpdates in comments {self.raw.keys()}")
        self.content: List[Comment] = [
            Comment(
                self._renderers[com_id],
                self._entity_contents[com_id],
                self.net_obj,
                self.it,
                self._comment_method,
            )
            for com_id in self._renderers.keys()
        ]

    def __repr__(self) -> str:
        return (
            f"<youtube_client_async.comment.RepliesResponse"
            f"comment in resp {len(self._renderers)}"
            f"{' and continuation ' if self.continuation_token else ' '}>"
        )

    def __len__(self) -> int:
        return len(self.content)

    def __iter__(self) -> Iterator[Comment]:
        return iter(self.content)

    @overload
    def __getitem__(self, i: int) -> Comment:
        pass

    @overload
    def __getitem__(self, i: slice) -> List[Comment]:
        pass

    def __getitem__(self, i: Union[int, slice]) -> Union[Comment, List[Comment]]:
        return self.content[i]


class RepliesResponseGetter:
    def __init__(
        self,
        current_item: RepliesResponse,
        net_obj: net.SessionRequest,
        it: innertube.InnerTube,
        get_comment_method: GetCommentMethod = GetCommentMethod.next,
    ):
        self.current_item: RepliesResponse = current_item
        self.current_continuation_token = current_item.continuation_token
        self.net_obj = net_obj
        self.it = it
        self.f = True
        self.get_comment_method: GetCommentMethod = get_comment_method

    def __aiter__(self) -> AsyncIterator[RepliesResponse]:
        return self

    async def __anext__(self) -> RepliesResponse:
        if self.f:
            self.f = False
            return self.current_item
        if self.current_continuation_token is None:
            raise StopAsyncIteration()
        raw = None
        if self.get_comment_method == GetCommentMethod.next:
            raw = await self.it.next(continuation=self.current_continuation_token)
        elif self.get_comment_method == GetCommentMethod.browse:
            raw = await self.it.browse(continuation=self.current_continuation_token)
        self.current_item = RepliesResponse(
            raw, self.net_obj, self.it, self.get_comment_method
        )
        self.current_continuation_token = self.current_item.continuation_token
        return self.current_item


class CommentThread(Comment):
    def __init__(
        self,
        renderer,
        entity,
        net_obj: net.SessionRequest,
        it: innertube.InnerTube,
        get_comment_method: GetCommentMethod = GetCommentMethod.next,
    ):
        super().__init__(renderer, entity, net_obj, it)
        self.get_comment_method: GetCommentMethod = get_comment_method

    @property
    def pinned_text(self) -> Optional[str]:
        try:
            return self._renderer._comment_view_model["pinnedText"]
        except:
            return None

    @property
    def reply_count(self) -> str:
        return self._entity._raw["toolbar"]["replyCount"]

    async def get_replies_getter(self) -> Optional[RepliesResponseGetter]:
        token = self._renderer._replies_token
        if token is None:
            return None
        resp = None
        if self.get_comment_method == GetCommentMethod.next:
            resp = await self.it.next(continuation=token)
        elif self.get_comment_method == GetCommentMethod.browse:
            resp = await self.it.browse(continuation=token)
        fo = RepliesResponse(resp, self.net_obj, self.it, self.get_comment_method)
        if fo is None:
            return None
        return RepliesResponseGetter(fo, self.net_obj, self.it, self.get_comment_method)

    def __repr__(self) -> str:
        return f'<youtube_client_async.CommentThread id="{self.comment_id}">'


class CommentResponse(CommentResponseBase):
    def __init__(
        self,
        raw: dict,
        net_obj: net.SessionRequest,
        it: innertube.InnerTube,
        get_comment_method: GetCommentMethod = GetCommentMethod.next,
    ):
        super().__init__(raw, net_obj, it, get_comment_method)
        self._renderers = {
            renderer["commentThreadRenderer"]["commentViewModel"]["commentViewModel"][
                "commentId"
            ]: CommentThreadRendererViewModel(renderer)
            for renderer in self._raw_comments
        }
        self._entity_contents = {
            entity["payload"]["commentEntityPayload"]["properties"][
                "commentId"
            ]: CommentEntityPayload(entity["payload"]["commentEntityPayload"])
            for entity in self.raw["frameworkUpdates"]["entityBatchUpdate"]["mutations"]
            if "payload" in entity and "commentEntityPayload" in entity["payload"]
        }
        self.content: List[CommentThread] = [
            CommentThread(
                self._renderers[com_id],
                self._entity_contents[com_id],
                self.net_obj,
                self.it,
                self._comment_method,
            )
            for com_id in self._renderers.keys()
        ]

    def __repr__(self) -> str:
        return (
            "<youtube_client_async.comment.CommentResponse comment in resp"
            f" {len(self._renderers)}{' and continuation ' if self.continuation_token else ' '}>"
        )

    def __len__(self) -> int:
        return len(self.content)

    def __iter__(self) -> Iterator[CommentThread]:
        return iter(self.content)

    @overload
    def __getitem__(self, i: int) -> CommentThread:
        pass

    @overload
    def __getitem__(self, i: slice) -> List[CommentThread]:
        pass

    def __getitem__(
        self, i: Union[int, slice]
    ) -> Union[CommentThread, List[CommentThread]]:
        return self.content[i]


class CommentResponseFirst(CommentResponse):
    def __init__(
        self,
        raw: dict,
        net_obj: net.SessionRequest,
        it: innertube.InnerTube,
        get_comment_method: GetCommentMethod = GetCommentMethod.next,
    ):
        super().__init__(raw, net_obj, it, get_comment_method)

    @cached_property
    def _header(self):
        return self.raw["onResponseReceivedEndpoints"][0][
            "reloadContinuationItemsCommand"]["continuationItems"][0][
            "commentsHeaderRenderer"]

    @property
    def count_comments(self) -> str:
        return helpers.get_text_by_runs(self._header["countText"])

    @property
    def sorted_items(self) -> CommentSortedItemsQuery:
        return CommentSortedItemsQuery(
            self._header["sortMenu"]["sortFilterSubMenuRenderer"]["subMenuItems"]
        )

    @property
    def unicode_emojis_json_url(self) -> Optional[str]:
        self._header.get("unicodeEmojisUrl")

    @property
    def custom_emojis(self) -> List[EmojiInfo]:
        raw = self._header.get("customEmojis")
        if not raw:
            return list()
        return [EmojiInfo(x, self.net_obj) for x in raw]

    @property
    def emoji_categories_array(self) -> List[EmojiCategory]:
        renderer = self._create_renderer
        if renderer:
            return [
                EmojiCategory(x["emojiPickerCategoryRenderer"])
                for x in renderer["emojiPicker"]["emojiPickerRenderer"]["categories"]
            ]
        return list()

    @property
    def show_separator(self) -> bool:
        return self._header.get("showSeparator", False)

    @property
    def _create_renderer(self):
        return self._header["createRenderer"]["commentSimpleboxRenderer"]

    @property
    def your_avatar_thumbnails(self) -> thumbnail.ThumbnailQuery:
        return thumbnail.ThumbnailQuery(
            self._create_renderer["authorThumbnail"]["thumbnails"], self.net_obj
        )


class CommentResponseGetter:
    def __init__(
        self,
        current_item: CommentResponseFirst,
        net_obj: net.SessionRequest,
        it: innertube.InnerTube,
        get_comment_method: GetCommentMethod = GetCommentMethod.next,
    ):
        self.current_item: CommentResponseFirst = current_item
        self.current_continuation_token: str = self.current_item.continuation_token
        self.net_obj: net.SessionRequest = net_obj
        self.it: innertube.InnerTube = it
        self.f: bool = True
        self.get_comment_method: GetCommentMethod = get_comment_method

    def __aiter__(self) -> AsyncIterator[CommentResponse]:
        return self

    async def __anext__(self) -> Union[CommentResponseFirst, CommentResponse]:
        if self.f:
            self.f = False
            return self.current_item
        if self.current_continuation_token is None:
            raise StopAsyncIteration()
        raw = None
        if self.get_comment_method == GetCommentMethod.next:
            raw = await self.it.next(continuation=self.current_continuation_token)
        elif self.get_comment_method == GetCommentMethod.browse:
            raw = await self.it.browse(continuation=self.current_continuation_token)
        self.current_item = CommentResponse(
            raw, self.net_obj, self.it, self.get_comment_method
        )
        self.current_continuation_token = self.current_item.continuation_token
        return self.current_item


class CommentResponseGetterWithoutFirstInfo(CommentResponseGetter):
    def __init__(
        self,
        current_item: CommentResponse,
        net_obj: net.SessionRequest,
        it: innertube.InnerTube,
        get_comment_method: GetCommentMethod = GetCommentMethod.next,
    ):
        super().__init__(current_item, net_obj, it, get_comment_method)

    def __aiter__(self) -> AsyncIterator[CommentResponse]:
        return self

    async def __anext__(self) -> CommentResponse:
        if self.f:
            self.f = False
            return self.current_item
        if self.current_continuation_token is None:
            raise StopAsyncIteration()
        raw = None
        if self.get_comment_method == GetCommentMethod.next:
            raw = await self.it.next(continuation=self.current_continuation_token)
        elif self.get_comment_method == GetCommentMethod.browse:
            raw = await self.it.browse(continuation=self.current_continuation_token)
        self.current_item = CommentResponse(
            raw, self.net_obj, self.it, self.get_comment_method
        )
        self.current_continuation_token = self.current_item.continuation_token
        return self.current_item


async def _get_comment_response(
    continuation: str,
    sorted_type: CommentSortedType,
    net_obj: net.SessionRequest,
    it: innertube.InnerTube,
    method: GetCommentMethod = GetCommentMethod.next,
    generate_first: bool = True,
) -> Union[CommentResponseFirst, CommentResponse]:

    raw = None
    if method == GetCommentMethod.browse:
        raw = await it.browse(continuation=continuation)
    elif method == GetCommentMethod.next:
        raw = await it.next(continuation=continuation)
    cr = None
    if generate_first:
        cr = CommentResponseFirst(raw, net_obj, it, method)
    else:
        cr = CommentResponse(raw, net_obj, it, method)
    if generate_first and cr.sorted_items.selected_index != sorted_type.value:
        raw = None
        if method == GetCommentMethod.browse:
            raw = await it.browse(continuation=cr.sorted_items.selected.token)
        elif method == GetCommentMethod.next:
            raw = await it.next(continuation=cr.sorted_items.selected.token)
        if generate_first:
            cr = CommentResponseFirst(raw, net_obj, it, method)
        else:
            cr = CommentResponse(raw, net_obj, it, method)
    return cr
