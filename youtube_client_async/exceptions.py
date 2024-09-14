from typing import Pattern, Union


class YoutubeClientError(Exception):
    """Base exception"""
    def __init__(self, *args):
        super().__init__(*args)


class HTMLParseError(YoutubeClientError):
    """HTML could not be parsed"""


class ExtractError(YoutubeClientError):
    """Data extraction based exception."""


class RegexMatchError(ExtractError):
    def __init__(self, caller: str, pattern: Union[str, Pattern]):
        super().__init__(f"{caller}: could not find match for {pattern}")
        self.caller = caller
        self.pattern = pattern


class VideoUnavailable(YoutubeClientError):
    """Base video unavailable error."""

    def __init__(self, video_id: str):
        """
        :param str video_id:
            A YouTube video identifier.
        """
        self.video_id = video_id
        super().__init__(self.error_string)

    @property
    def error_string(self):
        return f"{self.video_id} is unavailable"


class AgeRestrictedError(VideoUnavailable):
    """Video is age restricted, and cannot be accessed without authorization."""

    def __init__(self, video_id: str):
        self.video_id = video_id
        super().__init__(self.video_id)

    @property
    def error_string(self):
        return f"{self.video_id} is age restricted, and can't be accessed without logging in."


class VideoPrivate(VideoUnavailable):
    def __init__(self, video_id: str):
        """
        :param str video_id:
            A YouTube video identifier.
        """
        self.video_id = video_id
        super().__init__(self.video_id)

    @property
    def error_string(self):
        return f"{self.video_id} is a private video"


class RecordingUnavailable(VideoUnavailable):
    def __init__(self, video_id: str):
        """
        :param str video_id:
            A YouTube video identifier.
        """
        self.video_id = video_id
        super().__init__(self.video_id)

    @property
    def error_string(self):
        return f"{self.video_id} does not have a live stream recording available"


class MembersOnly(VideoUnavailable):
    """Video is members-only.

    YouTube has special videos that are only viewable to users who have
    subscribed to a content creator.
    ref: https://support.google.com/youtube/answer/7544492?hl=en
    """

    def __init__(self, video_id: str):
        self.video_id = video_id
        super().__init__(self.video_id)

    @property
    def error_string(self):
        return f"{self.video_id} is a members-only video"


class VideoRegionBlocked(VideoUnavailable):
    def __init__(self, video_id: str):
        self.video_id = video_id
        super().__init__(self.video_id)

    @property
    def error_string(self):
        return f"{self.video_id} is not available in your region"
