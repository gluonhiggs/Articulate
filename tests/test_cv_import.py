"""A CV arrives as a file the candidate did not write for us, so every reader must fail loudly."""

from __future__ import annotations

import zipfile
from io import BytesIO

import pytest

from backend.services.cv_import import CvReadError, guess_name, read_cv, suffix_of, tidy

CV = "Nguyen Van A\n\nData engineer, 5 years.\n\nProjects\n- Spark pipeline for 2 TB a day."


def docx_bytes(paragraphs: list[str]) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    document = f'<?xml version="1.0"?><w:document xmlns:w="x"><w:body>{body}</w:body></w:document>'
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


class TestSuffix:
    @pytest.mark.parametrize(
        "filename,expected",
        [("cv.PDF", ".pdf"), ("my cv.docx", ".docx"), ("cv", ""), ("a.b.txt", ".txt")],
    )
    def test_reads_the_last_extension_in_lower_case(self, filename: str, expected: str) -> None:
        assert suffix_of(filename) == expected


class TestTidy:
    def test_collapses_the_blank_runs_a_pdf_leaves_behind(self) -> None:
        assert tidy("A\n\n\n\n\nB") == "A\n\nB"

    def test_normalises_windows_line_endings_and_trailing_space(self) -> None:
        assert tidy("A  \r\nB\r\n") == "A\nB"


class TestReadCv:
    def test_reads_a_text_file(self) -> None:
        text, truncated = read_cv("cv.txt", CV.encode("utf-8"))
        assert "Spark pipeline" in text
        assert truncated is False

    def test_reads_a_text_file_saved_by_windows(self) -> None:
        text, _ = read_cv("cv.txt", "Nguyen Van A - 5 years".encode("cp1252"))
        assert text == "Nguyen Van A - 5 years"

    def test_reads_a_word_document_as_one_line_per_paragraph(self) -> None:
        text, _ = read_cv("cv.docx", docx_bytes(["Nguyen Van A", "Data engineer", "Spark &amp; SQL"]))
        assert text == "Nguyen Van A\nData engineer\nSpark & SQL"

    def test_rejects_a_word_document_that_is_not_a_zip(self) -> None:
        with pytest.raises(CvReadError, match="Word document"):
            read_cv("cv.docx", b"not a zip")

    def test_rejects_a_file_type_it_cannot_read(self) -> None:
        with pytest.raises(CvReadError, match=".pages is not supported"):
            read_cv("cv.pages", b"anything")

    def test_rejects_an_empty_file_rather_than_saving_a_blank_cv(self) -> None:
        with pytest.raises(CvReadError, match="No text was found"):
            read_cv("cv.txt", b"   \n\n  ")

    def test_rejects_a_scanned_pdf_with_no_text_layer(self) -> None:
        # A PDF of page images extracts to nothing, which must not pass as a CV.
        with pytest.raises(CvReadError):
            read_cv("cv.pdf", b"%PDF-1.4\nnot really a pdf")

    def test_cuts_a_long_cv_to_the_limit_and_says_so(self) -> None:
        text, truncated = read_cv("cv.txt", ("word " * 500).encode("utf-8"), limit=100)
        assert len(text) == 100
        assert truncated is True


class TestGuessName:
    @pytest.mark.parametrize(
        "first_line",
        ["Duong H. D. Tran", "Tran Minh Quang", "Nguyen Van A", "Mary-Jane O'Neil", "Tran Thi Hoa"],
    )
    def test_reads_a_name_from_the_first_line(self, first_line: str) -> None:
        assert guess_name(f"{first_line}\nData Engineer\n") == first_line

    def test_skips_blank_lines_before_the_name(self) -> None:
        assert guess_name("\n\n  Tran Minh Quang  \nData Engineer") == "Tran Minh Quang"

    @pytest.mark.parametrize(
        "first_line",
        [
            "quang.tran@example.com",
            "Data Engineer - Ho Chi Minh City",
            "Phone: 0901 234 567",
            "Tran",
            "Data Engineer",
            "Senior Software Developer",
            "Senior Data Engineer with five years of experience in Spark",
        ],
    )
    def test_returns_nothing_for_a_first_line_that_is_not_a_name(self, first_line: str) -> None:
        assert guess_name(f"{first_line}\nmore text") == ""

    def test_returns_nothing_for_an_empty_cv(self) -> None:
        assert guess_name("") == ""

    def test_reads_the_name_after_a_heading(self) -> None:
        assert guess_name("CURRICULUM VITAE\nDuong H. D. Tran\nData Engineer") == "Duong H. D. Tran"

    def test_a_heading_followed_by_no_name_gives_nothing(self) -> None:
        assert guess_name("CURRICULUM VITAE\nquang.tran@example.com") == ""

    def test_reads_the_name_after_two_headings(self) -> None:
        assert guess_name("Resume\nCV\nTran Minh Quang") == "Tran Minh Quang"

    def test_does_not_look_past_a_line_that_is_not_a_heading(self) -> None:
        # The company on line two must not be taken for the person.
        assert guess_name("quang@example.com\nVela Outsourcing\nTran Minh Quang") == ""
