"""List PreTeXt catalog books and download their directly linked files."""

import argparse
import re
import sys
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, Field, HttpUrl, TypeAdapter

CATALOG_URL = "https://pretextbook.org/catalog.html"
DEFAULT_OUTPUT = Path(__file__).parent / "books"
USER_AGENT = "Logos/0.1 (mathematical textbook research)"
HTTP_URL = TypeAdapter(HttpUrl)


class BookFile(BaseModel):
    """A downloadable file linked from a book's public page."""

    kind: Literal["pdf", "source"]
    url: HttpUrl


class Book(BaseModel):
    """A book entry collected from the PreTeXt catalog."""

    id: str
    title: str
    authors: str
    url: HttpUrl
    files: list[BookFile] = Field(default_factory=list)


class DownloadedFile(BookFile):
    """A downloaded file and its path relative to the book directory."""

    path: str


class BookMetadata(BaseModel):
    """Book provenance and local files saved by this collector."""

    id: str
    title: str
    authors: str
    url: HttpUrl
    files: list[DownloadedFile]


def _is_web_url(url: str) -> bool:
    return urlsplit(url).scheme in {"http", "https"}


def _attribute_text(tag: Tag, name: str) -> str:
    value = tag.get(name)
    return value if isinstance(value, str) else ""


def _book_from_card(card: Tag, catalog_url: str) -> Book | None:
    title_link = card.select_one(".biblio a.title[href]")
    if title_link is None:
        return None

    book_url = urljoin(catalog_url, _attribute_text(title_link, "href"))
    if not _is_web_url(book_url):
        return None

    authors = card.select_one(".biblio .authors")
    return Book(
        id=_attribute_text(card, "id"),
        title=title_link.get_text(" ", strip=True),
        authors=authors.get_text(" ", strip=True) if authors else "",
        url=HTTP_URL.validate_python(book_url),
    )


def list_books(client: httpx.Client) -> list[Book]:
    """Read book entries from the PreTeXt catalog."""
    response = client.get(CATALOG_URL)
    _ = response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    books: list[Book] = []
    for card in soup.select(".book-summary[id]"):
        book = _book_from_card(card, str(response.url))
        if book is not None:
            books.append(book)
    return books


def _file_kind(url: str) -> Literal["pdf", "source"] | None:
    path = urlsplit(url).path.lower()
    if path.endswith(".pdf"):
        return "pdf"
    if path.endswith((".zip", ".tar.gz", ".tgz")) and re.search(
        r"source|pretext|latex", url, re.IGNORECASE
    ):
        return "source"
    return None


def discover_files(client: httpx.Client, book: Book) -> Book:
    """Find direct PDF and likely source archive links on a book page."""
    response = client.get(str(book.url))
    _ = response.raise_for_status()

    urls = [str(response.url)]
    content_type = response.headers.get("content-type", "")
    if "html" in content_type:
        soup = BeautifulSoup(response.text, "html.parser")
        for link in soup.select("a[href]"):
            href = _attribute_text(link, "href")
            if href:
                urls.append(urljoin(str(response.url), href))

    files: list[BookFile] = []
    seen_urls: set[str] = set()
    for url in urls:
        if not _is_web_url(url) or url in seen_urls:
            continue
        kind = _file_kind(url)
        if kind is not None:
            files.append(BookFile(kind=kind, url=HTTP_URL.validate_python(url)))
            seen_urls.add(url)

    return book.model_copy(update={"files": files})


def _safe_filename(url: str, fallback: str) -> str:
    name = Path(unquote(urlsplit(url).path)).name
    name = re.sub(r"[^a-zA-Z0-9._-]", "_", name).strip(".")
    return name or fallback


def download_book(client: httpx.Client, book: Book, output: Path) -> Path:
    """Download book files and a JSON record with their original URLs."""
    safe_id = re.sub(r"[^a-zA-Z0-9._-]", "-", book.id).strip(".-")
    if not safe_id:
        raise ValueError(f"Unsafe book ID: {book.id!r}")

    directory = output / safe_id
    directory.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()
    downloaded_files: list[DownloadedFile] = []

    for index, book_file in enumerate(book.files, start=1):
        filename = _safe_filename(str(book_file.url), f"file-{index}")
        if filename in used_names:
            filename = f"{index}-{filename}"
        used_names.add(filename)

        destination = directory / filename
        with client.stream("GET", str(book_file.url)) as response:
            _ = response.raise_for_status()
            with destination.open("wb") as file:
                for chunk in response.iter_bytes():
                    _ = file.write(chunk)

        downloaded_files.append(
            DownloadedFile(kind=book_file.kind, url=book_file.url, path=filename)
        )

    metadata = BookMetadata(
        id=book.id,
        title=book.title,
        authors=book.authors,
        url=book.url,
        files=downloaded_files,
    )
    _ = (directory / "metadata.json").write_text(
        metadata.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return directory


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect books and direct download links from the PreTeXt catalog"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    _ = commands.add_parser("list", help="List books in the catalog")

    download_parser = commands.add_parser("download", help="Download a book's files")
    _ = download_parser.add_argument("book_id", help="ID shown by the list command")
    _ = download_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    command = args.command
    book_id = args.book_id if hasattr(args, "book_id") else ""
    output = args.output if hasattr(args, "output") else DEFAULT_OUTPUT

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=30,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            books = list_books(client)
            if command == "list":
                for book in books:
                    print(f"{book.id}\t{book.title} — {book.authors}")
                return 0

            book = next((entry for entry in books if entry.id == book_id), None)
            if book is None:
                print(f"Book not found: {book_id}", file=sys.stderr)
                return 1

            book = discover_files(client, book)
            if not book.files:
                print(
                    f"No direct PDF or source archive links found at {book.url}",
                    file=sys.stderr,
                )
                return 1

            directory = download_book(client, book, output)
            print(f"Downloaded {len(book.files)} file(s) to {directory}")
    except (httpx.HTTPError, OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
