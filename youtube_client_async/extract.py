import re
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib import parse

from .cipher import Cipher
from .exceptions import HTMLParseError, RegexMatchError
from .helpers import (
    get_text_by_runs,
    logger,
    parse_for_all_objects,
    parse_for_object,
    regex_search,
)


def generate_url_by_query(parsed_url: parse.ParseResult, query, path: str) -> str:
    rquery = parse.urlencode(query, doseq=True)
    if not rquery or len(rquery) < 2:
        rquery = ""
    else:
        rquery = "?" + rquery

    return (parsed_url.scheme + "://" + parsed_url.netloc + path 
    + parsed_url.params + rquery + parsed_url.fragment)

def time_from_url(parsed_query: dict) -> Optional[int]:
    res: str = parsed_query.get("t", [None])[0]
    if res is None:
        return None
    return int(res)
    # TODO implement hours, minuts, seconds


def playlist_id(parsed_url: parse.ParseResult, parsed_query: dict) -> str:
    val = None
    if parsed_url.hostname == "youtu.be":
        val = parsed_query["si"][0]
    else:
        val = parsed_query["list"][0]
    logger.info(f"extract playlist id {val} from {parsed_url.geturl()}")
    return val


def playlist_video_id(parsed_url: parse.ParseResult, parsed_query: dict) -> Optional[str]:
    # TODO playlist from share url
    val = None
    if parsed_url.hostname == "youtu.be":
        val = parsed_url.path[1:]
    else:
        val = parsed_query.get("v", [None])[0]
    logger.info(f"extract playlist video id {val} from {parsed_url.geturl()}")
    return val


def channel_id(url: str) -> str:
    """Extract the ``channel_name`` or ``channel_id`` from a YouTube url.

    This function supports the following patterns:

    - :samp:`https://youtube.com/c/{channel_name}/*`
    - :samp:`https://youtube.com/channel/{channel_id}/*
    - :samp:`https://youtube.com/u/{channel_name}/*`
    - :samp:`https://youtube.com/user/{channel_id}/*
    - :samp:`https://youtube.com/@{channel_id}/*

    :param str url:
        A YouTube url containing a channel name.
    :rtype: str
    :returns:
        YouTube channel name.
    """
    patterns = [
        r"(?:\/(c)\/([%\d\w_\-]+)(\/.*)?)",
        r"(?:\/(channel)\/([%\w\d_\-]+)(\/.*)?)",
        r"(?:\/(u)\/([%\d\w_\-]+)(\/.*)?)",
        r"(?:\/(user)\/([%\w\d_\-]+)(\/.*)?)",
        r"(?:\/(\@)([%\d\w_\-\.]+)(\/.*)?)",
    ]
    for pattern in patterns:
        regex = re.compile(pattern)
        function_match = regex.search(url)
        if function_match:
            logger.debug("finished regex search, matched: %s", pattern)
            uri_style = function_match.group(1)
            uri_identifier = function_match.group(2)
            val = uri_identifier if uri_style != "@" else f"@{uri_identifier}"
            logger.info(f"extract channel id {val} from {url}")
            return val
            # f'/{uri_style}/{uri_identifier}' if uri_style != '@' else f'/{uri_style}{uri_identifier}'

    raise RegexMatchError(caller="channel_name", pattern="patterns")


def video_id(parsed_url: parse.ParseResult, parsed_query: dict) -> str:
    """
    Examples:
    - http://youtu.be/SA2iWivDJiE
    - http://www.youtube.com/watch?v=_oPAwA_Udwc&feature=feedu
    - http://www.youtube.com/embed/SA2iWivDJiE
    - http://www.youtube.com/v/SA2iWivDJiE?version=3&amp;hl=en_US
    """
    val = None
    if parsed_url.hostname == "youtu.be":
        val = parsed_url.path[1:]
    elif parsed_url.path.startswith("/shorts"):
        val = parsed_url.path.split("/")[-1]
    elif parsed_url.hostname in ("www.youtube.com", "youtube.com"):
        if parsed_url.path == "/watch":
            val = parsed_query["v"][0]
        if parsed_url.path[:7] == "/embed/":
            val = parsed_url.path.split("/")[2]
        if parsed_url.path[:3] == "/v/":
            val = parsed_url.path.split("/")[2]
    logger.info(f"extract video id {val} {parsed_url.geturl()}")
    if val is None:
        raise Exception(f"cant extract video id from url {parsed_url.geturl()}")
    return val

