from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


def _namespace(tag: str) -> str:
    if tag.startswith("{"):
        return tag[1:].split("}", 1)[0]
    return ""


def _q(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}" if ns else tag


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if tag.startswith("{") else tag


def _text(element: ET.Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    return element.text.strip()


def _first_child_name(element: ET.Element | None, ns: str) -> str | None:
    if element is None or len(element) == 0:
        return None
    tag = element[0].tag
    return tag.removeprefix(f"{{{ns}}}") if ns else tag


def _indent(element: ET.Element, level: int = 0) -> None:
    i = "\n" + level * "  "
    if len(element):
        if not element.text or not element.text.strip():
            element.text = i + "  "
        for child in element:
            _indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not element.tail or not element.tail.strip()):
        element.tail = i


def _read_mxl(path: Path) -> str:
    with ZipFile(path) as archive:
        names = archive.namelist()
        musicxml_names = [
            name
            for name in names
            if name.lower().endswith((".xml", ".musicxml")) and not name.startswith("META-INF/")
        ]
        if not musicxml_names:
            raise ValueError(f"MXL 文件中没有找到 MusicXML：{path}")
        with archive.open(musicxml_names[0]) as handle:
            return handle.read().decode("utf-8")


def _mxl_rootfile_name(archive: ZipFile) -> str:
    try:
        container = ET.fromstring(archive.read("META-INF/container.xml"))
    except (KeyError, ET.ParseError):
        container = None
    if container is not None:
        for rootfile in container.iter():
            if _local_name(rootfile.tag) == "rootfile":
                full_path = rootfile.get("full-path")
                if full_path:
                    return full_path
    return next(
        item
        for item in archive.namelist()
        if item.lower().endswith((".xml", ".musicxml")) and not item.startswith("META-INF/")
    )


def _read_musicxml(path: Path) -> str:
    if path.suffix.lower() == ".mxl":
        with ZipFile(path) as archive:
            name = _mxl_rootfile_name(archive)
            return archive.read(name).decode("utf-8")
    return path.read_text(encoding="utf-8")
