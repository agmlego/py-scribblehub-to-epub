import abc
import arrow
from typing import Iterable, Self


class BookMetadata(abc.ABC):
    sourceUrl: str
    slug: str
    title: str
    coverUrl: str
    date: arrow.Arrow
    description: str
    author: str
    publisher: str
    description: str


class Chapter(abc.ABC):
    sourceUrl: str
    index: int
    title: str
    text: str

    @classmethod
    def load(cls) -> Self:
        ...


class Book(abc.ABC):
    sourceUrl: str
    metadata: BookMetadata
    coverImage: bytes
    chapters: Iterable[Chapter]
    styles: str
    isLoaded: bool = False

    @classmethod
    def canHandleUrl(cls, url: str) -> bool:
        ...

    def load(self) -> None:
        ...
