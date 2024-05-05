import abc
from typing import Iterable, Self, Union

import arrow
import click


class BookMetadata(abc.ABC):
    source_url: str = None
    slug: str = None
    title: str = None
    cover_url: str = None
    date: arrow.Arrow = None
    description: str = None
    author: str = None
    publisher: str = None
    identifier: str = None
    genres: Iterable[str] = None
    tags: Iterable[str] = None
    rights: str = None
    is_loaded: bool = False

    @classmethod
    def load(cls) -> Self: ...


class Chapter(abc.ABC):
    source_url: str = None
    index: int = None
    title: str = None
    text: str = None
    date: arrow.Arrow = None
    assets: dict[str, bytes] = None
    is_loaded: bool = False

    def load(self) -> Self: ...


class Book(abc.ABC):
    source_url: str = None
    metadata: BookMetadata = None
    cover_image: bytes = None
    chapters: Iterable[Chapter] = None
    styles: str = None
    filename: str = None
    assets: dict[str, dict[str, Union[str, bytes]]] = None
    is_loaded: bool = False

    @classmethod
    def can_handle_url(cls, url: str) -> bool: ...

    def load(self) -> None: ...

    def save(self, out_path: click.Path) -> None: ...
