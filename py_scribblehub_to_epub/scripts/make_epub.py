import click

from ..scribblehub import ScribbleHubBook

providers = [
    ScribbleHubBook,
]


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
    tasks = []
    for u in url:
        for provider in providers:
            if provider.can_handle_url(u):
                tasks.append(provider(u))

    for task in tasks:
        task.load()
        task.save(out_path)
