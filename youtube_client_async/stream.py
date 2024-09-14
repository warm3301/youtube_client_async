import math
from collections.abc import Sequence
from datetime import datetime
from typing import Callable, List, Optional, TypeVar, Union, overload
from urllib import parse

from aiohttp.http_exceptions import HttpProcessingError

from . import extract, itags, net

default_range_size = 9437184


class AudioTrackInfo:
    def __init__(self, raw):
        self.id: str = raw["id"]
        self.name: str = raw["displayName"]
        self.is_default: bool = raw["audioIsDefault"]
    def __repr__(self) -> str:
        return f"<AudioTrack {self.name}/>"


class Stream:
    def __init__(self, raw, duration, title, net_obj: net.SessionRequest):
        self.net_obj: net.SessionRequest = net_obj
        self.duration = duration
        self.title = title
        self.raw = raw
        self.itag = raw["itag"]
        self.url: str = raw["url"]
        self._content_lenght: str = int(raw.get("contentLength",0))
        self.average_bitrate: int = raw.get("averageBitrate",None)
        self.mime_type_sourse: str = raw["mimeType"]
        self.bitrate: int = raw["bitrate"]
        self.last_modified: str = raw.get("lastModified")
        self.quality: str = raw["quality"]
        self.quality_label: str = raw.get("qualityLabel")
        self.projection_type: str = raw["projectionType"]
        self.approx_duration: str = raw.get("approxDurationMs")
        
        self.color_info_matrix_coefficients: str = None
        self.color_info_primaries: str = None
        self.color_info_transfer_characteristics: str = None
        _color_info = raw.get("colorInfo")
        if _color_info:
            self.color_info_primaries = _color_info.get("primaries")
            self.color_info_transfer_characteristics = _color_info.get("transferCharacteristics")
            self.color_info_matrix_coefficients = _color_info.get("matrixCoefficients")
        
        self.fps: float = raw.get("fps",None)
        self.width: int = raw.get("width",None)
        self.height: int = raw.get("height",None)
        self.video_quality_lable = raw.get("qualityLabel")

        self.audio_quality: str = raw.get("audioQuality")
        self.audio_channels: int = raw.get("audioChannels")
        self.audio_sample_rate: str = raw.get("audioSampleRate")
        self.loudness_db: float = raw.get("loudnessDb")

        # 'video/webm; codecs="vp8, vorbis"' -> 'video/webm', ['vp8', 'vorbis']
        self.mime_type, self.codecs = extract.mime_type_codec(self.mime_type_sourse)
        # 'video/webm' -> 'video', 'webm'
        self.type, self.ext = self.mime_type.split("/")

        # ['vp8', 'vorbis'] -> video_codec: vp8, audio_codec: vorbis. DASH
        # streams return NoneType for audio/video depending.
        self.video_codec, self.audio_codec = self.parse_codecs()

        self._filesize_kb: Optional[float] = float(math.ceil(float(self._content_lenght) / 1024 * 1000) / 1000)
        self._filesize_mb: Optional[float] = float(math.ceil(float(self._content_lenght) / 1024 / 1024 * 1000) / 1000)
        self._filesize_gb: Optional[float] = float(math.ceil(float(self._content_lenght) / 1024 / 1024 / 1024 * 1000) / 1000)

        # Additional information about the stream format, such as resolution,
        # frame rate, and whether the stream is live (HLS) or 3D.
        itag_profile = itags.get_format_profile(self.itag)
        self.is_dash = itag_profile["is_dash"]
        self.abr = itag_profile["abr"]  # average bitrate (audio streams only)
        self.resolution = itag_profile[
            "resolution"
        ]  # resolution (e.g.: "480p")
        self.is_3d: bool = itag_profile["is_3d"]
        self.is_hdr: bool = itag_profile["is_hdr"]
        # self.is_live:bool = itag_profile["is_live"] # not true
        self.is_otf: bool = raw.get("is_otf", None)
        self._lparsed_url = None

        self.contains_audio_track_info: bool = "audioTrack" in raw
        self.audio_track_info: Optional[AudioTrackInfo] = AudioTrackInfo(raw["audioTrack"]) if self.contains_audio_track_info else None

    #From url
    @property
    def _parsed_url(self) -> dict:  # expire = parse_qs(self.url.split("?")[1])["expire"][0]
        if self._lparsed_url:
            return self._lparsed_url
        self._lparsed_url = parse.parse_qs(parse.urlparse(self.url).query)
        # self._lparsed_url = parse_qs(self.url.split("?")[1])#urllib.parse.urlparse(url)
        return self._lparsed_url

    @property
    def expiration(self) -> datetime:
        expire = self._parsed_url["expire"][0]
        return datetime.utcfromtimestamp(int(expire))

    @property
    def current_ip(self) -> str:
        return self._parsed_url['ip'][0]

    @property
    def aitags(self) -> List[int]:  # TODO for test:
        return [int(x) for x in self._parsed_url.get("aitags",[""])[0].split(',') if x.isdigit()]

    @property
    def require_ssl(self) -> Optional[bool]:  # TODO move to extract.py
        val = self._parsed_url["requiressl"][0]
        if val == "yes":
            return True
        elif val == "no":
            return False
        else:
            return None

    @property
    def url_duration(self) -> float:
        return float(self._parsed_url.get('dur', [0])[0])

    @property
    def lmt(self) -> Optional[str]:
        return self._parsed_url.get('lmt', [None])[0]

    @property
    def keep_alive(self) -> Optional[bool]:
        val = self._parsed_url.get('keepalive', [None])[0]
        if val == "yes":
            return True
        elif val == "no":
            return False
        else:
            return None

    @property
    def ratebypass(self) -> Optional[bool]:
        val = self._parsed_url.get('ratebypass', [None])[0]
        if val == "yes":
            return True
        elif val == "no":
            return False
        else:
            return None

    @property
    def pcm2cms(self) -> Optional[bool]:
        val = self._parsed_url.get("pcm2cms", [None])[0]
        if val == "yes":
            return True
        elif val == "no":
            return False
        else:
            return None

    @property
    def sm_host(self) -> Optional[str]:
        """For live stream"""
        return self._parsed_url.get("smhost", [None])[0]

    @property
    def sourse(self) -> str:
        return self._parsed_url.get("source", [None])[0]

    @property
    def is_live(self) -> bool:
        return self._parsed_url.get("live", [0])[0] == "1"

    @property
    def current_device(self) -> str:
        return self._parsed_url.get("c", [None])[0]

    async def get_filesize(self) -> int:
        """File size of the media stream in bytes.

        :rtype: int
        :returns:
            Filesize (in bytes) of the stream.
        """
        if self._content_lenght == 0:
            try:
                self._content_lenght = await self.net_obj.get_lenght(self.url)
            except HttpProcessingError as e:
                if e.code != 404:
                    raise
                self._content_lenght = await self.net_obj.seq_filesize(self.url)
        return self._content_lenght
        # TODO kb, mb, gb

    @property
    def filesize_approx(self) -> int:
        """Get approximate filesize of the video

        Falls back to HTTP call if there is not sufficient information to approximate

        :rtype: int
        :returns: size of video in bytes
        """
        if self.duration and self.bitrate:
            return int(
                (int(self.duration) * self.bitrate) / 8
            )

        return self.filesize
    
    @property
    def filesize_approx_kb(self)->float:
        return float(math.ceil(self.filesize_approx / 1024 * 1000)/1000)
    
    @property
    def filesize_approx_mb(self)->float:
        return float(math.ceil(self.filesize_approx/1024/1024 * 1000)/1000)
    
    @property
    def filesize_approx_gb(self)->float:
        return float(math.ceil(self.filesize_approx/1024/1024/1024 * 1000)/1000)
    
    @property
    def is_adaptive(self) -> bool:
        """Whether the stream is DASH.

        :rtype: bool
        """
        # if codecs has two elements (e.g.: ['vp8', 'vorbis']): 2 % 2 = 0
        # if codecs has one element (e.g.: ['vp8']) 1 % 2 = 1
        return bool(len(self.codecs) % 2)
        # return self.raw["is_adaptive"]

    @property
    def is_progressive(self) -> bool:
        """Whether the stream is progressive.

        :rtype: bool
        """
        return not self.is_adaptive

    @property
    def includes_audio(self) -> bool:
        """Whether the stream only contains audio.

        :rtype: bool
        """
        return self.is_progressive or self.type == "audio"

    @property
    def includes_video(self) -> bool:
        """Whether the stream only contains video.

        :rtype: bool
        """
        return self.is_progressive or self.type == "video"
    
    @property
    def only_video(self) -> bool:
        return self.includes_video and (not self.includes_audio)
    
    @property
    def only_audio(self) -> bool:
        return self.includes_audio and (not self.includes_video)

    def parse_codecs(self) -> (str, str):
        """Get the video/audio codecs from list of codecs.

        Parse a variable length sized list of codecs and returns a
        constant two element tuple, with the video codec as the first element
        and audio as the second. Returns None if one is not available
        (adaptive only).

        :rtype: tuple
        :returns:
            A two element tuple with audio and video codecs.

        """
        video = None
        audio = None
        if not self.is_adaptive:
            video, audio = self.codecs
        elif self.includes_video:
            video = self.codecs[0]
        elif self.includes_audio:
            audio = self.codecs[0]
        return video, audio

    def __repr__(self) -> str:
        parts = ['itag="{s.itag}"', 'mime_type="{s.mime_type}"']
        if self.includes_video:
            parts.extend(['res="{s.resolution}"', 'fps="{s.fps}fps"'])
            if not self.is_adaptive:
                parts.extend(
                    ['vcodec="{s.video_codec}"', 'acodec="{s.audio_codec}"',]
                )
            else:
                parts.extend(['vcodec="{s.video_codec}"'])
        else:
            parts.extend(['abr="{s.abr}"', 'acodec="{s.audio_codec}"'])
        parts.extend(['progressive="{s.is_progressive}"', 'type="{s.type}"'])
        return f"<Stream: {' '.join(parts).format(s=self)}>"


