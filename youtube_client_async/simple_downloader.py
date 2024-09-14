import asyncio
import time
from typing import Callable, Optional

import aiohttp

from . import exceptions, net, stream
from .helpers import logger


class DownloadingLiveError(exceptions.YoutubeClientError):
    def __init__(self, *args):
        super().__init__("downloading live stream is not supported")


async def _load_video_stream_part(
    url: str,
    start: int,
    end: int,
    net_obj: net.SessionRequest,
    chunk_size: int = 1024*10,
    timeout: int = 10,
    max_retries: int = 1
    ):
    retries = 0
    while True:
        try:
            range_param = f"&range={start}-{end}"
            response = await net_obj._send("GET", url + range_param, timeout=timeout)  # TODO header Range
            log_str = f"Getting {range_param} len={response.content_length}"
            logger.info(log_str)
            async for chunk in response.content.iter_chunked(chunk_size):
                yield chunk
            # yield await response.read()
            return
        except (aiohttp.client_exceptions.ClientConnectionError, asyncio.TimeoutError):
            # aiohttp.client_exceptions.ClientResponseError 404 ?
            retries += 1
            if retries > max_retries + 1:
                raise Exception(f"max retries {retries} from {max_retries}")


async def simple_video_stream(
    url: str,
    net_obj: net.SessionRequest,
    max_retries: int = 1,
    timeout: int = 10,
    url_chunk_size: int = 1024*1024*10,
    chunk_size: int = 1024 * 10,
    filesize: Optional[int] = None
    ):

    if filesize is None:
        try:
            filesize = await net_obj.get_lenght(url)
        except:
            filesize = await net_obj.seq_filesize(url)
    downloaded = 0
    while downloaded < filesize if filesize else True:
        start_pos = downloaded
        stop_pos = start_pos + url_chunk_size if filesize == 0 else min(filesize, start_pos + url_chunk_size)
        first_chunk = None
        try:
            async for mchunk in _load_video_stream_part(url, start_pos, stop_pos, net_obj, chunk_size, timeout, max_retries):
                if first_chunk is None:
                    first_chunk = mchunk
                    if not first_chunk:
                        return
                if not mchunk:
                    break
                downloaded += len(mchunk)
                yield mchunk
        except aiohttp.client_exceptions.ClientResponseError as e:
            if e.status == 400:
                return
            raise e


async def simple_download(
    stream: stream.Stream,
    filepath: str,  # TODO helpers.generate_unique_file_name Моржовый  оператор работает 3.8?
    net_obj: Optional[net.SessionRequest] = None,  # TODO send to stream info dict about video (title, lenght, is_live, upload_date, owner_name)
    max_retries: int = 1,
    timeout: int = 10,
    url_chunk_size: int = 1024 * 1024 * 10,
    chunk_size: int = 1024 * 10,
    callback: Optional[Callable[[bytes, int, int], None]] = None,
    ) -> int:
    """filepath is path to filename without extantion"""
    if stream.is_live:
        raise DownloadingLiveError("cant work on live streams")
    current_net_obj: net.SessionRequest = net_obj if net_obj else stream.net_obj
    filesize = await stream.get_filesize()
    filesize_mb = filesize / (1024 * 1024)
    logger.info(f"stream filesize is {filesize_mb} mb")
    downloaded = 0
    ctime = time.time()
    with open(f"{filepath}.{stream.ext}","wb") as file:
        async for x in simple_video_stream(
            stream.url,
            current_net_obj,
            max_retries,
            timeout,
            url_chunk_size,
            chunk_size,
            filesize
        ):
            file.write(x)
            downloaded += len(x)
            if callback:
                callback(x, downloaded, filesize)
    time_delta = time.time() - ctime
    logger.info(f"downloaded {downloaded/(1024*1024)} mb  from {filesize_mb} mb")
    logger.info(f"downloaded in {time_delta} seconds")
    logger.info(f"{filesize_mb / time_delta} mb/sec")
    return filesize
