"""Decode one authored ZIP package into the existing atomic artifact importer."""

from __future__ import annotations

import json
import struct
from base64 import b64decode
from binascii import Error as Base64Error
from datetime import date
from io import BytesIO
from pathlib import PurePosixPath, PureWindowsPath
from typing import Annotated, Any
from zipfile import ZIP_BZIP2, ZIP_DEFLATED, ZIP_LZMA, ZIP_STORED, BadZipFile, ZipFile

from pydantic import Field

from app.contracts.base import StrictDefaultsRequired
from app.domains.training.application.imports import (
    ImportFile,
    ImportRequest,
    ImportResult,
    import_artifacts,
)
from app.domains.training.dependencies import TrainingRepository

MAX_PACKAGE_BYTES = 5 * 1024 * 1024
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024
MAX_TOTAL_ARTIFACT_BYTES = 10 * 1024 * 1024
MAX_JSON_MEMBERS = 32
MAX_ARCHIVE_MEMBERS = 64
MAX_PACKAGE_BASE64_CHARS = 4 * ((MAX_PACKAGE_BYTES + 2) // 3)
MAX_WARNING_ACKS = 64
MAX_WARNING_ACK_CHARS = 4096

_SUPPORTED_COMPRESSION = {ZIP_STORED, ZIP_DEFLATED, ZIP_BZIP2, ZIP_LZMA}
_CENTRAL_DIRECTORY_SIGNATURE = b"PK\x01\x02"
_CENTRAL_DIRECTORY_HEADER_BYTES = 46
_EOCD_SIGNATURE = b"PK\x05\x06"
_EOCD_MIN_BYTES = 22
_MAX_ZIP_COMMENT_BYTES = 65_535


class ImportPackageRequest(StrictDefaultsRequired):
    """One authored ZIP package plus any lint warnings already acknowledged."""

    filename: Annotated[str, Field(min_length=1, max_length=255)]
    content_base64: Annotated[str, Field(max_length=MAX_PACKAGE_BASE64_CHARS)]
    start_date: date
    warning_acks: Annotated[
        list[Annotated[str, Field(max_length=MAX_WARNING_ACK_CHARS)]],
        Field(max_length=MAX_WARNING_ACKS),
    ] = []


def import_package(repo: TrainingRepository, request: ImportPackageRequest) -> ImportResult:
    """Read bounded JSON artifacts from one ZIP and delegate atomic activation."""
    if not request.filename.lower().endswith(".zip"):
        raise ValueError("Training package filename must end in .zip")

    try:
        package_bytes = b64decode(request.content_base64, validate=True)
    except (Base64Error, ValueError) as exc:
        raise ValueError("Training package content must be valid base64") from exc
    if len(package_bytes) > MAX_PACKAGE_BYTES:
        raise ValueError(
            f"Training package exceeds the {MAX_PACKAGE_BYTES}-byte compressed size limit"
        )

    try:
        files = _read_artifacts(package_bytes)
    except BadZipFile as exc:
        raise ValueError("Training package must be a valid ZIP archive") from exc
    except NotImplementedError as exc:
        raise ValueError("Training package uses unsupported compression") from exc

    return import_artifacts(
        repo,
        ImportRequest(
            files=files,
            schedule_start=request.start_date.isoformat(),
            warning_acks=request.warning_acks,
        ),
    )


def _read_artifacts(package_bytes: bytes) -> list[ImportFile]:
    files: list[ImportFile] = []
    seen_filenames: set[str] = set()
    total_artifact_bytes = 0
    json_member_count = 0

    _preflight_archive_members(package_bytes)

    with ZipFile(BytesIO(package_bytes)) as archive:
        members = archive.infolist()
        if len(members) > MAX_ARCHIVE_MEMBERS:
            raise ValueError(
                f"Training package exceeds the {MAX_ARCHIVE_MEMBERS}-file archive member limit"
            )
        for member in members:
            path = PurePosixPath(member.filename.replace("\\", "/"))
            filename = path.name
            windows_path = PureWindowsPath(member.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or windows_path.is_absolute()
                or bool(windows_path.drive)
            ):
                raise ValueError(f"Training package contains unsafe path '{member.filename}'")
            if member.is_dir() or "__MACOSX" in path.parts or filename.startswith("._"):
                continue
            if not filename.lower().endswith(".json"):
                continue
            if member.flag_bits & 1:
                raise ValueError(f"Training package artifact '{filename}' is encrypted")
            if member.compress_type not in _SUPPORTED_COMPRESSION:
                raise ValueError(
                    f"Training package artifact '{filename}' uses unsupported compression"
                )
            if filename in seen_filenames:
                raise ValueError(f"Training package contains duplicate JSON filename '{filename}'")

            json_member_count += 1
            if json_member_count > MAX_JSON_MEMBERS:
                raise ValueError(
                    f"Training package exceeds the {MAX_JSON_MEMBERS}-file JSON member limit"
                )
            if member.file_size > MAX_ARTIFACT_BYTES:
                raise ValueError(
                    f"Training package artifact '{filename}' exceeds the artifact size limit"
                )
            total_artifact_bytes += member.file_size
            if total_artifact_bytes > MAX_TOTAL_ARTIFACT_BYTES:
                raise ValueError("Training package exceeds the total artifact size limit")

            with archive.open(member) as source:
                raw_content = source.read(MAX_ARTIFACT_BYTES + 1)
            if len(raw_content) > MAX_ARTIFACT_BYTES:
                raise ValueError(
                    f"Training package artifact '{filename}' exceeds the artifact size limit"
                )

            content = _parse_json_object(filename, raw_content)
            files.append(ImportFile(filename=filename, content=content))
            seen_filenames.add(filename)

    return files


def _preflight_archive_members(package_bytes: bytes) -> None:
    """Count central-directory records before ZipFile materializes member objects."""
    eocd_offset = _find_eocd(package_bytes)
    if eocd_offset is None:
        return

    declared_count = struct.unpack_from("<H", package_bytes, eocd_offset + 10)[0]
    directory_size = struct.unpack_from("<I", package_bytes, eocd_offset + 12)[0]
    directory_offset = struct.unpack_from("<I", package_bytes, eocd_offset + 16)[0]
    if declared_count == 0xFFFF or directory_size == 0xFFFFFFFF or directory_offset == 0xFFFFFFFF:
        raise ValueError("Training package ZIP64 archives are not supported")

    directory_end = directory_offset + directory_size
    if directory_end != eocd_offset or directory_end > len(package_bytes):
        raise BadZipFile("Malformed ZIP central directory")

    cursor = directory_offset
    actual_count = 0
    while cursor < directory_end:
        if (
            cursor + _CENTRAL_DIRECTORY_HEADER_BYTES > directory_end
            or package_bytes[cursor : cursor + 4] != _CENTRAL_DIRECTORY_SIGNATURE
        ):
            raise BadZipFile("Malformed ZIP central directory")
        filename_length, extra_length, comment_length = struct.unpack_from(
            "<HHH",
            package_bytes,
            cursor + 28,
        )
        cursor += (
            _CENTRAL_DIRECTORY_HEADER_BYTES
            + filename_length
            + extra_length
            + comment_length
        )
        if cursor > directory_end:
            raise BadZipFile("Malformed ZIP central directory")
        actual_count += 1
        if actual_count > MAX_ARCHIVE_MEMBERS:
            raise ValueError(
                f"Training package exceeds the {MAX_ARCHIVE_MEMBERS}-file archive member limit"
            )

    if actual_count != declared_count:
        raise BadZipFile("ZIP member count does not match its central directory")


def _find_eocd(package_bytes: bytes) -> int | None:
    search_start = max(
        0,
        len(package_bytes) - (_EOCD_MIN_BYTES + _MAX_ZIP_COMMENT_BYTES),
    )
    search_end = len(package_bytes)
    while True:
        offset = package_bytes.rfind(_EOCD_SIGNATURE, search_start, search_end)
        if offset < 0:
            return None
        if offset + _EOCD_MIN_BYTES <= len(package_bytes):
            comment_length = struct.unpack_from("<H", package_bytes, offset + 20)[0]
            if offset + _EOCD_MIN_BYTES + comment_length == len(package_bytes):
                return offset
        search_end = offset


def _parse_json_object(filename: str, content: bytes) -> dict[str, Any]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Training package artifact '{filename}' must be UTF-8") from exc
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Training package artifact '{filename}' must contain valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"Training package artifact '{filename}' must contain a JSON object")
    return parsed
