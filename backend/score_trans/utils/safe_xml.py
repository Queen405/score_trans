from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import BinaryIO
from zipfile import ZipFile


MAX_XML_BYTES = 64 * 1024 * 1024
_DOCTYPE_START = re.compile(r"<!\s*DOCTYPE\b", re.IGNORECASE)
_DOCTYPE_DECLARATION = re.compile(
    r"""<!\s*DOCTYPE\b(?:[^>"']|"[^"]*"|'[^']*')*>""",
    re.IGNORECASE | re.DOTALL,
)
_ENTITY_DECLARATION = re.compile(r"<!\s*ENTITY\b", re.IGNORECASE)
_MUSICXML_DOCTYPE = re.compile(
    r"""
    <!\s*DOCTYPE\s+
    (?P<root>score-(?:partwise|timewise))\s+
    PUBLIC\s+
    (?P<public_quote>["'])
    -//Recordare//DTD\s+MusicXML\s+
    \d+(?:\.\d+){1,2}\s+
    (?P<form>Partwise|Timewise)//EN
    (?P=public_quote)\s+
    (?P<system_quote>["'])
    https?://www\.musicxml\.org/dtds/(?P<file>partwise|timewise)\.dtd
    (?P=system_quote)\s*>
    """,
    re.IGNORECASE | re.VERBOSE,
)
_COMMENT_OR_CDATA = re.compile(
    r"<!--.*?-->|<!\[CDATA\[.*?\]\]>",
    re.DOTALL,
)


class UnsafeXmlError(ValueError):
    """Raised before XML parsing when a payload violates resource limits."""


def safe_xml_fromstring(
    data: str | bytes,
    *,
    source: str = "XML",
    max_bytes: int = MAX_XML_BYTES,
    allow_musicxml_doctype: bool = False,
) -> ET.Element:
    text = safe_xml_text(
        data,
        source=source,
        max_bytes=max_bytes,
        allow_musicxml_doctype=allow_musicxml_doctype,
    )
    return ET.fromstring(text)


def safe_xml_text(
    data: str | bytes,
    *,
    source: str = "XML",
    max_bytes: int = MAX_XML_BYTES,
    allow_musicxml_doctype: bool = False,
) -> str:
    if max_bytes <= 0:
        raise ValueError("max_bytes must be greater than zero")

    if isinstance(data, bytes):
        raw = data
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeError as exc:
            raise UnsafeXmlError(f"{source} 必须使用 UTF-8 编码") from exc
    else:
        text = data.lstrip("\ufeff")
        raw = text.encode("utf-8")

    if len(raw) > max_bytes:
        raise UnsafeXmlError(f"{source} 超过 XML 大小上限 {max_bytes} bytes")
    declaration_text = _COMMENT_OR_CDATA.sub(
        lambda match: _mask_markup(match.group(0)),
        text,
    )
    if _ENTITY_DECLARATION.search(declaration_text):
        raise UnsafeXmlError(f"{source} 不允许包含 DTD 或 ENTITY 声明")

    doctype_starts = list(_DOCTYPE_START.finditer(declaration_text))
    if not doctype_starts:
        return text
    if not allow_musicxml_doctype:
        raise UnsafeXmlError(f"{source} 不允许包含 DTD 或 ENTITY 声明")

    declarations = list(_DOCTYPE_DECLARATION.finditer(declaration_text))
    if (
        len(doctype_starts) != 1
        or len(declarations) != 1
        or doctype_starts[0].start() != declarations[0].start()
    ):
        raise UnsafeXmlError(f"{source} 不允许包含 DTD 或 ENTITY 声明")

    declaration = declarations[0]
    allowed = _MUSICXML_DOCTYPE.fullmatch(declaration.group(0))
    if allowed is None:
        raise UnsafeXmlError(f"{source} 不允许包含 DTD 或 ENTITY 声明")

    root_form = allowed.group("root").rsplit("-", 1)[-1].casefold()
    if (
        root_form != allowed.group("form").casefold()
        or root_form != allowed.group("file").casefold()
    ):
        raise UnsafeXmlError(f"{source} 不允许包含 DTD 或 ENTITY 声明")

    return (
        text[: declaration.start()]
        + _mask_markup(text[declaration.start() : declaration.end()])
        + text[declaration.end() :]
    )


def safe_xml_file_text(
    path: Path,
    *,
    source: str | None = None,
    max_bytes: int = MAX_XML_BYTES,
    allow_musicxml_doctype: bool = False,
) -> str:
    label = source or path.name
    with path.open("rb") as stream:
        data = _read_bounded(stream, source=label, max_bytes=max_bytes)
    return safe_xml_text(
        data,
        source=label,
        max_bytes=max_bytes,
        allow_musicxml_doctype=allow_musicxml_doctype,
    )


def safe_zip_member_bytes(
    archive: ZipFile,
    name: str,
    *,
    source: str | None = None,
    max_bytes: int = MAX_XML_BYTES,
) -> bytes:
    label = source or name
    info = archive.getinfo(name)
    if info.file_size > max_bytes:
        raise UnsafeXmlError(f"{label} 超过 XML 大小上限 {max_bytes} bytes")
    with archive.open(info, "r") as stream:
        return _read_bounded(stream, source=label, max_bytes=max_bytes)


def safe_zip_member_text(
    archive: ZipFile,
    name: str,
    *,
    source: str | None = None,
    max_bytes: int = MAX_XML_BYTES,
    allow_musicxml_doctype: bool = False,
) -> str:
    label = source or name
    data = safe_zip_member_bytes(
        archive,
        name,
        source=label,
        max_bytes=max_bytes,
    )
    return safe_xml_text(
        data,
        source=label,
        max_bytes=max_bytes,
        allow_musicxml_doctype=allow_musicxml_doctype,
    )


def _mask_markup(markup: str) -> str:
    return "".join(character if character in "\r\n" else " " for character in markup)


def _read_bounded(
    stream: BinaryIO,
    *,
    source: str,
    max_bytes: int,
) -> bytes:
    if max_bytes <= 0:
        raise ValueError("max_bytes must be greater than zero")
    data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise UnsafeXmlError(f"{source} 超过 XML 大小上限 {max_bytes} bytes")
    return data
