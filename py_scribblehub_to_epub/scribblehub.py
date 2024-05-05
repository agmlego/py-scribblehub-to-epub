import mimetypes
import os.path
import re
import uuid
from codecs import encode
from hashlib import sha1
from importlib.resources import files
from typing import Self

import arrow
import click
import ftfy
from appdirs import AppDirs
from bs4 import BeautifulSoup
from ebooklib import epub
from requests_cache import CachedSession

from . import models

dirs = AppDirs("py_scribblehub_to_epub", "agmlego")

headers = {"User-Agent": "node"}
session = CachedSession(dirs.user_cache_dir, backend="sqlite", cache_control=True)

CHAPTER_MATCH = re.compile(
    r"(?P<url_root>.*)/read/(?P<story_id>\d*)-(?P<slug>.*?)/chapter/(?P<chapter_id>\d*)"
)
STORY_MATCH = re.compile(r"(?P<url_root>.*)/series/(?P<story_id>\d*)/(?P<slug>[a-z-]*)")
DATE_MATCH = re.compile("Last updated: .*")


class ScribbleHubBookMetadata(models.BookMetadata):
    def __init__(self, url: str) -> None:
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
        url_parts = STORY_MATCH.search(self.source_url)
        self.slug = url_parts["slug"]
        self.identifier = url_parts["story_id"]

    def load(self) -> None:
        html = session.get(self.source_url, headers=headers)
        if not html.ok:
            html.raise_for_status()
        soup = BeautifulSoup(html.text)
        url = soup.find(property="og:url")["content"]
        if self.source_url != url:
            print(f"Metadata URL mismatch!\n\t{self.source_url}\n\t{url}")
        self.title = soup.find(property="og:title")["content"]
        self.cover_url = soup.find(property="og:image")["content"] or ""
        self.date = arrow.get(
            soup.find("span", title=DATE_MATCH)["title"][14:], "MMM D, YYYY hh:mm A"
        )
        self.description = ftfy.fix_text(soup.find(class_="wi_fic_desc").text)
        self.author = soup.find(attrs={"name": "twitter:creator"})["content"]
        self.publisher = soup.find(property="og:site_name")["content"]
        self.genres = [a.string for a in soup.find_all(class_="fic_genre")]
        self.tags = [a.string for a in soup.find_all(class_="stag")]

        imgs = soup.find(class_="sb_content copyright").find_all("img")
        self.rights = ""
        for img in imgs:
            if "copy" not in img["class"]:
                continue
            self.rights = ftfy.fix_text(img.next.string)
        self.is_loaded = True


class ScribbleHubChapter(models.Chapter):
    def __init__(self, url: str):
        super().__init__()
        self.source_url = url
        self.assets = {}

    def load(self) -> Self:
        resp = session.get(self.source_url, headers=headers)
        if not resp.ok:
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text)
        self.title = soup.find(class_="chapter-title").text
        self.text = ftfy.fix_text(soup.find(class_="chp_raw").prettify())

        if not mimetypes.inited:
            mimetypes.init(None)

        for asset in soup.select("#chp_contents img[src]"):
            if asset["src"] not in self.assets:
                asset_resp = session.get(asset["src"], headers=headers)
                if not asset_resp.ok:
                    asset_resp.raise_for_status()
                fname = sha1(encode(asset["src"], "utf-8")).hexdigest()
                mimetype, _ = mimetypes.guess_type(asset["src"])
                ext = mimetypes.guess_extension(mimetype)
                relpath = f"static/{fname}{ext}"
                self.assets[asset["src"]] = {
                    "content": asset_resp.content,
                    "relpath": relpath,
                    "mimetype": mimetype,
                    "uid": fname,
                }
                asset["src"] = relpath
        self.fix_footnotes()

    def fix_footnotes(self):
        if not self.is_loaded:
            return
        soup = BeautifulSoup(self.text)
        footnotes = []
        for tag in soup.select(".modern-footnotes-footnote"):
            mfn = tag["data-mfn"].text
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
    metadata: ScribbleHubBookMetadata
    chapters: list[ScribbleHubChapter] = []
    styles = (
        files("py_scribblehub_to_epub.assets")
        .joinpath("scribblehub.css")
        .read_text(encoding="utf-8")
    )

    @classmethod
    def can_handle_url(cls, url: str) -> bool:
        return (
            CHAPTER_MATCH.search(url) is not None or STORY_MATCH.search(url) is not None
        )

    def __init__(self, url: str) -> None:
        super().__init__()
        self.metadata = ScribbleHubBookMetadata(url)
        self.source_url = url
        self.cover_image = None
        self.assets = {}

    def load(self) -> None:
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

    def save(self, out_path: click.Path):
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
        # book.set_language(self.metadata.language)

        book.add_metadata("DC", "date", self.metadata.date.isoformat())
        book.add_author(self.metadata.author)
        book.add_metadata("DC", "publisher", self.metadata.publisher)
        book.add_metadata(
            "DC",
            "rights",
            f"Copyright © {self.metadata.date.year} {self.metadata.author} {self.metadata.rights}",
        )
        book.add_metadata("DC", "description", self.metadata.description)

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
            title="Intro", file_name="intro.xhtml", content=self.metadata.description
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

        # set up styles
        nav_css = epub.EpubItem(
            uid="style_nav",
            file_name="style/nav.css",
            media_type="text/css",
            content=self.styles,
        )
        book.add_item(nav_css)

        # create spin, add cover page as first page
        book.spine = ["cover", "nav"]
        book.spine.extend(toc_chap_list)

        # create epub file
        epub.write_epub(os.path.join(out_path, self.filename), book, {})

    def get_chapters(self) -> None:
        chapter_resp = session.post(
            f"{self.metadata.source_url}/wp-admin/admin-ajax.php",
            {
                "action": "wi_getreleases_pagination",
                "pagenum": -1,
                "mypostid": self.metadata.identifier,
            },
            headers=headers,
        )
        if not chapter_resp.ok:
            chapter_resp.raise_for_status()
        chapter_soup = BeautifulSoup(chapter_resp.text)
        for chapter_tag in chapter_soup.find_all(class_="toc_w"):
            chapter = ScribbleHubChapter(chapter_tag.a["href"])
            chapter.index = int(chapter_tag["order"])
            chapter.title = chapter_tag.a.text
            chapter.date = arrow.get(chapter_tag.span["title"], "MMM D, YYYY hh:mm A")
            self.chapters.append(chapter)

        self.chapters.sort(key=lambda x: x.index)
        for chapter in self.chapters:
            chapter.load()
            self.assets.update(chapter.assets)
