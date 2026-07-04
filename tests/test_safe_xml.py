from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest

from score_trans.domain.parse.musicxml import read_musicxml_text
from score_trans.services.overlay.omr_parser import OmrParser
from score_trans.utils.safe_xml import (
    UnsafeXmlError,
    safe_xml_fromstring,
    safe_zip_member_bytes,
)


ENTITY_BOMB = """\
<?xml version="1.0"?>
<!DOCTYPE score-partwise [
  <!ENTITY a "1234567890">
  <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
]>
<score-partwise><movement-title>&b;</movement-title></score-partwise>
"""

MUSICXML_DOCTYPE = """\
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0.3 Partwise//EN" \
"http://www.musicxml.org/dtds/partwise.dtd">\
"""


def test_safe_xml_accepts_normal_document() -> None:
    root = safe_xml_fromstring("<score-partwise><part-list/></score-partwise>")

    assert root.tag == "score-partwise"


@pytest.mark.parametrize(
    "payload",
    [
        ENTITY_BOMB,
        "<!DoCtYpE score-partwise><score-partwise/>",
        "<score-partwise><!ENTITY x 'boom'></score-partwise>",
    ],
)
def test_safe_xml_rejects_doctype_and_entity_declarations(payload: str) -> None:
    with pytest.raises(UnsafeXmlError, match="DTD|ENTITY"):
        safe_xml_fromstring(payload)


def test_safe_xml_and_zip_members_enforce_uncompressed_size_limit(
    tmp_path: Path,
) -> None:
    with pytest.raises(UnsafeXmlError, match="大小上限"):
        safe_xml_fromstring("<root>" + ("x" * 128) + "</root>", max_bytes=32)

    archive_path = tmp_path / "large.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("score.xml", b"x" * 128)
    with ZipFile(archive_path) as archive:
        with pytest.raises(UnsafeXmlError, match="大小上限"):
            safe_zip_member_bytes(archive, "score.xml", max_bytes=32)


def test_mxl_musicxml_rejects_entity_declarations(tmp_path: Path) -> None:
    mxl = tmp_path / "unsafe.mxl"
    with ZipFile(mxl, "w") as archive:
        archive.writestr(
            "META-INF/container.xml",
            """<container><rootfiles><rootfile full-path="score.xml"/></rootfiles></container>""",
        )
        archive.writestr("score.xml", ENTITY_BOMB)

    with pytest.raises(UnsafeXmlError, match="DTD|ENTITY"):
        read_musicxml_text(mxl)


def test_mxl_musicxml_accepts_standard_external_doctype(tmp_path: Path) -> None:
    mxl = tmp_path / "audiveris.mxl"
    with ZipFile(mxl, "w") as archive:
        archive.writestr(
            "META-INF/container.xml",
            """<container><rootfiles><rootfile full-path="score.xml"/></rootfiles></container>""",
        )
        archive.writestr(
            "score.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
{MUSICXML_DOCTYPE}
<score-partwise version="4.0.3"><part-list/></score-partwise>""",
        )

    text = read_musicxml_text(mxl)
    root = safe_xml_fromstring(text)

    assert "<!DOCTYPE" not in text
    assert root.tag == "score-partwise"


@pytest.mark.parametrize(
    "doctype",
    [
        """<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0.3 Partwise//EN"
        "http://www.musicxml.org/dtds/partwise.dtd" [
          <!ENTITY injected "boom">
        ]>""",
        """<!DOCTYPE score-partwise SYSTEM "https://attacker.invalid/score.dtd">""",
        """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
        "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">""",
    ],
)
def test_mxl_musicxml_rejects_unsafe_doctype_variants(
    tmp_path: Path,
    doctype: str,
) -> None:
    mxl = tmp_path / "unsafe-doctype.mxl"
    with ZipFile(mxl, "w") as archive:
        archive.writestr(
            "META-INF/container.xml",
            """<container><rootfiles><rootfile full-path="score.xml"/></rootfiles></container>""",
        )
        archive.writestr(
            "score.xml",
            f"{doctype}<score-partwise><movement-title>&injected;</movement-title></score-partwise>",
        )

    with pytest.raises(UnsafeXmlError, match="DTD|ENTITY"):
        read_musicxml_text(mxl)


def test_omr_sheet_rejects_entity_declarations(tmp_path: Path) -> None:
    omr = tmp_path / "unsafe.omr"
    with ZipFile(omr, "w") as archive:
        archive.writestr("book/sheet#1/sheet#1.xml", ENTITY_BOMB)

    with pytest.raises(UnsafeXmlError, match="DTD|ENTITY"):
        OmrParser().parse(omr)
