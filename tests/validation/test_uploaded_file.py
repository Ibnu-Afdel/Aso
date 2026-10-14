from __future__ import annotations

import pytest

from fastogram.validation.uploaded_file import UploadedFile


async def test_basic_attributes_and_read():
    f = UploadedFile("photo.jpg", "image/jpeg", b"hello")
    assert f.filename == "photo.jpg"
    assert f.content_type == "image/jpeg"
    assert f.size == 5
    assert f.extension() == "jpg"
    assert await f.read() == b"hello"


def test_content_type_is_guessed_when_omitted():
    f = UploadedFile("doc.pdf", None, b"x")
    assert f.content_type == "application/pdf"


def test_fake_image_and_create():
    image = UploadedFile.fake().image("avatar.png", width=32, height=32)
    assert image.filename == "avatar.png"
    assert image.content_type == "image/png"
    assert image.size > 0

    created = UploadedFile.fake().create("report.csv", size_kb=2, mime_type="text/csv")
    assert created.size == 2048
    assert created.content_type == "text/csv"


async def test_store_and_store_as_raise_not_implemented_until_t43():
    f = UploadedFile("a.txt", "text/plain", b"x")
    with pytest.raises(NotImplementedError, match="T-43"):
        await f.store("uploads")
    with pytest.raises(NotImplementedError, match="T-43"):
        await f.store_as("uploads", "b.txt")


def test_from_upload_file_reads_filename_and_content_type():
    class FakeStarletteUpload:
        filename = "x.png"
        content_type = "image/png"

    wrapped = UploadedFile.from_upload_file(FakeStarletteUpload(), b"data")
    assert wrapped.filename == "x.png"
    assert wrapped.content_type == "image/png"
    assert wrapped.size == 4
