import json
import os
import time
from typing import Optional

from . import helpers, net
from .helpers import logger  # TODO logging innertube

# YouTube on TV client secrets
_client_id = "861556708454-d6dlm3lh05idd8npek18k6be8ba3oc68.apps.googleusercontent.com"
_client_secret = "SboVhoG9s0rNafixCSGGKXAT"

# Extracted API keys -- unclear what these are linked to.
# API keys are not required, see: https://github.com/TeamNewPipe/NewPipeExtractor/pull/1168
_api_keys = [
    "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8",
    "AIzaSyCtkvNIR1HCEwzsqK6JuE6KqpyjusIRI30",
    "AIzaSyA8eiZmM1FaDVjRy-df2KTyQ_vz_yYM39w",
    "AIzaSyC8UYZpvA2eknNex0Pjid0_eTLJoDu6los",
    "AIzaSyCjc_pVEDi4qsv5MtC2dMXzpIaDoRFLsxw",
    "AIzaSyDHQ9ipnphqTzDqZsbtd8_Ru4_kiKVQe2k",
]

_default_clients = {
        'WEB': {
        'innertube_context': {
            'context': {
                'client': {
                    'clientName': 'WEB',
                    'osName': 'Windows',
                    'osVersion': '10.0',
                    'clientVersion': '2.20240709.01.00',
                    'platform': 'DESKTOP'
                }
            }
        },
        'header': {
            'User-Agent': 'Mozilla/5.0',
            'X-Youtube-Client-Name': '1',
            'X-Youtube-Client-Version': '2.20240709.01.00'
        },
        'api_key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
        'require_js_player': True
    },

    'WEB_EMBED': {
        'innertube_context': {
            'context': {
                'client': {
                    'clientName': 'WEB_EMBEDDED_PLAYER',
                    'osName': 'Windows',
                    'osVersion': '10.0',
                    'clientVersion': '2.20240530.02.00',
                    'clientScreen': 'EMBED'
                }
            }
        },
        'header': {
            'User-Agent': 'Mozilla/5.0',
            'X-Youtube-Client-Name': '56'
        },
        'api_key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
        'require_js_player': True
    },

    'WEB_MUSIC': {
        'innertube_context': {
            'context': {
                'client': {
                    'clientName': 'WEB_REMIX',
                    'clientVersion': '1.20240403.01.00'
                }
            }
        },
        'header': {
            'User-Agent': 'Mozilla/5.0',
            'X-Youtube-Client-Name': '67'
        },
        'api_key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
        'require_js_player': True
    },

    'WEB_CREATOR': {
        'innertube_context': {
            'context': {
                'client': {
                    'clientName': 'WEB_CREATOR',
                    'clientVersion': '1.20220726.00.00'
                }
            }
        },
        'header': {
            'User-Agent': 'Mozilla/5.0',
            'X-Youtube-Client-Name': '62'
        },
        'api_key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
        'require_js_player': True
    },

    'WEB_SAFARI': {
        'innertube_context': {
            'context': {
                'client': {
                    'clientName': 'WEB',
                    'clientVersion': '2.20240726.00.00',
                }
            }
        },
        'header': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Safari/605.1.15,gzip(gfe)',
            'X-Youtube-Client-Name': '1'
        },
        'api_key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
        'require_js_player': True
    },

    'MWEB': {
        'innertube_context': {
            'context': {
                'client': {
                    'clientName': 'MWEB',
                    'clientVersion': '2.20240726.01.00'
                }
            }
        },
        'header': {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36',
            'X-Youtube-Client-Name': '2'
        },
        'api_key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
        'require_js_player': True
    },
    'ANDROID': {
        'innertube_context': {
            'context': {
                'client': {
                    'clientName': 'ANDROID',
                    'clientVersion': '19.29.37',
                    'platform': 'MOBILE',
                    'osName': 'Android',
                    'osVersion': '14',
                    'androidSdkVersion': '34'
                }
            }
        },
        'header': {
            'User-Agent': 'com.google.android.youtube/',
            'X-Youtube-Client-Name': '3'
        },
        'api_key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
        'require_js_player': False
    },
    # Deprecated
    #   'ANDROID_EMBED': {
    #     'innertube_context': {
    #         'context': {
    #             'client': {
    #                 'clientName': 'ANDROID_EMBEDDED_PLAYER',
    #                 'clientVersion': '19.13.36',
    #                 'clientScreen': 'EMBED',
    #                 'androidSdkVersion': '30'
    #             }
    #         }
    #     },
    #     'header': {
    #         'User-Agent': 'com.google.android.youtube/',
    #         'X-Youtube-Client-Name': '55',
    #         'X-Youtube-Client-Version': '19.13.36'
    #     },
    #     'api_key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
    #     'require_js_player': False
    # },
    'ANDROID_VR': {
        'innertube_context': {
            'context': {
                'client': {
                    'clientName': 'ANDROID_VR',
                    'clientVersion': '1.57.29',
                    'deviceMake': 'Oculus',
                    'deviceModel': 'Quest 3',
                    'osName': 'Android',
                    'osVersion': '12L',
                    'androidSdkVersion': '32'
                }
            }
        },
        'header': {
            'User-Agent': 'com.google.android.apps.youtube.vr.oculus/1.57.29 (Linux; U; Android 12L; eureka-user Build/SQ3A.220605.009.A1) gzip',
            'X-Youtube-Client-Name': '28'
        },
        'api_key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
        'require_js_player': False
    },
    'ANDROID_MUSIC': {
        'innertube_context': {
            'context': {
                'client': {
                    'clientName': 'ANDROID_MUSIC',
                    'clientVersion': '7.11.50',
                    'androidSdkVersion': '30',
                    'osName': 'Android',
                    'osVersion': '11'
                }
            }
        },
        'header': {
            'User-Agent': 'com.google.android.apps.youtube.music/7.11.50 (Linux; U; Android 11) gzip',
            'X-Youtube-Client-Name': '21'
        },
        'api_key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
        'require_js_player': False
    },
    'ANDROID_CREATOR': {
        'innertube_context': {
            'context': {
                'client': {
                    'clientName': 'ANDROID_CREATOR',
                    'clientVersion': '24.30.100',
                    'androidSdkVersion': '30',
                    'osName': 'Android',
                    'osVersion': '11'
                }
            }
        },
        'header': {
            'User-Agent': 'com.google.android.apps.youtube.creator/24.30.100 (Linux; U; Android 11) gzip',
            'X-Youtube-Client-Name': '14'
        },
        'api_key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
        'require_js_player': False
    },
    'ANDROID_TESTSUITE': {
        'innertube_context': {
            'context': {
                'client': {
                    'clientName': 'ANDROID_TESTSUITE',
                    'clientVersion': '1.9',
                    'platform': 'MOBILE',
                    'osName': 'Android',
                    'osVersion': '14',
                    'androidSdkVersion': '34'
                }
            }
        },
        'header': {
            'User-Agent': 'com.google.android.youtube/',
            'X-Youtube-Client-Name': '30',
            'X-Youtube-Client-Version': '1.9'
        },
        'api_key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
        'require_js_player': False
    },
    'ANDROID_PRODUCER': {
        'innertube_context': {
            'context': {
                'client': {
                    'clientName': 'ANDROID_PRODUCER',
                    'clientVersion': '0.111.1',
                    'androidSdkVersion': '30',
                    'osName': 'Android',
                    'osVersion': '11'
                }
            }
        },
        'header': {
            'User-Agent': 'com.google.android.apps.youtube.producer/0.111.1 (Linux; U; Android 11) gzip',
            'X-Youtube-Client-Name': '91'
        },
        'api_key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
        'require_js_player': False
    },
    'IOS': {
        'innertube_context': {
            'context': {
                'client': {
                    'clientName': 'IOS',
                    'clientVersion': '19.29.1',
                    'deviceMake': 'Apple',
                    'platform': 'MOBILE',
                    'osName': 'iPhone',
                    'osVersion': '17.5.1.21F90',
                    'deviceModel': 'iPhone16,2'
                }
            }
        },
        'header': {
            'User-Agent': 'com.google.ios.youtube/19.29.1 (iPhone16,2; U; CPU iOS 17_5_1 like Mac OS X;)',
            'X-Youtube-Client-Name': '5'
        },
        'api_key': 'AIzaSyB-63vPrdThhKuerbB2N_l7Kwwcxj6yUAc',
        'require_js_player': False
    },
    # Deprecated
    # 'IOS_EMBED': {
    #     'innertube_context': {
    #         'context': {
    #             'client': {
    #                 'clientName': 'IOS_MESSAGES_EXTENSION',
    #                 'clientVersion': '19.16.3',
    #                 'deviceMake': 'Apple',
    #                 'platform': 'MOBILE',
    #                 'osName': 'iOS',
    #                 'osVersion': '17.4.1.21E237',
    #                 'deviceModel': 'iPhone15,5'
    #             }
    #         }
    #     },
    #     'header': {
    #         'User-Agent': 'com.google.ios.youtube/',
    #         'X-Youtube-Client-Name': '66'
    #     },
    #     'api_key': 'AIzaSyB-63vPrdThhKuerbB2N_l7Kwwcxj6yUAc',
    #     'require_js_player': False
    # },
    'IOS_MUSIC': {
        'innertube_context': {
            'context': {
                'client': {
                    'clientName': 'IOS_MUSIC',
                    'clientVersion': '7.08.2',
                    'deviceMake': 'Apple',
                    'platform': 'MOBILE',
                    'osName': 'iPhone',
                    'osVersion': '17.5.1.21F90',
                    'deviceModel': 'iPhone16,2'
                }
            }
        },
        'header': {
            'User-Agent': 'com.google.ios.youtubemusic/7.08.2 (iPhone16,2; U; CPU iOS 17_5_1 like Mac OS X;)',
            'X-Youtube-Client-Name': '26'
        },
        'api_key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
        'require_js_player': False
    },
    'IOS_CREATOR': {
        'innertube_context': {
            'context': {
                'client': {
                    'clientName': 'IOS_CREATOR',
                    'clientVersion': '24.30.100',
                    'deviceMake': 'Apple',
                    'deviceModel': 'iPhone16,2',
                    'osName': 'iPhone',
                    'osVersion': '17.5.1.21F90'
                }
            }
        },
        'header': {
            'User-Agent': 'com.google.ios.ytcreator/24.30.100 (iPhone16,2; U; CPU iOS 17_5_1 like Mac OS X;)',
            'X-Youtube-Client-Name': '15'
        },
        'api_key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
        'require_js_player': False
    },
    'TV_EMBED': {
        'innertube_context': {
            'context': {
                'client': {
                    'clientName': 'TVHTML5_SIMPLY_EMBEDDED_PLAYER',
                    'clientVersion': '2.0',
                    'clientScreen': 'EMBED',
                    'platform': 'TV'
                }
            }
        },
        'header': {
            'User-Agent': 'Mozilla/5.0',
            'X-Youtube-Client-Name': '85'
        },
        'api_key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
        'require_js_player': True
    },
    'MEDIA_CONNECT': {
        'innertube_context': {
            'context': {
                'client': {
                    'clientName': 'MEDIA_CONNECT_FRONTEND',
                    'clientVersion': '0.1'
                }
            }
        },
        'header': {
            'User-Agent': 'Mozilla/5.0',
            'X-Youtube-Client-Name': '95'
        },
        'api_key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
        'require_js_player': False
    }
}
_token_file = "tokens.json"


