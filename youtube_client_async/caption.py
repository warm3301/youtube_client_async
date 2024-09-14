"""Module for obtaining information about subtitles and for working with an array of subtitles"""
import math
import time
import xml.etree.ElementTree as ElementTree
from collections.abc import Iterable, Mapping
from html import unescape
from typing import Callable, List, Optional, Tuple, TypeVar, Union, overload

from . import exceptions, helpers, net


class CaptionError(exceptions.YoutubeClientError):
    pass

class CaptionGettingError(CaptionError):
    pass

class Caption:
    """Subtitle information"""
    def __init__(
        self,
        raw: dict,
        translation_languages: Tuple[str, str],
        net_obj: net.SessionRequest,
    ):
        self.translation_languages: Tuple[str, str] = translation_languages
        self.raw: dict = raw
        self.url: str = raw["baseUrl"]
        name = raw["name"]
        self.name: str = "simpleText" if "simpleText" in name else helpers.get_text_by_runs(name)
        self.audio_track_name: Optional[str] = raw.get("trackName")
        self.vss_id: str = raw["vssId"]
        self.l_code: str = raw["languageCode"]
        self.is_translatable: bool = raw["isTranslatable"]
        vid = self.vss_id.split(".")
        self.is_generated: bool = vid[0] == "a"
        self.kind: Optional[str] = raw.get("kind")
        self.rtl: Optional[bool] = raw.get("rtl", False)  # is .ar then True
        self.net_obj: net.SessionRequest = net_obj

    def __repr__(self) -> str:
        return f'<youtube_client_async.Caption vss="{self.vss_id}"/>'

    @staticmethod
    def _float_to_srt_time_format(d: float) -> str:
        fraction, whole = math.modf(d)
        time_fmt = time.strftime("%H:%M:%S,", time.gmtime(whole))
        ms = f"{fraction:.3f}".replace("0.", "")
        return time_fmt + ms

    @staticmethod
    def _xml_caption_to_srt(xml_captions: str, replace_nl: bool = False) -> str:
        segments = []
        root = ElementTree.fromstring(xml_captions)
        count_line = 0
        for i, child in enumerate(list(root.findall("text"))):

            text = "".join(child.itertext()).strip()
            if not text:
                continue
            count_line += 1
            tttx = text.replace("  ", " ")
            if replace_nl:
                tttx.replace("\n", " ")
            caption = unescape(
                tttx,
            )
            try:
                duration = float(child.attrib["dur"])
            except KeyError:
                duration = 0.0
            start = float(child.attrib["start"])
            end = start + duration
            try:
                end2 = float(root.findall("text")[i + 2].attrib["start"])
            except:
                end2 = float(root.findall("text")[i].attrib["start"]) + duration
            line = "{seq}\n{start} --> {end}\n{text}\n".format(
                seq=count_line,
                start=Caption._float_to_srt_time_format(start),
                end=Caption._float_to_srt_time_format(end),
                text=caption,
            )
            segments.append(line)

        return "\n".join(segments).strip()

    @staticmethod
    def _xml_caption_to_text(xml_captions: str, replace_nl: bool = False) -> str:
        segments = []
        root = ElementTree.fromstring(xml_captions)
        for i, child in enumerate(list(root.findall("text"))):
            text = "".join(child.itertext()).strip()
            if not text:
                continue
            tttx = text.replace("  ", " ")
            if replace_nl:
                tttx.replace("\n", " ")
            caption = unescape(
                tttx,
            )
            segments.append(caption)

        return "\n".join(segments).strip()

    async def get(self, fmt: str = "srt", t_lang: Optional[str] = None, delete_nl: bool = False) -> str:
        """Get subtitle text as text.
        :param str fmt:
            Format of caption. It can be json(json3), xml, srv1, srv2, ttml,
            vtt(webvtt), txt(text), srt
        :param str t_lang:
            translation of subtitles into a specific language using YouTube.
            If this is not possible raise a CaptionGettingError exception
        :param delete_nl:
            it works for srt and txt captions
        :returns:
            subtitle text"""
        if not self.is_translatable and t_lang is not None and t_lang != self.l_code:
            raise CaptionGettingError("not translatable")
        if t_lang is not None and t_lang not in self.translation_languages:
            raise CaptionGettingError(f"translation_langs does not contains {t_lang}")

        helpers.logger.info(f"get captions {fmt} {t_lang=} {delete_nl=}")
        fmt = fmt.lower()
        lq = ""
        if t_lang is not None:
            lq = f"&tlang={t_lang}"
        if fmt in ["json", "json3"]:
            return await self.net_obj.get_text(self.url + "&fmt=json3" + lq)
        elif fmt == "xml":
            return await self.net_obj.get_text(self.url + lq)
        elif fmt == "srv1":  # is xml? by default
            return await self.net_obj.get_text(self.url + "&fmt=srv1" + lq)
        elif fmt == "srv2":
            return await self.net_obj.get_text(self.url + "&fmt=srv2" + lq)
        elif fmt == "srv3":
            return await self.net_obj.get_text(self.url + "&fmt=srv3" + lq)
        elif fmt == "ttml":
            return await self.net_obj.get_text(self.url + "&fmt=ttml" + lq)
        elif fmt in ["vtt", "webvtt"]:
            return await self.net_obj.get_text(self.url + "&fmt=vtt" + lq)
        elif fmt in ["txt", "text"]:
            return self._xml_caption_to_text(
                await self.net_obj.get_text(self.url + lq), delete_nl
            )
        elif fmt == "srt":
            return self._xml_caption_to_srt(
                await self.net_obj.get_text(self.url + lq), delete_nl
            )
        else:
            raise CaptionGettingError(f"fmt {fmt} is not supported.")


