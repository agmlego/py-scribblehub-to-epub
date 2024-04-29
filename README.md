# py-scribblehub-to-epub
Python project to make epub books from Scribblehub works, inspired by https://github.com/AnnaDamm/scribblehub-to-epub

## Goals
1. Create functional epubs no less complete than the above project
2. Add the URL for the work into the `dc:identifier` field as a URI so there is traceback to the work from the epub
3. Add the genre(s) and tags into appropriate epub fields
4. Add the ratings from the `ld+json` data into whatever field calibre uses for ratings
