"""
Base classes for book model
"""

# pylint: disable=unused-argument
# pylint: disable=too-few-public-methods

import abc
from typing import Iterable, Self, Union

import arrow


class BookMetadata(abc.ABC):
    """
    Represents the metadata for the book
    """

    source_url: str = None
    """URL from which this metadata was fetched"""

    slug: str = None
    """Short text part of the URL for this book"""

    title: str = None
    """Book title"""

    languages: Iterable[str] = None
    """Book language(s) as Dublin-core language codes"""

    cover_url: str = None
    """URL for the cover image"""

    date: arrow.Arrow = None
    """Publication date for the book"""

    description: str = None
    """Description or synopsis of the book"""

    author: str = None
    """Book author(s)"""

    publisher: str = None
    """Book publisher"""

    identifier: str = None
    """Unique identifier for this book (e.g. UUID, hosting site book ID, ISBN, etc.)"""

    genres: Iterable[str] = None
    """Series of tags relating to the book genre"""

    tags: Iterable[str] = None
    """Series of tags describing the book content"""

    rights: str = None
    """Rights reservation for copyright purpose"""

    is_loaded: bool = False
    """Whether the metadata for this object has been loaded"""

    def load(self) -> None:
        """
        Load the metadata for this object
        """


class Chapter(abc.ABC):
    """
    Representation of a book chapter
    """

    source_url: str = None
    """URL for this chapter"""

    index: int = None
    """Unique identifier for this chapter (e.g. chapter number, hosting site chapter ID, etc.)"""

    title: str = None
    """Chapter title without number"""

    languages: Iterable[str] = None
    """Any language(s) in the chapter as Dublin-core language codes"""

    text: str = None
    """HTML content of chapter"""

    date: arrow.Arrow = None
    """Publication date for the chapter"""

    assets: dict[str, bytes] = None
    """Any image assets to embed into the chapter"""

    is_loaded: bool = False
    """Whether the metadata for this object has been loaded"""

    def load(self) -> Self:
        """
        Load the metadata for this object

        Returns:
            Self: This object containing all loaded data
        """


class Book(abc.ABC):
    """
    Representation of a book
    """

    source_url: str = None
    """URL from which this book was fetched"""

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

    is_loaded: bool = False
    """Whether the metadata for this object has been loaded"""

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

    def load(self) -> None:
        """
        Load the metadata for this object
        """

    def save(self, out_path: str) -> None:
        """
        Save this book as an ePub to disk

        Args:
            out_path (str): Directory to save the book
        """
