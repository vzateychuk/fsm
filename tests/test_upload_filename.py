"""Tests for upload filename sanitization."""

from common.upload_filename import sanitize_upload_filename


def test_sanitize_basename_only() -> None:
    assert sanitize_upload_filename("/data/ingest/2024-10-13_report.md") == "2024-10-13_report.md"
    assert sanitize_upload_filename("dir\\report.md") == "report.md"


def test_sanitize_fallback() -> None:
    assert sanitize_upload_filename(None) == "upload.md"
    assert sanitize_upload_filename("") == "upload.md"
    assert sanitize_upload_filename("   ") == "upload.md"


def test_sanitize_strips_null_bytes() -> None:
    assert sanitize_upload_filename("rep\0ort.md") == "report.md"
