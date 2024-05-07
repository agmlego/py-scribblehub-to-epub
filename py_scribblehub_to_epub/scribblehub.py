"""
Scribble Hub provider to generate ePubs
"""

# pylint: disable=too-few-public-methods
# pylint: disable=too-many-instance-attributes
# pylint: disable=logging-fstring-interpolation

import logging
import math
import mimetypes
import os.path
import re
import uuid
from codecs import encode
from hashlib import sha1
from importlib.resources import files
from typing import Self, Union

import arrow
import ftfy
from appdirs import AppDirs
from bs4 import BeautifulSoup
from ebooklib import epub
from requests_cache import CachedSession
from rich.logging import RichHandler

from . import models

FORMAT = "%(message)s"
logging.basicConfig(
    level="DEBUG",
    format=FORMAT,
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)
logging.getLogger("requests_cache").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

dirs = AppDirs("py_scribblehub_to_epub", "agmlego")

headers = {"User-Agent": "node"}
session = CachedSession(dirs.user_cache_dir, backend="sqlite", cache_control=True)

CHAPTER_MATCH = re.compile(
    r"(?P<url_root>.*)/read/(?P<story_id>\d*)-(?P<slug>.*?)/chapter/(?P<chapter_id>\d*)"
)
STORY_MATCH = re.compile(r"(?P<url_root>.*)/series/(?P<story_id>\d*)/(?P<slug>[a-z-]*)")
DATE_MATCH = re.compile("Last updated: .*")


class ScribbleHubBookMetadata(models.BookMetadata):
    """
    Implementation of book metadata for Scribble Hub works
    """

    source_url: str = None
    """
    Canonical series URL for the work,
        `https://www.scribblehub.com/series/{{story_id}}/{{slug}}/`
    """

    slug: str = None
    """Short text part of the URL for this book, broken out of the series URL `story_id`"""

    title: str = None
    """Book title, loaded from `og:title`"""

    languages: list[str] = []
    """Book language(s) as Dublin-core language codes, loaded from `lang="*"`"""

    cover_url: str = None
    """URL for the cover image, loaded from `og:image`"""

    date: arrow.Arrow = None
    """Last updated date from series page, parsed from `<span title="Last updated: .*">`"""

    intro: str = None
    """Description of the book with HTML markup, loaded from `wi_fic_desc`"""

    description: str = None
    """Plaintext description of the book, loaded from `wi_fic_desc`"""

    author: str = None
    """Book author(s), loaded from `twitter:creator`"""

    publisher: str = "Scribble Hub"
    """Scribble Hub by default, loaded from `og:site_name`"""

    identifier: str = None
    """Unique identifier for this book, broken out of the series URL `slug`"""

    genres: list[str] = None
    """Series of tags relating to the book genre, loaded from `fic_genre`"""

    tags: list[str] = None
    """Series of tags describing the book content, loaded from `stag`"""

    rights: str = None
    """
    Rights reservation for copyright purpose,
        parsed out of `<div class="sb_content copyright">...<img class="copy*">`
    """

    chapters: int = 0
    """Number of chapters, loaded from `cnt_toc`"""

    def __init__(self, url: str) -> None:
        """
        Create an initial metadata object *without* loading the data

        Args:
            url (str): Either a chapter or series URL
        """
        super().__init__()
        self.source_url = url
        if not STORY_MATCH.search(self.source_url):
            url_parts = CHAPTER_MATCH.search(self.source_url)
            self.source_url = "/".join(
                (
                    url_parts["url_root"],
                    "series",
                    url_parts["story_id"],
                    url_parts["slug"],
                    "",
                )
            )
            log.debug(
                f"Fixing chapter URL to be series URL: {url} -> {self.source_url}"
            )
        url_parts = STORY_MATCH.search(self.source_url)
        self.slug = url_parts["slug"]
        self.identifier = url_parts["story_id"]
        log.debug(f"Metadata ready for {self.slug} ({self.identifier})")

    def load(self) -> None:
        """
        Load the metadata for this object
        """
        html = session.get(self.source_url, headers=headers)
        if not html.ok:
            html.raise_for_status()
        soup = BeautifulSoup(html.text, "lxml")
        for tag in soup.find_all(lambda x: x.has_attr("lang")):
            log.debug(f'Found language {tag["lang"]}')
            self.languages.append(tag["lang"])
        url = soup.find(property="og:url")["content"]
        if self.source_url != url:
            log.warning(f"Metadata URL mismatch!\n\t{self.source_url}\n\t{url}")
        self.title = soup.find(property="og:title")["content"]
        log.info(f"Book Title: {self.title}")
        self.cover_url = soup.find(property="og:image")["content"] or ""
        self.date = arrow.get(
            soup.find("span", title=DATE_MATCH)["title"][14:], "MMM D, YYYY hh:mm A"
        )
        description = soup.find(class_="wi_fic_desc")
        self.intro = ftfy.fix_text(description.prettify())
        self.description = ftfy.fix_text(description.text)
        self.author = soup.find(attrs={"name": "twitter:creator"})["content"]
        self.publisher = soup.find(property="og:site_name")["content"]
        self.genres = [a.string for a in soup.find_all(class_="fic_genre")]
        self.tags = [a.string for a in soup.find_all(class_="stag")]
        self.chapters = int(soup.find(class_="cnt_toc").text)

        imgs = soup.find(class_="sb_content copyright").find_all("img")
        self.rights = ""
        for img in imgs:
            if "copy" not in img["class"]:
                continue
            self.rights = ftfy.fix_text(img.next.string)
        self.is_loaded = True


