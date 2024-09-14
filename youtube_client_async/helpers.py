import ast
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from random import choice
from string import ascii_lowercase, ascii_uppercase
from typing import Any, Optional, Union

from .exceptions import HTMLParseError, RegexMatchError

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")  # - %(name)s
handler.setFormatter(formatter)
# logger.addHandler(handler)


def is_vereficated(raw) -> bool:
    try:
        return raw["ownerBadges"][0]["metadataBadgeRenderer"]["style"] == "BADGE_STYLE_TYPE_VERIFIED"
    except (KeyError, IndexError):
        return False

def get_text_by_runs(raw) -> str:
    return " ".join([x["text"] for x in raw["runs"]])


def parse_for_all_objects(html, preceding_regex):
    """Parses input html to find all matches for the input starting point.

    :param str html:
        HTML to be parsed for an object.
    :param str preceding_regex:
        Regex to find the string preceding the object.
    :rtype list:
    :returns:
        A list of dicts created from parsing the objects.
    """
    result = []
    regex = re.compile(preceding_regex)
    match_iter = regex.finditer(html)
    for match in match_iter:
        if match:
            start_index = match.end()
            try:
                obj = parse_for_object_from_startpoint(html, start_index)
            except HTMLParseError:
                # Some of the instances might fail because set is technically
                # a method of the ytcfg object. We'll skip these since they
                # don't seem relevant at the moment.
                continue
            else:
                result.append(obj)

    if len(result) == 0:
        raise HTMLParseError(f"No matches for regex {preceding_regex}")

    return result


def parse_for_object(html, preceding_regex):
    """Parses input html to find the end of a JavaScript object.

    :param str html:
        HTML to be parsed for an object.
    :param str preceding_regex:
        Regex to find the string preceding the object.
    :rtype dict:
    :returns:
        A dict created from parsing the object.
    """
    regex = re.compile(preceding_regex)
    result = regex.search(html)
    if not result:
        raise HTMLParseError(f"No matches for regex {preceding_regex}")

    start_index = result.end()
    return parse_for_object_from_startpoint(html, start_index)


def find_object_from_startpoint(html, start_point):
    """Parses input html to find the end of a JavaScript object.

    :param str html:
        HTML to be parsed for an object.
    :param int start_point:
        Index of where the object starts.
    :rtype dict:
    :returns:
        A dict created from parsing the object.
    """
    html = html[start_point:]
    if html[0] not in ["{", "["]:
        raise HTMLParseError(f"Invalid start point. Start of HTML:\n{html[:20]}")

    # First letter MUST be a open brace, so we put that in the stack,
    # and skip the first character.
    last_char = "{"
    curr_char = None
    stack = [html[0]]
    i = 1

    context_closers = {"{": "}", "[": "]", '"': '"', "/": "/"}  # javascript regex

    while i < len(html):
        if len(stack) == 0:
            break
        if curr_char not in [" ", "\n"]:
            last_char = curr_char
        curr_char = html[i]
        curr_context = stack[-1]

        # If we've reached a context closer, we can remove an element off the stack
        if curr_char == context_closers[curr_context]:
            stack.pop()
            i += 1
            continue

        # Strings and regex expressions require special context handling because they can contain
        #  context openers *and* closers
        if curr_context in ['"', "/"]:
            # If there's a backslash in a string or regex expression, we skip a character
            if curr_char == "\\":
                i += 2
                continue
        else:
            # Non-string contexts are when we need to look for context openers.
            if curr_char in context_closers.keys():
                # Slash starts a regular expression depending on context
                if not (
                    curr_char == "/"
                    and last_char
                    not in ["(", ",", "=", ":", "[", "!", "&", "|", "?", "{", "}", ";"]
                ):
                    stack.append(curr_char)

        i += 1

    full_obj = html[:i]
    return full_obj