class InnerTube:
    __slots__ = (
        "token_timeout",
        "token_file",
        "innertube_context",
        "header",
        "api_key",
        "require_js_player",
        "access_token",
        "refresh_token",
        "use_oauth",
        "allow_cache",
        "expires",
        "net_obj",
        "token_file",
        "gl",
        "hl"
    )

    def __init__(
        self,
        net_obj: net.SessionRequest,
        client: str = "WEB",
        use_oauth: bool = False,
        allow_cache: bool = True,
        token_file: str = None,
        gl: str = None,
        hl: str = None,
    ):
        self.gl = gl
        self.hl = hl
        self.token_timeout = 1800
        self.token_file = "tokens.json"
        self.innertube_context = _default_clients[client]["innertube_context"]
        if gl:
            self.innertube_context["context"]["client"]["gl"] = gl
        if hl:
            self.innertube_context["context"]["client"]["hl"] = hl
        self.header = _default_clients[client]["header"]
        self.api_key = _default_clients[client]["api_key"]
        self.require_js_player = _default_clients[client]["require_js_player"]
        self.access_token = None
        self.refresh_token = None
        self.use_oauth = use_oauth
        self.allow_cache = allow_cache
        self.expires = None
        self.net_obj: net.SessionRequest = net_obj
        self.token_file = token_file or _token_file
        if self.use_oauth and self.allow_cache and os.path.exists(self.token_file):
            with open(self.token_file) as f:
                data = json.load(f)
                self.access_token = data["access_token"]
                self.refresh_token = data["refresh_token"]
                self.expires = data["expires"]
                self.refresh_bearer_token()

    def cache_tokens(self):
        """Cache tokens to file if allowed."""
        if not self.allow_cache:
            return

        data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires": self.expires,
        }
        with open(self.token_file, "w") as f:
            json.dump(data, f)

    async def refresh_bearer_token(self, force=False):
        """Refreshes the OAuth token if necessary.

        :param bool force:
            Force-refresh the bearer token.
        """
        if not self.use_oauth:
            return
        # Skip refresh if it's not necessary and not forced
        if self.expires > time.time() and not force:
            return

        # Subtracting 30 seconds is arbitrary to avoid potential time discrepencies
        start_time = int(time.time() - 30)
        data = {
            "client_id": _client_id,
            "client_secret": _client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }
        response_data = await self.net_obj.post_json(
            "https://oauth2.googleapis.com/token",
            headers={"Content-Type": "application/json"},
            data=data,
        )
        self.access_token = response_data["access_token"]
        self.expires = start_time + response_data["expires_in"]
        self.cache_tokens()

    async def fetch_bearer_token(self):
        """Fetch an OAuth token."""
        # Subtracting 30 seconds is arbitrary to avoid potential time discrepencies
        start_time = int(time.time() - 30)
        data = {
            "client_id": _client_id,
            "scope": "https://www.googleapis.com/auth/youtube",
        }
        response_data = await self.net_obj.post_json(
            "https://oauth2.googleapis.com/device/code",
            headers={"Content-Type": "application/json"},
            data=data,
        )
        verification_url = response_data["verification_url"]
        user_code = response_data["user_code"]
        print(f"Please open {verification_url} and input code {user_code}")
        input("Press enter when you have completed this step.")

        data = {
            "client_id": _client_id,
            "client_secret": _client_secret,
            "device_code": response_data["device_code"],
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }
        response_data = await self.net_obj.post_json(
            "https://oauth2.googleapis.com/token",
            headers={"Content-Type": "application/json"},
            data=data,
        )

        self.access_token = response_data["access_token"]
        self.refresh_token = response_data["refresh_token"]
        self.expires = start_time + response_data["expires_in"]
        self.cache_tokens()

    @property
    def base_url(self) -> str:
        """Return the base url endpoint for the innertube API."""
        return "https://www.youtube.com/youtubei/v1"

    @property
    def base_data(self) -> dict:
        """Return the base json data to transmit to the innertube API."""
        return self.innertube_context

    @property
    def base_params(self):
        """Return the base query parameters to transmit to the innertube API."""
        return {"key": self.api_key, "prettyPrint": "false"}

    async def _call_api(self, endpoint, query, data):
        headers = {
            "Content-Type": "application/json",
        }
        # Add the bearer token if applicable
        if self.use_oauth:
            if self.access_token:
                await self.refresh_bearer_token()
            else:
                await self.fetch_bearer_token()

            headers["Authorization"] = f"Bearer {self.access_token}"
        headers.update(self.header)
        res = await self.net_obj.post_json(endpoint, query, data, headers)
        return res

    async def browse(self, browse_id=None, continuation=None) -> dict:
        endpoint = f"{self.base_url}/browse"
        query = dict()
        if browse_id:
            query["browseId"] = (browse_id,)

        if continuation:
            query["continuation"] = continuation
        query.update(self.base_params)
        if self.use_oauth:
            del query["key"]
        data = self.base_data
        data.update({"engagementType": "ENGAGEMENT_TYPE_UNBOUND"})
        return await self._call_api(endpoint, query, self.base_data)

    async def next(
        self,
        video_id: Optional[str] = None,
        playlist_id: Optional[str] = None,
        index: Optional[int] = None,
        continuation: Optional[str] = None,
    ) -> dict:
        endpoint = f"{self.base_url}/next"
        query = dict()
        if continuation:
            query["continuation"] = continuation
        if index:
            query["playlistIndex"] = index
        if playlist_id:
            query["playlistId"] = playlist_id
        if video_id:
            query["videoId"] = video_id
        query.update(self.base_params)
        if self.use_oauth:
            del query["key"]
        return await self._call_api(endpoint, query, self.base_data)

    async def player(self, video_id) -> dict:
        endpoint = f"{self.base_url}/player"
        query = {"videoId": video_id, "contentCheckOk": "true"}
        query.update(self.base_params)

        if self.use_oauth:
            del query["key"]
        return await self._call_api(endpoint, query, self.base_data)

    async def search(self, search_query=None, continuation=None) -> dict:
        endpoint = f"{self.base_url}/search"
        query = dict()
        if search_query:
            query["query"] = search_query
        query.update(self.base_params)
        if self.use_oauth:
            del query["key"]
        data = {}
        if continuation:
            data["continuation"] = continuation
        data.update(self.base_data)
        return await self._call_api(endpoint, query, data)

    async def live_chat(self, continuation: str) -> dict:
        endpoint = f"{self.base_url}/live_chat/get_live_chat"
        data = {"continuation": continuation}
        data.update(self.base_data)
        query = self.base_params.copy()
        if self.use_oauth:
            del query["key"]
        return await self._call_api(endpoint, query, data)

    async def update_metadata(self, video_id: str = None, continuation: str = None) -> dict:
        if video_id is None and continuation is None:
            raise Exception(
                "requere video id or continuation token. all of this is None"
            )
        endpoint = f"{self.base_url}/updated_metadata"
        data = {}
        if video_id:
            data["videoId"] = video_id
        if continuation:
            data["continuation"] = continuation
        data.update(self.base_data)
        query = self.base_params.copy()
        if self.use_oauth:
            del query["key"]
        return await self._call_api(endpoint, query, data)

    async def verify_age(self, video_id) -> dict:
        endpoint = f"{self.base_url}/verify_age"
        data = {
            "nextEndpoint": {"urlEndpoint": {"url": f"/watch?v={video_id}"}},
            "setControvercy": True,
        }
        data.update(self.base_data)
        query = self.base_params.copy()
        if self.use_oauth:
            del query["key"]
        result = await self._call_api(endpoint, query, data)
        return result

    async def get_transcript(self, video_id) -> dict:
        """Make a request to the get_transcript endpoint.

        This is likely related to captioning for videos, but is currently untested.
        """
        endpoint = f"{self.base_url}/get_transcript"
        query = {
            "videoId": video_id,
        }
        query.update(self.base_params)
        if self.use_oauth:
            del query["key"]
        result = await self._call_api(endpoint, query, self.base_data)
        return result