class ScribbleHubChapter(models.Chapter):
    """
    Implementation of a book chapter for Scribble Hub works
    """

    parent: "ScribbleHubBook" = None
    """Book owning this chapter"""

    source_url: str = None
    """
    URL for this chapter,
        `https://www.scribblehub.com/read/{{story_id}}-{{slug}}/chapter/{{chapter_id}}/`
    """

    index: int = None
    """
    Unique identifier for this chapter,
        loaded in parent from series TOC `<li class="toc_w" order="{{index}}">`
    """

    title: str = None
    """Chapter title, loaded from `chapter-title`"""

    languages: list[str] = []
    """Any language(s) in the chapter  as Dublin-core language codes, loaded from `lang="*"`"""

    text: str = None
    """HTML content of chapter, loaded from `chp_raw`"""

    date: arrow.Arrow = None
    """
    Publication date for the chapter,
        loaded in parent from series TOC `<li class="toc_w" title="{{date}}">`
    """

    assets: dict[str, bytes] = None
    """
    Any image assets to embed into the chapter, loaded from `#chp_contents img[src]`

    Each asset is a dict keyed to the asset URL with keys:
    - `content`: the `bytes` content of the image
    - `relpath`: "static/{fname}{ext}"
        - `fname`: a SHA-1 hash of the URL
        - `ext`: a mimetypes guessed extension
    - `mimetype`: mimetype of the asset
    - `uid`: `fname`
    """

    def __init__(self, parent: "ScribbleHubBook", url: str):
        """
        Create an initial chapter object *without* loading the data

        Args:
            parent (ScribbleHubBook): Book owning this chapter
            url (str): A chapter URL
        """
        super().__init__()
        self.parent = parent
        self.source_url = url
        self.assets = {}

    def load(self) -> Self:
        """
        Load the metadata for this object

        Returns:
            Self: This object containing all loaded data
        """
        # ditch out if parent did not load index and date,
        # since those come from the series TOC not the chapter page metadata
        assert self.date is not None
        assert self.index is not None
        resp = session.get(self.source_url, headers=headers)
        if not resp.ok:
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup.find_all(lambda x: x.has_attr("lang")):
            log.debug(f'Found language {tag["lang"]}')
            self.languages.append(tag["lang"])
        self.title = soup.find(class_="chapter-title").text
        log.info(f"{self.parent.metadata.title} Chapter {self.index}: {self.title}")

        if not mimetypes.inited:
            mimetypes.init(None)

        for asset in soup.select("#chp_contents img[src]"):
            if asset["src"] not in self.assets:
                log.debug(f'Found asset at {asset["src"]}')
                asset_resp = session.get(asset["src"], headers=headers)
                if not asset_resp.ok:
                    asset_resp.raise_for_status()
                fname = sha1(encode(asset["src"], "utf-8")).hexdigest()
                mimetype, _ = mimetypes.guess_type(asset["src"])
                log.debug(f"Asset is {mimetype}")
                ext = mimetypes.guess_extension(mimetype)
                relpath = f"static/{fname}{ext}"
                log.debug(f"Asset destination {relpath}")
                self.assets[asset["src"]] = {
                    "content": asset_resp.content,
                    "relpath": relpath,
                    "mimetype": mimetype,
                    "uid": fname,
                }
                asset["src"] = relpath

        self.text = ftfy.fix_text(soup.find(class_="chp_raw").prettify())
        self.is_loaded = True
        self.fix_footnotes()

    def fix_footnotes(self):
        """
        Iterate through any footnotes and refactor them to ePub format
        """
        if not self.is_loaded:
            return
        soup = BeautifulSoup(self.text, "lxml")
        footnotes = []
        for tag in soup.select(".modern-footnotes-footnote"):
            mfn = tag["data-mfn"].text
            log.debug(f"Found footnote {mfn}")
            anchor = tag.find_all("a")[-1]
            content_tag_element = soup.select(
                f".modern-footnotes-footnote__note[data-mfn={mfn}]"
            )
            content_tag = content_tag_element[0]
            if not anchor or not content_tag:
                return
            anchor["id"] = f"noteanchor-{mfn}"
            anchor["href"] = f"#note-{mfn}"
            anchor["epub:type"] = "noteref"

            content_tag.name = "aside"
            content_tag["id"] = f"note-{mfn}"
            content_tag["epub:type"] = "footnote"
            footnote_anchor = soup.new_tag("a", href=f"#noteanchor-{mfn}")
            footnote_anchor.string = f"{mfn}."
            content_tag_element.insert(0, footnote_anchor)
            footnotes.append(content_tag_element)
        if footnotes:
            tag = soup.find_all("p")[-1]
            footnote_header = soup.new_tag("h2", id="footnotes")
            footnote_header.string = "Footnotes"
            tag.append(footnote_header)
            tag.extend(footnotes)

        soup.smooth()
        self.text = ftfy.fix_text(soup.prettify())


