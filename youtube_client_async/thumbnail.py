from collections.abc import Sequence
from typing import List, Optional, TypeVar, Union

from . import net


class Thumbnail:
    def __init__(self, raw: dict, net_obj: net.SessionRequest):
        self._raw = raw
        self.url: str = self._raw["url"]
        self.width: Optional[int] = self._raw.get("width")
        self.height: Optional[int] = self._raw.get("height")
        self.net_obj: net.SessionRequest = net_obj

    # TODO get bytes and PIL

    def __repr__(self) -> str:
        return f'<youtube_client_async.thumbnail.Thumbnail url="{self.url}" />'


ThumbnailQueryType = TypeVar("ThumbnailQueryType", bound="ThumbnailQuery")
class ThumbnailQuery(Sequence):
    def __init__(self, raw: List[dict], net_obj: net.SessionRequest):
        self.net_obj: net.SessionRequest = net_obj
        self._raw: List = raw
        self.items: List[Thumbnail] = [Thumbnail(x, net_obj) for x in self._raw]

    def sort_by_resolution(self, reverse=False) -> ThumbnailQueryType:
        return ThumbnailQuery(self.items.sort(key=lambda x: x.height, reverse=reverse), self.net_obj)

    def get_highest_resolution(self) -> Thumbnail:
        return max(self.items, key=lambda th: th.height)

    def get_lowest_resolution(self) -> Thumbnail:
        return min(self.items, key=lambda th: th.height)

    @property
    def first(self) -> Thumbnail:
        return self.items[0]

    @property
    def last(self) -> Thumbnail:
        return self.items[-1]

    @property
    def reversed(self) -> ThumbnailQueryType:
        return ThumbnailQuery(self.items[::-1], self.net_obj)

    def __getitem__(self, i: Union[slice, int]) -> Union[ThumbnailQueryType, Thumbnail]:
        if isinstance(i, slice):
            return ThumbnailQuery(self.items[i], self.net_obj)
        return self.items[i]

    def __len__(self) -> int:
        return len(self.items)

    def __repr__(self) -> str:
        return f"<youtube_client_async.thumbnail.ThumbnailQuery {self.items} />"

    def __iter__(self):
        self.current_index = 0
        return self

    def __next__(self) -> Thumbnail:
        if self.current_index >= len(self.items):
            raise StopIteration()
        val = self.items[self.current_index]
        self.current_index += 1
        return val
