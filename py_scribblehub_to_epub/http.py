from appdirs import AppDirs
from pyrate_limiter import SQLiteBucket
from requests import Session
from requests_cache import CacheMixin
from requests_ratelimiter import LimiterMixin

cache_dir = AppDirs("py_scribblehub_to_epub", "agmlego").user_cache_dir


class CachedLimiterSession(CacheMixin, LimiterMixin, Session):
    """Session class with caching and rate-limiting behavior.
    Accepts keyword arguments for both LimiterSession and CachedSession.
    """


# Limit non-cached requests to 5 requests per second, with unlimited cached requests
session = CachedLimiterSession(
    cache_name=cache_dir,
    backend="sqlite",
    cache_control=True,
    per_minute=100,
    bucket_class=SQLiteBucket,
)
