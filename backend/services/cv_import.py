"""Read the text of a CV out of the file the candidate uploads."""

from __future__ import annotations

import logging
import re
import zipfile
from io import BytesIO
from typing import Optional

logger = logging.getLogger(__name__)

TEXT_SUFFIXES = (".txt", ".md", ".markdown", ".rst")
SUPPORTED_SUFFIXES = TEXT_SUFFIXES + (".pdf", ".docx")

_DOCX_PARAGRAPH_RE = re.compile(r"<w:p[ >].*?</w:p>", re.DOTALL)
_DOCX_TEXT_RE = re.compile(r"<w:t[^>]*>(.*?)</w:t>", re.DOTALL)
_XML_ENTITIES = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&apos;": "'"}
_BLANK_LINES_RE = re.compile(r"\n{3,}")


class CvReadError(Exception):
    """The file could not be turned into text."""


def suffix_of(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def tidy(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return _BLANK_LINES_RE.sub("\n\n", "\n".join(lines)).strip()


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise CvReadError("The file is not readable as text.")


def _unescape(value: str) -> str:
    for entity, char in _XML_ENTITIES.items():
        value = value.replace(entity, char)
    return value


def _read_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            document = archive.read("word/document.xml").decode("utf-8")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise CvReadError("This does not look like a Word document.") from exc
    paragraphs = [
        "".join(_unescape(piece) for piece in _DOCX_TEXT_RE.findall(block))
        for block in _DOCX_PARAGRAPH_RE.findall(document)
    ]
    return "\n".join(paragraphs)


def _read_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise CvReadError("Reading PDF files needs the pypdf package, which is not installed.") from exc
    try:
        reader = PdfReader(BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        logger.warning("CV PDF could not be read: %r", exc)
        raise CvReadError("This PDF could not be read. Save it as text and upload that instead.") from exc


def read_cv(filename: str, data: bytes, limit: Optional[int] = None) -> tuple[str, bool]:
    """
    The CV text and whether it was cut to *limit* characters.

    A PDF written as scanned images has no text layer, so it extracts to nothing; that is
    reported as an empty file rather than silently stored as a CV with no content.
    """
    suffix = suffix_of(filename)
    if suffix in TEXT_SUFFIXES:
        text = _decode_text(data)
    elif suffix == ".docx":
        text = _read_docx(data)
    elif suffix == ".pdf":
        text = _read_pdf(data)
    else:
        supported = ", ".join(SUPPORTED_SUFFIXES)
        raise CvReadError(f"{suffix or 'This file'} is not supported. Upload one of: {supported}.")

    text = tidy(text)
    if not text:
        raise CvReadError("No text was found in the file. A scanned or image-only CV has to be typed in by hand.")
    if limit is not None and len(text) > limit:
        return text[:limit], True
    return text, False


_NOT_A_NAME = {"cv", "resume", "curriculum vitae", "profile", "summary"}
# A CV that opens with its title instead of a name would otherwise read as one.
_ROLE_WORDS = {
    "engineer", "developer", "analyst", "scientist", "manager", "architect", "consultant",
    "intern", "lead", "designer", "administrator", "specialist", "programmer", "tester",
}
_NAME_MAX_WORDS = 5
_NAME_MAX_CHARS = 60
_HEADINGS_TO_SKIP = 2


def _looks_like_a_word_of_a_name(word: str) -> bool:
    return word[0].isalpha() and all(char.isalpha() or char in ".-'" for char in word)


def _name_or_empty(line: str) -> str:
    words = line.split()
    if not 2 <= len(words) <= _NAME_MAX_WORDS or len(line) > _NAME_MAX_CHARS:
        return ""
    if any(word.lower() in _ROLE_WORDS for word in words):
        return ""
    if not all(_looks_like_a_word_of_a_name(word) for word in words):
        return ""
    return line


def guess_name(text: str) -> str:
    """
    The candidate's name, from the line a CV opens with, as nearly every CV does.

    Up to two headings such as "Curriculum Vitae" are skipped first. Any other line is
    taken as the opening line: if it is not a short run of name-like words, with no job
    title, digit or email in it, the result is empty. Looking further down would accept
    a company or a project name as a person's.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    skipped = 0
    while lines and skipped < _HEADINGS_TO_SKIP and lines[0].lower() in _NOT_A_NAME:
        lines.pop(0)
        skipped += 1
    return _name_or_empty(lines[0]) if lines else ""
