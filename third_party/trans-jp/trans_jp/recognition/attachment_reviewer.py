from __future__ import annotations

from collections import Counter
import json
from ..models.melody import (
    AttachmentReviewRequest,
    AttachmentReviewResult,
    AttachmentRelation,
)

REVIEW_SYSTEM = "You review only numbered local musical marks attached to confirmed Jianpu digits. Return strict JSON. Never invent coordinates, IDs, durations or missing notes. Unknown is preferable to a guessed relationship."


def review_prompt(request: AttachmentReviewRequest) -> str:
    candidates = [
        {"id": c.candidate_id, "allowed_kinds": c.kinds, "possible_owners": c.owners}
        for c in request.candidates
    ]
    return (
        "蓝框 B 标签为已确认主体，红框 A 标签为附属墨迹。只判断红框类别和归属。"
        "kind可用 octave_up/octave_down/augmentation/underline/extension/sharp/flat/natural/non_music/unsupported。"
        "点和变音记号最多一个owner；只有共享减时线允许多个owner。不能把连线、反复点、歌词标点当附点。"
        "unknown_ids列出无法判断的附属编号。若主体附近还有未框出的记号，missing_evidence列出主体编号；不发明新框。"
        "返回 schema_version=1, relations:[{candidate_id,body_ids:[主体编号],kind}], unknown_ids:[], missing_evidence:[]。"
        "倚音、连音组、延音弧或无法解释的音乐结构标为unsupported并指定邻近主体，不能当non_music忽略。不能填写或推测音符时值，不能修改主体数字。当前主体："
        + json.dumps(request.body_ids)
        + "；当前附属："
        + json.dumps(candidates, ensure_ascii=False)
    )


def parse_attachment_review(
    content: str, request: AttachmentReviewRequest
) -> AttachmentReviewResult:
    out = AttachmentReviewResult(request.request_id, raw_response=content)
    candidates = {c.candidate_id: c for c in request.candidates}

    def invalid(reason: str) -> AttachmentReviewResult:
        out.status = "invalid"
        out.reason = reason
        out.unknown_ids = list(candidates)
        return out

    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return invalid("JSON 无效")
    if (
        not isinstance(data, dict)
        or type(data.get("schema_version")) is not int
        or data["schema_version"] != 1
    ):
        return invalid("复核协议无效")
    if any(
        not isinstance(data.get(k, []), list)
        for k in ("relations", "unknown_ids", "missing_evidence")
    ):
        return invalid("复核数组格式错误")
    unknown = data.get("unknown_ids", [])
    missing = data.get("missing_evidence", [])
    if any(not isinstance(cid, str) or cid not in candidates for cid in unknown) or any(
        not isinstance(cid, str) or cid not in request.body_ids for cid in missing
    ):
        return invalid("复核编号超出请求")
    relations = data.get("relations", [])
    if any(
        not isinstance(r, dict) or not isinstance(r.get("candidate_id"), str)
        for r in relations
    ):
        return invalid("关系格式错误")
    counts = Counter([r["candidate_id"] for r in relations] + unknown)
    for r in relations:
        cid = r["candidate_id"]
        owners = r.get("body_ids")
        kind = r.get("kind")
        if cid not in candidates:
            return invalid("附属编号不存在")
        c = candidates[cid]
        allowed = set(c.kinds) | {"non_music", "unsupported"}
        if "unclassified" in allowed:
            allowed |= {
                "sharp",
                "flat",
                "natural",
                "octave_up",
                "octave_down",
                "augmentation",
                "underline",
                "extension",
            }
        if (
            not isinstance(owners, list)
            or any(
                not isinstance(o, str) or o not in c.owners or o not in request.body_ids
                for o in owners
            )
            or len(set(owners)) != len(owners)
            or not isinstance(kind, str)
            or kind not in allowed
        ):
            out.unknown_ids.append(cid)
            continue
        if (
            counts[cid] != 1
            or (kind != "non_music" and not owners)
            or (kind not in ("underline", "non_music") and len(owners) != 1)
            or (kind == "non_music" and owners)
        ):
            out.unknown_ids.append(cid)
            continue
        if kind in ("underline", "extension") and c.line is None:
            out.unknown_ids.append(cid)
            continue
        out.relations.append(AttachmentRelation(cid, tuple(owners), kind, source="vlm"))
    resolved = {r.candidate_id for r in out.relations}
    out.unknown_ids = sorted(
        set(out.unknown_ids) | set(unknown) | (set(candidates) - resolved)
    )
    out.relations = [r for r in out.relations if r.candidate_id not in out.unknown_ids]
    out.missing_evidence = list(dict.fromkeys(missing))
    return out


def parse_melody_metadata(content: str, region_ids: tuple[str, ...]) -> dict:
    import re

    result = {
        "key": {"value": None, "status": "unknown"},
        "meter": {"value": None, "status": "unknown"},
        "changes": [],
        "warnings": [],
    }
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return result
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        return result
    for field, pattern in [
        ("key", r"[A-G](?:b|#)?"),
        ("meter", r"[1-9][0-9]?/(?:1|2|4|8|16|32)"),
    ]:
        value = data.get(field)
        if (
            isinstance(value, dict)
            and value.get("status") == "confirmed"
            and isinstance(value.get("value"), str)
            and re.fullmatch(pattern, value["value"])
            and value.get("region_id") in region_ids
        ):
            result[field] = {
                "value": value["value"],
                "status": "observed",
                "region_id": value["region_id"],
                "source": "vlm",
            }
    if any(result[field]["status"] == "observed" for field in ("key", "meter")):
        result["warnings"].append(
            "整页模型读数仅为候选，缺少局部独立证据；不得作为已确认调号/拍号"
        )
    if data.get("changes_detected") is True:
        result["warnings"].append("页面存在调号/拍号变化，变化位置及生效范围尚未确认")
        result["changes"] = [{"status": "unknown"}]
    return result


def parse_local_metadata(content: str, region_ids: tuple[str, ...]) -> list[dict]:
    import re

    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return []
    if (
        not isinstance(data, dict)
        or type(data.get("schema_version")) is not int
        or data["schema_version"] != 1
        or not isinstance(data.get("declarations"), list)
    ):
        return []
    entries = data["declarations"]
    counts = Counter(
        e.get("region_id")
        for e in entries
        if isinstance(e, dict) and isinstance(e.get("region_id"), str)
    )
    result = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("region_id"), str):
            continue
        rid = entry["region_id"]
        if rid not in region_ids or counts[rid] != 1:
            continue
        key = entry.get("key_text")
        meter = entry.get("meter_text")
        parsed_key = None
        if isinstance(key, str):
            normalized = key.replace("♭", "b").replace("♯", "#").replace(" ", "")
            match = re.fullmatch(r"1=([#b]?)([A-G])([#b]?)", normalized)
            if match and not (match[1] and match[3]):
                parsed_key = match[2] + (match[1] or match[3])
        parsed_meter = (
            meter
            if isinstance(meter, str)
            and re.fullmatch(r"[1-9][0-9]?/(?:1|2|4|8|16|32)", meter)
            else None
        )
        if parsed_key or parsed_meter:
            result.append(
                {
                    "region_id": rid,
                    "key": parsed_key,
                    "meter": parsed_meter,
                    "key_text": key,
                    "meter_text": meter,
                    "status": "observed_local",
                }
            )
    return result
