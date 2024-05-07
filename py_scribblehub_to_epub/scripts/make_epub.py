# pylint: disable=logging-fstring-interpolation

import logging
from typing import Iterable, Union

import click
from rich.logging import RichHandler

from ..scribblehub import ScribbleHubBook

providers = [
    ScribbleHubBook,
]

FORMAT = "%(message)s"
logging.basicConfig(
    level="DEBUG",
    format=FORMAT,
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)
logging.getLogger("requests_cache").setLevel(logging.WARNING)
log = logging.getLogger(__name__)


@click.command()
@click.version_option()
@click.argument("url", nargs=-1, type=str)
@click.argument(
    "out_path",
    nargs=1,
    type=click.Path(exists=True, writable=True, dir_okay=True, file_okay=False),
)
def cli(url: str, out_path: click.Path):
    """
    Make an epub book from URL(s), outputting them in a directory structure rooted at OUT_PATH
    """
    make_epub(url=url, out_path=out_path)


def make_epub(url: Union[str, Iterable[str]], out_path: str):
    """
    Make an epub book

    Args:
        url (str or iterable of str): Source URL(s) from which to fetch the work
        out_path (str): Destination directory to save the epub
    """
    tasks = []
    if isinstance(url, str):
        url = [url]
    for u in url:
        for provider in providers:
            if provider.can_handle_url(u):
                log.info(f"{provider} can handle {u}")
                tasks.append(provider(u))

    for task in tasks:
        task.load()
        task.save(out_path)
