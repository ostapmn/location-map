"""Versioned cache for the locations list.

Every cached page is stored under a key containing the current version.
Bumping the version makes all old pages unreachable at once (they expire via TTL),
so invalidation is O(1) and needs no key scanning.
"""
import hashlib
import time

from django.core.cache import cache

VERSION_KEY = "locations:version"
LIST_TTL = 60 * 5


def _version():
    version = cache.get(VERSION_KEY)
    if version is None:
        cache.add(VERSION_KEY, 1, None)
        version = cache.get(VERSION_KEY)
    return version


def list_cache_key(full_path):
    return f"locations:list:v{_version()}:{hashlib.md5(full_path.encode()).hexdigest()}"


def invalidate_list_cache():
    cache.set(VERSION_KEY, time.time_ns(), None)
