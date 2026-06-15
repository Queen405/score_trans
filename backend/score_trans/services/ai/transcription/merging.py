from __future__ import annotations

import re


def merge_page_jianpu_texts(
    page_texts: list[str],
    *,
    target_key: str = "C",
    title: str | None = None,
) -> str:
    non_empty = [text for text in page_texts if text.strip()]
    if not non_empty:
        return f"1={target_key}\n4/4\n"

    first_header = extract_header(non_empty[0])
    header: list[str] = []
    resolved_title = title or first_header.get("title")
    if resolved_title:
        header.append(f"title={resolved_title}")
    header.append(f"1={first_header.get('key') or target_key}")
    header.append(first_header.get("meter") or "4/4")
    if first_header.get("tempo"):
        header.append(f"tempo={first_header['tempo']}")

    body: list[str] = []
    for index, text in enumerate(non_empty, start=1):
        stripped = strip_header(text)
        if stripped:
            body.append(f"// Page {index}")
            body.append(stripped)
    return "\n".join(header + [""] + body).strip()


def extract_header(text: str) -> dict[str, str]:
    header: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("title="):
            header["title"] = line.split("=", 1)[1].strip()
        elif line.startswith("1="):
            header["key"] = line.split("=", 1)[1].strip()
        elif line.startswith("tempo="):
            header["tempo"] = line.split("=", 1)[1].strip()
        elif re.fullmatch(r"\d+\s*/\s*\d+", line) and "meter" not in header:
            header["meter"] = line.replace(" ", "")
    return header


def strip_header(text: str) -> str:
    body: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if (
            line.startswith("title=")
            or line.startswith("1=")
            or line.startswith("tempo=")
            or re.fullmatch(r"\d+\s*/\s*\d+", line)
        ):
            continue
        body.append(raw)
    return "\n".join(body).strip()


def first_present(values: list[str | None]) -> str | None:
    for value in values:
        if value:
            return value
    return None