StreamQueryType = TypeVar("StreamQueryType",bound="StreamQuery")
class StreamQuery(Sequence):
    def __init__(self, streams:List[Stream]):
        self.items: List[Stream] = streams
        self.current_index = 0
    def get_by_itag(self, itag) -> Stream:
        for x in self.items:
            if int(x.itag) == int(itag):
                return x
        return None

    def _filter(self, filters: [Callable[[Stream], bool]]) -> StreamQueryType:
        fmt_streams = self.items
        for filter_lambda in filters:
            fmt_streams = filter(filter_lambda, fmt_streams)
        return StreamQuery(list(fmt_streams))
    def filter(
        self,
        fps=None,
        res=None,
        resolution=None,
        mime_type=None,
        type=None,
        subtype=None,
        file_extension=None,
        # size_less_than:str=None,
        abr=None,
        bitrate=None,
        video_codec=None,
        audio_codec=None,
        only_audio=None,
        only_video=None,
        contains_audio=None,
        contains_video=None,
        progressive=None,
        adaptive=None,
        is_dash=None,
        contains_audio_track_info:bool=None,
        audio_track_id:str=None,
        custom_filter_functions=None,
    ) -> StreamQueryType:
        filters = []
        if res or resolution:
            if isinstance(res, str) or isinstance(resolution, str):
                filters.append(lambda s: s.resolution == (res or resolution))
            elif isinstance(res, list) or isinstance(resolution, list):
                filters.append(lambda s: s.resolution in (res or resolution))

        if fps:
            filters.append(lambda s: s.fps == fps)

        if mime_type:
            filters.append(lambda s: s.mime_type == mime_type)

        if type:
            filters.append(lambda s: s.type == type)

        if subtype or file_extension:
            filters.append(lambda s: s.subtype == (subtype or file_extension))

        if abr or bitrate:
            filters.append(lambda s: s.abr == (abr or bitrate))

        if video_codec:
            filters.append(lambda s: s.video_codec == video_codec)

        if audio_codec:
            filters.append(lambda s: s.audio_codec == audio_codec)

        if only_audio:
            filters.append(
                lambda s: (
                    s.only_audio
                ),
            )

        if only_video:
            filters.append(
                lambda s: (
                    s.only_video
                ),
            )
        if contains_audio:
            filters.append(
                lambda s:{
                    s.includes_audio
                }
            )
        if contains_video:
            filters.append(
                lambda s:{
                    s.includes_video
                }
            )
        if progressive:
            filters.append(lambda s: s.is_progressive)

        if adaptive:
            filters.append(lambda s: s.is_adaptive)

        if custom_filter_functions:
            filters.extend(custom_filter_functions)

        if is_dash is not None:
            filters.append(lambda s: s.is_dash == is_dash)
        
        if contains_audio_track_info is not None:
            filters.append(lambda s: s.contains_audio_track_info == contains_audio_track_info)
        if audio_track_id is not None:
            filters.append(lambda s: s.contains_audio_track_info and s.audio_track_info.id == audio_track_id)
        # if size_less_than is not None:
        #     rfilter = None
        #     if isinstance(size_less_than,str):
        #         size_less_than = size_less_than.lower()
        #     if isinstance(size_less_than,int):
        #         rfilter = lambda s: s.filesize_approx < s.int(size_less_than[:-1])
        #     elif size_less_than.endswith("b"):
        #         rfilter = lambda s: s.filesize_approx < int(size_less_than[:-1])
        #     elif size_less_than.endswith("kb"):
        #         rfilter = lambda s: s.filesize_approx_kb < int(size_less_than[:-2])
        #     elif size_less_than.endswith("mb"):
        #         rfilter = lambda s: s.filesize_approx_mb < int(size_less_than[:-2])
        #     elif size_less_than.endswith("gb"):
        #         rfilter = lambda s: s.filesize_approx_gb < int(size_less_than[:-2])
        #     else:
        #         raise Exception(f"not understand command {rfilter}")
        #     filters.append(rfilter)
        return self._filter(filters)
    
    def order_by(self, attribute_name: str, reverse: bool = False) -> StreamQueryType:
        """Apply a sort order. Filters out stream the do not have the attribute.

        :param str attribute_name:
            The name of the attribute to sort by.
        """
        has_attribute = [
            s
            for s in self.items
            if getattr(s, attribute_name) is not None
        ]
        # Check that the attributes have string values.
        if has_attribute and isinstance(
            getattr(has_attribute[0], attribute_name), str
        ):
            # Try to return a StreamQuery sorted by the integer representations
            # of the values.
            try:
                return StreamQuery(
                    sorted(
                        has_attribute,
                        key=lambda s: int(
                            "".join(
                                filter(str.isdigit, getattr(s, attribute_name))
                            )
                        ),reverse=reverse
                    )
                )
            except ValueError:
                pass

        return StreamQuery(
            sorted(has_attribute, key=lambda s: getattr(s, attribute_name))
        )
    
    def sort_by_filesize(self,reverse: bool = False)->StreamQueryType:
        return self.order_by("filesize_approx", reverse=reverse)

    def sort_by_audio_sample_rate(self, reverse: bool = False)->StreamQueryType:
        return self.filter(contains_audio=True).order_by("audio_sample_rate", reverse)

    def sort_by_bitrate(self, reverse: bool = False) -> StreamQueryType:
        return self.order_by("bitrate", reverse)

    def get_by_itag(self, itag: int) -> Stream:
        return self._filter(lambda x: x.itag == itag)

    def get_by_audio_codec(self, codec: str) -> StreamQueryType:
        return self.filter(audio_codec=codec)

    def get_progressive(self) -> StreamQueryType:
        return self.filter(progressive=True)

    def get_adaptive(self) -> StreamQueryType:
        return self.filter(adaptive=True)

    def get_by_video_codec(self, codec: str) -> StreamQueryType:
        return self.filter(video_codec=codec)

    def get_by_resolution(self, resolution) -> StreamQueryType:
        return self.filter(resolution=resolution)

    def get_lowest_resolution(self) -> Stream:
        return self.filter().order_by("resolution").first

    def get_highest_resolution(self) -> Stream:
        return self.filter().order_by("resolution", reverse=True).first

    def get_audio_only(self) -> StreamQueryType:
        return self.filter(only_audio=True)

    def get_video_only(self) -> StreamQueryType:
        return self.filter(only_video=True)

    def get_video_contains(self) -> StreamQueryType:
        return self.filter(contains_video=True)

    def get_audio_contains(self) -> StreamQueryType:
        return self.filter(contains_audio=True)

    def otf(self,otf:bool=False) -> StreamQueryType:
        return self._filter([lambda s: s.is_otf == is_otf])

    def contains_audio_track_info(self, val: bool = True) -> StreamQueryType:
        return self.filter(contains_audio_track_info=val)

    def get_by_audio_track_id(self, id: str) -> StreamQueryType:
        return self.filter(audio_track_id=id)

    def get_by_audio_track_name(self, name: str) -> StreamQueryType:
        ln = name.lower()
        return self._filter([lambda x: contains_audio_track_info and audio_track_info.name.lower() == ln])

    def max_filesize(self, filesize: str):
        ...  # TODO max size

    def get_by_ext(self, ext: str)->StreamQueryType:
        return self.filter(subtype=ext)

    def hdr(self, hdr=True) -> StreamQueryType:
        return self._filter([lambda s: s.is_hdr == hdr])

    def threeD(self, threeD=True) -> StreamQueryType:
        return self._filter([lambda s:s.is_3d == threeD])

    @property
    def first(self) -> Stream:
        return self.items[0]

    @property
    def last(self) -> Stream:
        return self.items[-1]

    @property
    def reversed(self) -> StreamQueryType:
        return StreamQuery(self.items[::-1])

    @overload
    def __getitem__(self, i: slice) -> StreamQueryType:
        pass
    
    @overload
    def __getitem__(self, i: int) -> Stream:
        pass

    def __getitem__(self, i: Union[slice, int]) -> Union[StreamQueryType, Stream]:
        if isinstance(i, slice):
            return StreamQuery(self.items[i])
        return self.items[i]

    def __len__(self) -> int:
        return len(self.items)

    def __repr__(self) -> str:
        return f"<StreamQuery {self.items}/>"

    def __iter__(self):
        self.current_index = 0
        return self

    def __next__(self) -> Stream:
        if self.current_index >= len(self.items):
            raise StopIteration()
        val = self.items[self.current_index]
        self.current_index += 1
        return val
