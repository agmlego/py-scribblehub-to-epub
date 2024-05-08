"""
Base classes for book model
"""

# pylint: disable=unused-argument
# pylint: disable=too-few-public-methods

import abc
import enum
from typing import Iterable, Union

import arrow


class LoadStates(enum.IntEnum):
    EMPTY = enum.auto()
    LOADING = enum.auto()
    LOADED = enum.auto()


class BookModel(abc.ABC):
    """Represents the basic model for a book item"""

    source_url: str
    """URL from which this data was fetched"""

    load_state: LoadStates = LoadStates.EMPTY
    """Whether the data in this object has been loaded"""

    def load(self) -> None:
        """
        Load the metadata for this object
        """

    def __getattr__(self, name):
        if self.load_state == LoadStates.EMPTY:
            self.load()
        if self.load_state == LoadStates.LOADING:
            raise AttributeError(obj=self, name=name)
        return getattr(self, name)


class BookMetadata(BookModel):
    """
    Represents the metadata for the book
    """

    slug: str
    """Short text part of the URL for this book"""

    title: str
    """Book title"""

    languages: Iterable[str]
    """Book language(s) as Dublin-core language codes"""

    cover_url: str
    """URL for the cover image"""

    date: arrow.Arrow
    """Publication date for the book"""

    description: str
    """Description or synopsis of the book"""

    author: str
    """Book author(s)"""

    publisher: str
    """Book publisher"""

    identifier: str
    """Unique identifier for this book (e.g. UUID, hosting site book ID, ISBN, etc.)"""

    genres: Iterable[str]
    """Series of tags relating to the book genre"""

    tags: Iterable[str]
    """Series of tags describing the book content"""

    rights: str
    """Rights reservation for copyright purpose"""


class Chapter(BookModel):
    """
    Representation of a book chapter
    """

    parent: "Book"
    """Book owning this chapter"""

    index: int
    """Unique identifier for this chapter (e.g. chapter number, hosting site chapter ID, etc.)"""

    title: str
    """Chapter title without number"""

    text: str
    """HTML content of chapter"""

    date: arrow.Arrow
    """Publication date for the chapter"""

    assets: dict[str, bytes]
    """Any image assets to embed into the chapter"""


class Book(BookModel):
    """
    Representation of a book
    """

    metadata: BookMetadata = None
    """Metadata for the book"""

    cover_image: bytes = None
    """The image fetched from `self.metadata.cover_url`"""

    chapters: Iterable[Chapter] = None
    """Series of chapters in the book"""

    styles: str = None
    """Combined CSS stylesheet for the ePub"""

    filename: str = None
    """Filename to save the book"""

    assets: dict[str, dict[str, Union[str, bytes]]] = None
    """Combined set of image assets from all chapters to embed into the ePub"""

    @classmethod
    def can_handle_url(cls, url: str) -> bool:
        """
        Whether this class can handle the given URL,
            used to determine which provider can target a source URL

        Args:
            url (str): URL to check

        Returns:
            bool: Whether this class can handle the URL
        """

    def save(self, out_path: str) -> None:
        """
        Save this book as an ePub to disk

        Args:
            out_path (str): Directory to save the book
        """