def post_id(parsed_url: parse.ParseResult) -> str:
    if parsed_url.hostname in ("www.youtube.com", "youtube.com"):
        if parsed_url.path[:6] == "/post/":
            val = parsed_url.path.split("/")[2]
            logger.info(f"extract post id {val} {parsed_url.geturl()}")
            return val
    raise Exception(f"cant get post id from url {parsed_url.geturl()}")


def short_id(url: str) -> str:
    val = regex_search(r"(?:\/shorts\/)([0-9A-Za-z_-]{11}).*", url, group=1)
    logger.info(f"extract short id {val} {url}")
    if val is None:
        raise Exception(f"cant get short id from url {url}")
    return val


def get_comment_id(parsed_query: dict) -> Optional[Union[str, List[str]]]:
    cid: str = parsed_query.get("lc", [None])[0]
    if cid is None:
        raise Exception(f"cant get comment id from parsed_query {parsed_query}")#TODO get_url
    val = None
    if "." in cid:
        val = cid.split(".")
    else:
        val = cid
    logger.info(f"extract comment id {val} from {parsed_query}")#TODO in url


def video_info_url(video_id: str, watch_url: str) -> str:
    """Construct the video_info url.

    :param str video_id:
        A YouTube video identifier.
    :param str watch_url:
        A YouTube watch url.
    :rtype: str
    :returns:
        :samp:`https://youtube.com/get_video_info` with necessary GET
        parameters.
    """
    params = OrderedDict(
        [
            ("video_id", video_id),
            ("ps", "default"),
            ("eurl", parse.quote(watch_url)),
            ("hl", "ru_RU"),
            ("html5", "1"),
            ("c", "TVHTML5"),
            ("cver", "7.20201028"),
        ]
    )
    return _video_info_url(params)


def video_info_url_age_restricted(video_id: str, embed_html: str) -> str:
    """Construct the video_info url.

    :param str video_id:
        A YouTube video identifier.
    :param str embed_html:
        The html contents of the embed page (for age restricted videos).
    :rtype: str
    :returns:
        :samp:`https://youtube.com/get_video_info` with necessary GET
        parameters.
    """
    try:
        sts = regex_search(r'"sts"\s*:\s*(\d+)', embed_html, group=1)
    except RegexMatchError:
        sts = ""
    # Here we use ``OrderedDict`` so that the output is consistent between
    eurl = f"https://youtube.googleapis.com/v/{video_id}"
    params = OrderedDict(
        [
            ("video_id", video_id),
            ("eurl", eurl),
            ("sts", sts),
            ("html5", "1"),
            ("c", "TVHTML5"),
            ("cver", "7.20201028"),
        ]
    )
    return _video_info_url(params)


def _video_info_url(params: OrderedDict) -> str:
    return "https://www.youtube.com/get_video_info?" + parse.urlencode(params)


def js_url(html: str) -> str:
    """Get the base JavaScript url.

    Construct the base JavaScript url, which contains the decipher
    "transforms".

    :param str html:
        The html contents of the watch page.
    """
    try:
        base_js = get_ytplayer_config(html)["assets"]["js"]
    except (KeyError, RegexMatchError):
        base_js = get_ytplayer_js(html)
    return "https://youtube.com" + base_js


def mime_type_codec(mime_type_codec: str) -> Tuple[str, List[str]]:
    """Parse the type data.

    Breaks up the data in the ``type`` key of the manifest, which contains the
    mime type and codecs serialized together, and splits them into separate
    elements.

    **Example**:

    mime_type_codec('audio/webm; codecs="opus"') -> ('audio/webm', ['opus'])

    :param str mime_type_codec:
        String containing mime type and codecs.
    :rtype: tuple
    :returns:
        The mime type and a list of codecs.

    """
    pattern = r"(\w+\/\w+)\;\scodecs=\"([a-zA-Z-0-9.,\s]*)\""
    regex = re.compile(pattern)
    results = regex.search(mime_type_codec)
    if not results:
        raise RegexMatchError(caller="mime_type_codec", pattern=pattern)
    mime_type, codecs = results.groups()
    return mime_type, [c.strip() for c in codecs.split(",")]


