# pylint: disable=logging-fstring-interpolation
import logging
from os.path import join

from appdirs import AppDirs
from pyrate_limiter import SQLiteBucket
from requests import HTTPError, Session
from requests_cache import CacheMixin
from requests_ratelimiter import LimiterMixin

log = logging.getLogger(__name__)

RETRY_COUNT = 42
cache_dir = AppDirs("py_scribblehub_to_epub", "agmlego").user_cache_dir
limit_statuses = [
    429,
]


class CachedLimiterSession(CacheMixin, LimiterMixin, Session):
    """Session class with caching and rate-limiting behavior.
    Accepts keyword arguments for both LimiterSession and CachedSession.
    """

    def request(self, *args, **kwargs):
        for _ in range(RETRY_COUNT):
            response = super().request(*args, **kwargs)
            if response.ok or response.status_code not in limit_statuses:
                break
        if response.status_code in limit_statuses:
            log.warning(f"So many retries! ({RETRY_COUNT})")
        response.raise_for_status()
        return response


# Limit non-cached requests, with unlimited cached requests
session = CachedLimiterSession(
    cache_name=join(cache_dir, "http.sqlite"),
    backend="sqlite",
    cache_control=True,
    per_minute=60,
    bucket_class=SQLiteBucket,
    bucket_kwargs={
        "path": join(cache_dir, "rate_limit.sqlite"),
        "isolation_level": "EXCLUSIVE",
        "check_same_thread": False,
    },
    limit_statuses=[(code,) for code in limit_statuses],
)
