import abc
from typing import Iterable, Self, Union
import arrow
import click


class BookMetadata(abc.ABC):
    sourceUrl: str = None
    slug: str = None
    title: str = None
    coverUrl: str = None
    date: arrow.Arrow = None
    description: str = None
    author: str = None
    publisher: str = None
    identifier: str = None
    genres: Iterable[str] = None
    tags: Iterable[str] = None
    rights: str = None
    isLoaded: bool = False

    @classmethod
    def load(cls) -> Self:
        ...


class Chapter(abc.ABC):
    sourceUrl: str = None
    index: int = None
    title: str = None
    text: str = None
    date: arrow.Arrow = None
    assets: dict[str, bytes] = None
    isLoaded: bool = False

    def load(self) -> Self:
        ...


class Book(abc.ABC):
    sourceUrl: str = None
    metadata: BookMetadata = None
    coverImage: bytes = None
    chapters: Iterable[Chapter] = None
    styles: str = None
    filename: str = None
    assets: dict[str, dict[str, Union[str, bytes]]] = None
    isLoaded: bool = False

    @classmethod
    def canHandleUrl(cls, url: str) -> bool:
        ...

    def load(self) -> None:
        ...

    def save(self, out_path: click.Path) -> None:
        ...