def parse_for_object_from_startpoint(html, start_point):
    """JSONifies an object parsed from HTML.

    :param str html:
        HTML to be parsed for an object.
    :param int start_point:
        Index of where the object starts.
    :rtype dict:
    :returns:
        A dict created from parsing the object.
    """
    full_obj = find_object_from_startpoint(html, start_point)
    try:
        return json.loads(full_obj)
    except Exception:
        try:
            return ast.literal_eval(full_obj)
        except (ValueError, SyntaxError):
            raise HTMLParseError("Could not parse object.")


def throttling_array_split(js_array):
    """Parses the throttling array into a python list of strings.

    Expects input to begin with `[` and close with `]`.

    :param str js_array:
        The javascript array, as a string.
    :rtype: list:
    :returns:
        A list of strings representing splits on `,` in the throttling array.
    """
    results = []
    curr_substring = js_array[1:]

    comma_regex = re.compile(r",")
    func_regex = re.compile(r"function\([^)]*\)")

    while len(curr_substring) > 0:
        if curr_substring.startswith("function"):
            # Handle functions separately. These can contain commas
            match = func_regex.search(curr_substring)
            match_start, match_end = match.span()

            function_text = find_object_from_startpoint(curr_substring, match.span()[1])
            full_function_def = curr_substring[: match_end + len(function_text)]
            results.append(full_function_def)
            curr_substring = curr_substring[len(full_function_def) + 1:]
        else:
            match = comma_regex.search(curr_substring)

            # Try-catch to capture end of array
            try:
                match_start, match_end = match.span()
            except AttributeError:
                match_start = len(curr_substring) - 1
                match_end = match_start + 1

            curr_el = curr_substring[:match_start]
            results.append(curr_el)
            curr_substring = curr_substring[match_end:]

    return results


def regex_search(
    pattern: str, string: str, group: Optional[int] = None
) -> Union[str, Any]:
    """Shortcut method to search a string for a given pattern.

    :param str pattern:
        A regular expression pattern.
    :param str string:
        A target string to search.
    :param int group:
        Index of group to return.
    :rtype:
        str or tuple
    :returns:
        Substring pattern matches.
    """
    regex = re.compile(pattern)
    results = regex.search(string)
    if not results:
        raise RegexMatchError(caller="regex_search", pattern=pattern)
    logger.debug("matched regex search: %s", pattern)
    if group is None:
        return results.groups()
    return results.group(group)


def generate_random_str(lenght: int = 12) -> str:
    list_vars = (
        list(ascii_uppercase) + list(ascii_lowercase) + list(map(str, range(0, 10)))
    )
    return "".join([choice(list_vars) for x in range(lenght)])

def create_dirs(path: str):
    path_dir = Path(path)
    cpath = path_dir if path_dir.is_dir() else path_dir.parent
    if not cpath.exists():
        cpath.mkdir(parents=True, exist_ok=True)
    return cpath.absolute().resolve()

def generate_filename(directory_path: str, ext: str, prefix: str = "file_") -> str:
    path_dir = create_dirs(directory_path)
    clen = 6
    try_count = 0
    while True:
        cpath = path_dir.absolute().with_name(prefix + generate_random_str(clen + try_count // 10)+ f".{ext}")
        if not cpath.exists():
            return cpath.resolve()
        try_count +=1


class NoneDictElement:
    pass


def can_convert_to_int(s):
    try:
        return int(s)
    except ValueError:
        return False


def get_from_dict(
    source: dict,
    path: str,
    separator: str = "|",
    default: Any = None,
    throw_ex: bool = True,
    int_include: bool = False,
) -> Any:
    path_r = path.split(separator.strip())
    val = source
    for i, x in enumerate(path_r):
        if isinstance(val, list) and int_include:
            val = val[int(x)]
        else:
            val = val.get(x, NoneDictElement)
        if val == NoneDictElement:
            if not throw_ex:
                return default
            # last_val = '"[' + path_r[i] + '"]'
            last_last_val = '["' + path_r[i - 1] + '"]' if i - 1 >= 0 else None
            raise KeyError(
                f"helper.get_from_dict {last_last_val if last_last_val else str() }\n"
                + str(path_r)
            )
    return val