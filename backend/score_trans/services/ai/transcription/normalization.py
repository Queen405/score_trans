from __future__ import annotations

import re


def clean_jianpu_text(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    return stripped


def ensure_jianpu_header(
    text: str,
    *,
    target_key: str,
    meter: str | None = None,
    title: str | None = None,
    tempo: str | int | None = None,
) -> str:
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    resolved_key = normalize_key_value(target_key) or "C"
    resolved_meter = normalize_meter_value(meter) or "4/4"
    prefix: list[str] = []
    if title and not any(line.strip().startswith("title=") for line in lines):
        prefix.append(f"title={title}")
    if not any(re.fullmatch(r"\s*1\s*=\s*.+", line) for line in lines):
        prefix.append(f"1={resolved_key}")
    if not any(re.fullmatch(r"\s*\d+\s*/\s*\d+\s*", line) for line in lines):
        prefix.append(resolved_meter)
    if tempo is not None and not any(line.strip().startswith("tempo=") for line in lines):
        tempo_str = str(tempo)
        tempo_value = tempo_str.split("=", 1)[-1].strip() if "=" in tempo_str else tempo_str.strip()
        if tempo_value:
            prefix.append(f"tempo={tempo_value}")
    return "\n".join(prefix + lines).strip()


def normalize_key_value(value: str | None) -> str | None:
    if not value:
        return None
    work = value.strip()
    if work.startswith("1="):
        work = work.split("=", 1)[1].strip()
    return work or None


def normalize_meter_value(value: str | None) -> str | None:
    if not value:
        return None
    match = re.fullmatch(r"\s*\d+\s*/\s*\d+\s*", value)
    if not match:
        return None
    return value.replace(" ", "")