def get_ytplayer_js(html: str) -> Any:
    """Get the YouTube player base JavaScript path.

    :param str html
        The html contents of the watch page.
    :rtype: str
    :returns:
        Path to YouTube's base.js file.
    """
    js_url_patterns = [r"(/s/player/[\w\d]+/[\w\d_/.]+/base\.js)"]
    for pattern in js_url_patterns:
        regex = re.compile(pattern)
        function_match = regex.search(html)
        if function_match:
            logger.debug("finished regex search, matched: %s", pattern)
            yt_player_js = function_match.group(1)
            return yt_player_js

    raise RegexMatchError(caller="get_ytplayer_js", pattern="js_url_patterns")


def get_ytplayer_config(html: str) -> Any:
    """Get the YouTube player configuration data from the watch html.

    Extract the ``ytplayer_config``, which is json data embedded within the
    watch html and serves as the primary source of obtaining the stream
    manifest data.

    :param str html:
        The html contents of the watch page.
    :rtype: str
    :returns:
        Substring of the html containing the encoded manifest data.
    """
    logger.debug("finding initial function name")
    config_patterns = [r"ytplayer\.config\s*=\s*", r"ytInitialPlayerResponse\s*=\s*"]
    for pattern in config_patterns:
        # Try each pattern consecutively if they don't find a match
        try:
            res = parse_for_object(html, pattern)
            if res["playabilityStatus"]["status"] == "ERROR":
                raise Exception(
                    res["playabilityStatus"]["status"]
                    + "; "
                    + res["playabilityStatus"]["reason"]
                )
            return res
        except HTMLParseError as e:
            logger.debug(f"Pattern failed: {pattern}")
            logger.debug(e)
            continue

    # setConfig() needs to be handled a little differently.
    # We want to parse the entire argument to setConfig()
    # and use then load that as json to find PLAYER_CONFIG
    # inside of it.
    setconfig_patterns = [r"yt\.setConfig\(.*['\"]PLAYER_CONFIG['\"]:\s*"]
    for pattern in setconfig_patterns:
        # Try each pattern consecutively if they don't find a match
        try:
            res = parse_for_object(html, pattern)
            if res["playabilityStatus"]["status"] == "ERROR":
                raise Exception(
                    res["playabilityStatus"]["status"]
                    + "; "
                    + res["playabilityStatus"]["reason"]
                )
            return res
        except HTMLParseError:
            continue

    raise RegexMatchError(
        caller="get_ytplayer_config", pattern="config_patterns, setconfig_patterns"
    )


def get_ytcfg(html: str) -> dict:
    """Get the entirety of the ytcfg object.

    This is built over multiple pieces, so we have to find all matches and
    combine the dicts together.

    :param str html:
        The html contents of the watch page.
    :rtype: str
    :returns:
        Substring of the html containing the encoded manifest data.
    """
    ytcfg = {}
    ytcfg_patterns = [r"ytcfg\s=\s", r"ytcfg\.set\("]
    for pattern in ytcfg_patterns:
        # Try each pattern consecutively and try to build a cohesive object
        try:
            found_objects = parse_for_all_objects(html, pattern)
            for obj in found_objects:
                ytcfg.update(obj)
        except HTMLParseError:
            continue

    if len(ytcfg) > 0:
        return ytcfg

    raise RegexMatchError(caller="get_ytcfg", pattern="ytcfg_pattenrs")


def initial_data(watch_html: str) -> str:
    """Extract the ytInitialData json from the watch_html page.

    This mostly contains metadata necessary for rendering the page on-load,
    such as video information, copyright notices, etc.

    @param watch_html: Html of the watch page
    @return:
    """
    patterns = [r"window\[['\"]ytInitialData['\"]]\s*=\s*", r"ytInitialData\s*=\s*"]
    for pattern in patterns:
        try:
            res = parse_for_object(watch_html, pattern)
            try:
                message_container = res["contents"]["twoColumnWatchNextResults"][
                    "results"]["results"]["contents"][0]["itemSectionRenderer"][
                    "contents"][0]
                if "backgroundPromoRenderer" in message_container:
                    raise Exception(
                        get_text_by_runs(message_container["backgroundPromoRenderer"]["title"])
                    )
            except KeyError:
                pass
            try:
                message_container = res["alerts"][0]["alertRenderer"]
                if message_container["type"] == "ERROR":
                    raise Exception(
                        get_text_by_runs(message_container["text"])
                    )
            except KeyError:
                pass
            return res
        except HTMLParseError:
            pass

    raise RegexMatchError(caller="initial_data", pattern="initial_data_pattern")