CaptionQueryT = TypeVar("CaptionQueryT", bound="CaptionQuery")


class CaptionQuery(Mapping):
    """Add-on to the list that allows you to search by subtitle properties"""

    def __init__(self, items: List[Caption], translation_languages: List[Tuple[str, str]]):
        self.captions = items
        self.translation_languages = translation_languages

    def _filter(
        self: CaptionQueryT,
        filters: Union[List[Callable[[Caption], bool]], Callable[[Caption], bool]],
    ) -> CaptionQueryT:

        caps = self.captions
        if isinstance(filters, Iterable):
            for filter_lambda in filters:
                caps = filter(filter_lambda, caps)
        else:
            caps = filter(filters, caps)
        return CaptionQuery(list(caps), self.translation_languages)

    def filter(
        self,
        l_code: Optional[str] = None,
        vss_id: Optional[str] = None,
        is_generated: Optional[bool] = None,
        is_translatable: Optional[bool] = None,
        name: Optional[str] = None,
        rtl: Optional[bool] = None,
        kind: Optional[str] = None,
        custom_filter_function: Optional[Callable[[Caption], bool]] = None,
    ) -> CaptionQueryT:
        """Filter by subtitle property or you can use your own function"""

        filters = []
        if l_code:
            filters.append(lambda x: x.l_code == l_code)
        if vss_id:
            filters.append(lambda x: x.vss_id == vss_id)
        if is_generated:
            filters.append(lambda x: x.is_generated == is_generated)
        if is_translatable:
            filters.append(lambda x: x.is_translatable == is_translatable)
        if name:
            filters.append(lambda x: x.name == name)
        if rtl:
            filters.append(lambda x: x.rtl == rtl)
        if kind:
            filters.append(lambda x: x.kind == kind)
        if custom_filter_function:
            filters.append(custom_filter_function)
        return self._filter(filters)

    @property
    def caption_base_generated(self) -> Optional[Caption]:
        val = self.filter(is_generated=True)
        if len(val.captions) > 0:
            return val.first
        return None

    # TODO only one caption? create @property original_language
    @property
    def auto_created(self) -> CaptionQueryT:
        return self.filter(is_generated=True)

    @property
    def user_created(self) -> CaptionQueryT:
        return self.filter(is_generated=False)

    @property
    def translatable(self) -> CaptionQueryT:
        return self.filter(is_translatable=True)

    def get_by_name(self, name: str) -> Caption:
        return self.filter(name=name).first

    def get_by_lcode(self, l_code: str) -> CaptionQueryT:
        return filter(l_code=l_code)

    def get_by_vvs_id(self, vss_id: str) -> Caption:
        return self.filter(vss_id=vss_id).first

    @property
    def first(self) -> Caption:
        return self.captions[0]

    @property
    def last(self) -> Caption:
        return self.captions[-1]

    @overload
    def __getitem__(self, i: str) -> Caption:
        pass

    @overload
    def __getitem__(self, i: int) -> Caption:
        pass

    @overload
    def __getitem__(self, i: slice) -> CaptionQueryT:
        pass

    def __getitem__(self, i: Union[str, int, slice]) -> Union[CaptionQueryT, Caption]:
        if isinstance(i, int):
            return self.captions[i]
        elif isinstance(i, slice):
            return CaptionQuery(self.captions[i], self.translation_languages)
        elif isinstance(i, str):
            return self.filter(vss_id=i).first

    def keys(self) -> str:
        return [x.vss_id for x in self.captions]

    def values(self) -> List[Caption]:
        return self.captions

    def items(self) -> List[Tuple[str, Caption]]:
        return list(zip(self.keys, self.values))

    def __len__(self) -> int:
        return len(self.captions)

    def __iter__(self):
        return iter(self.captions)

    def __repr__(self) -> str:
        return f"<yotube_client_async.CaptionQuery {self.captions} />"