class ScribbleHubBook(models.Book):
    """
    Implementation of a book for Scribble Hub works
    """

    source_url: str = None
    """URL from which this book was fetched"""

    metadata: ScribbleHubBookMetadata = None
    """Metadata for the book"""

    cover_image: bytes = None
    """The image fetched from `self.metadata.cover_url`"""

    chapters: list[ScribbleHubChapter] = []
    """Series of chapters in the book"""

    styles = (
        files("py_scribblehub_to_epub.assets")
        .joinpath("scribblehub.css")
        .read_text(encoding="utf-8")
    )
    """Combined CSS stylesheet for the ePub"""

    filename: str = None
    """Filename to save the book, composed of `{{metadata.author}} - {{metadata.title}}.epub`"""

    assets: dict[str, dict[str, Union[str, bytes]]] = None
    """
    Combined set of image assets from all chapters to embed into the ePub
    
    Each asset is a dict keyed to the asset URL with keys:
    - `content`: the `bytes` content of the image
    - `relpath`: "static/{fname}{ext}"
        - `fname`: a SHA-1 hash of the URL
        - `ext`: a mimetypes guessed extension
    - `mimetype`: mimetype of the asset
    - `uid`: `fname`
    """

    @classmethod
    def can_handle_url(cls, url: str) -> bool:
        """
        Whether this class can handle the given URL. This class can handle the following:
        * Series: `https://www.scribblehub.com/series/{{story_id}}/{{slug}}/`
        * Chapter: `https://www.scribblehub.com/read/{{story_id}}-{{slug}}/chapter/{{chapter_id}}/`

        Args:
            url (str): URL to check

        Returns:
            bool: Whether this class can handle the URL
        """
        return (
            CHAPTER_MATCH.search(url) is not None or STORY_MATCH.search(url) is not None
        )

    def __init__(self, url: str) -> None:
        """
        Create an initial book object *without* loading the data

        Args:
            url (str): Either a chapter or series URL
        """
        super().__init__()
        self.metadata = ScribbleHubBookMetadata(url)
        self.source_url = url
        self.cover_image = None
        self.assets = {}
        self.chapters = []
        log.debug(f"Book ready for {self.source_url}")

    def load(self) -> None:
        """
        Load the metadata for this object
        """
        log.debug(f"Loading book for {self.source_url}")

        # fill out the metadata first from the series page
        self.metadata.load()
        self.filename = f"{self.metadata.author} - {self.metadata.title}.epub"

        # get the cover image downloaded
        img_resp = session.get(self.metadata.cover_url)
        if not img_resp.ok:
            img_resp.raise_for_status()
        self.cover_image = img_resp.content

        # fill out the chapters
        self.get_chapters()

    def save(self, out_path: str):
        """
        Save this book as an ePub to disk

        Args:
            out_path (str): Directory to save the book
        """

        log.debug(f"Saving book for {self.metadata.title}")

        book = epub.EpubBook()

        # set up metadata
        book.add_metadata("DC", "identifier", f"uuid:{uuid.uuid4()}", {"id": "BookId"})
        book.add_metadata(
            "DC", "identifier", f"url:{self.metadata.source_url}", {"id": "Source"}
        )
        book.add_metadata("DC", "subject", ",".join(self.metadata.tags), {"id": "tags"})
        book.add_metadata(
            "DC", "subject", ",".join(self.metadata.genres), {"id": "genre"}
        )
        book.set_title(self.metadata.title)

        book.add_metadata("DC", "date", self.metadata.date.isoformat())
        book.add_author(self.metadata.author)
        book.add_metadata("DC", "publisher", self.metadata.publisher)
        book.add_metadata(
            "DC",
            "rights",
            f"Copyright © {self.metadata.date.year} {self.metadata.author} {self.metadata.rights}",
        )
        book.add_metadata("DC", "description", self.metadata.description)

        # set languages; assume the first one is the "main" language
        main_lang = self.metadata.languages[0]
        book.set_language(main_lang)
        if len(self.metadata.languages) > 1:
            langs = set(self.metadata.languages[1:])
            langs.remove(main_lang)
            for lang in langs:
                book.add_metadata("DC", "language", lang)

        # add cover image
        if not mimetypes.inited:
            mimetypes.init(None)
        mimetype, _ = mimetypes.guess_type(self.metadata.cover_url)
        ext = mimetypes.guess_extension(mimetype)
        book.set_cover(f"cover{ext}", self.cover_image)

        # add other assets
        for _, asset in self.assets.items():
            book.add_item(
                epub.EpubImage(
                    uid=asset["uid"],
                    file_name=asset["relpath"],
                    media_type=asset["mimetype"],
                    content=asset["content"],
                )
            )

        # add chapters
        toc_chap_list = []
        intro = epub.EpubHtml(
            title="Introduction", file_name="intro.xhtml", content=self.metadata.intro
        )
        book.add_item(intro)
        for chapter in self.chapters:
            c = epub.EpubHtml(
                title=chapter.title,
                file_name=f"chapter{chapter.index}.xhtml",
                content=chapter.text,
            )
            book.add_item(c)
            toc_chap_list.append(c)

        # set up toc
        book.toc = (
            epub.Link("intro.xhtml", "Introduction", "intro"),
            (epub.Section("Languages"), toc_chap_list),
        )
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # create spine, add cover page as first page
        book.spine.extend(toc_chap_list)

        # create epub file
        epub.write_epub(os.path.join(out_path, self.filename), book, {})

    def get_chapters(self) -> None:
        """
        Fetch the chapters for the work, based on the TOC API
        """
        self.chapters = []
        page_count = math.ceil(self.metadata.chapters / 15)
        log.debug(
            f"Expecting {self.metadata.chapters} chapters, page_count={page_count}"
        )
        for page in range(1, page_count + 1):
            chapter_resp = session.post(
                "https://www.scribblehub.com/wp-admin/admin-ajax.php",
                {
                    "action": "wi_getreleases_pagination",
                    "pagenum": page,
                    "mypostid": self.metadata.identifier,
                },
                headers=headers,
            )
            if not chapter_resp.ok:
                chapter_resp.raise_for_status()
            chapter_soup = BeautifulSoup(chapter_resp.text, "lxml")
            for chapter_tag in chapter_soup.find_all(class_="toc_w"):
                chapter = ScribbleHubChapter(self, chapter_tag.a["href"])
                chapter.index = int(chapter_tag["order"])
                chapter.title = chapter_tag.a.text
                chapter.date = arrow.get(
                    chapter_tag.span["title"], "MMM D, YYYY hh:mm A"
                )
                self.chapters.append(chapter)
                self.metadata.languages.extend(chapter.languages)

        self.chapters.sort(key=lambda x: x.index)
        for chapter in self.chapters:
            chapter.load()
            self.assets.update(chapter.assets)