def initial_player_response(watch_html: str) -> str:
    """Extract the ytInitialPlayerResponse json from the watch_html page.

    This mostly contains metadata necessary for rendering the page on-load,
    such as video information, copyright notices, etc.

    @param watch_html: Html of the watch page
    @return:
    """
    patterns = [
        r"window\[['\"]ytInitialPlayerResponse['\"]]\s*=\s*",
        r"ytInitialPlayerResponse\s*=\s*",
    ]
    for pattern in patterns:
        try:
            return parse_for_object(watch_html, pattern)
        except HTMLParseError:
            pass

    raise RegexMatchError(
        caller="initial_player_response", pattern="initial_player_response_pattern"
    )

def signature_timestamp(js: str) -> str:
    return regex_search(r"signatureTimestamp:(\d*)", js, group=1)

def apply_signature(stream_manifest: Dict, vid_info: Dict, js: str, url_js: str) -> None:
    """Apply the decrypted signature to the stream manifest.

    :param dict stream_manifest:
        Details of the media streams available.
    :param str js:
        The contents of the base.js asset file.
    :param str url_js:
        Full base.js url

    """
    cipher = Cipher(js=js, js_url=url_js)
    discovered_n = dict()
    for i, stream in enumerate(stream_manifest):
        try:
            url: str = stream["url"]
        except KeyError:
            live_stream = (
                vid_info.get("playabilityStatus", {}, )
                .get("liveStreamability")
            )
            if live_stream:
                raise Exception("live_stream error")

        parsed_url = parse.urlparse(url)

        # Convert query params off url to dict
        query_params = parse.parse_qs(parsed_url.query)
        query_params = {
            k: v[0] for k, v in query_params.items()
        }

        # 403 Forbidden fix.
        if "signature" in url or (
                "s" not in stream and ("&sig=" in url or "&lsig=" in url)
        ):
            # For certain videos, YouTube will just provide them pre-signed, in
            # which case there's no real magic to download them and we can skip
            # the whole signature descrambling entirely.
            logger.debug("signature found, skip decipher")

        else:
            signature = cipher.get_signature(ciphered_signature=stream["s"])

            logger.debug(
                "finished descrambling signature for itag=%s", stream["itag"]
            )

            query_params['sig'] = signature

        if 'n' in query_params.keys():
            # For WEB-based clients, YouTube sends an "n" parameter that throttles download speed.
            # To decipher the value of "n", we must interpret the player's JavaScript.

            initial_n = query_params['n']

            # Check if any previous stream decrypted the parameter
            if initial_n not in discovered_n:
                discovered_n[initial_n] = cipher.get_throttling(initial_n)

            new_n = discovered_n[initial_n]
            query_params['n'] = new_n

        url = f'{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?{parse.urlencode(query_params)}'  # noqa:E501

        stream_manifest[i]["url"] = url


def apply_descrambler(stream_data: Dict) -> Optional[List[Dict]]:
    """Apply various in-place transforms to YouTube's media stream data.

    Creates a ``list`` of dictionaries by string splitting on commas, then
    taking each list item, parsing it as a query string, converting it to a
    ``dict`` and unquoting the value.

    :param dict stream_data:
        Dictionary containing query string encoded values.

    **Example**:

    >>> d = {'foo': 'bar=1&var=test,em=5&t=url%20encoded'}
    >>> apply_descrambler(d, 'foo')
    >>> print(d)
    {'foo': [{'bar': '1', 'var': 'test'}, {'em': '5', 't': 'url encoded'}]}

    """
    if 'url' in stream_data:
        return None

    # Merge formats and adaptiveFormats into a single list
    formats: list[Dict] = []
    if 'formats' in stream_data.keys():
        formats.extend(stream_data['formats'])
    if 'adaptiveFormats' in stream_data.keys():
        formats.extend(stream_data['adaptiveFormats'])

    # Extract url and s from signatureCiphers as necessary
    for data in formats:
        if 'url' not in data and 'signatureCipher' in data:
            cipher_url = parse.parse_qs(data['signatureCipher'])
            data['url'] = cipher_url['url'][0]
            data['s'] = cipher_url['s'][0]
        data['is_otf'] = data.get('type') == 'FORMAT_STREAM_TYPE_OTF'

    logger.debug("applying descrambler")
    return formats
