from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
from typing import Protocol
from ..models.classification import (
    CandidateBatchRequest,
    CandidateBatchResult,
    CandidateClassification,
)
from ..models.contracts import CompletionResult

CLASSIFICATION_SYSTEM = (
    "You classify individual printed Jianpu symbol bodies inside BLUE rectangles. "
    "Return strict JSON schema_version=3. Never transcribe a melody or output coordinates. "
    "Do not confuse the ID labels or neighboring symbols with the boxed subject. "
    "Digits in titles, page numbers, lyrics, key/time signatures, tempo and watermarks are NOT notes. "
    "Unknown or non-music ink must be explicitly reported as unknown, never guessed as rest 0."
)


def classification_prompt(request: CandidateBatchRequest) -> str:
    return (
        "第一张是原行上下文，第二张是候选图册。逐个识别蓝框主体，每个指定编号必须出现一次。"
        "只识别数字0至7和小节线，不输出时值、八度、和弦、歌词或row_text。"
        "高音1的圆点和横线不属于数字本体，不能写i；只返回1。"
        "标题、署名、歌词、调号拍号速度中的数字、点、括号、字母、横线、水印、粘连多数字均返回unknown。"
        "小节线只认音符之间的竖线，纸张边框和表格线不是小节线。"
        "不要根据候选顺序补齐缺失数字。看不清必须unknown。"
        "输出格式："
        + json.dumps(
            {
                "schema_version": 3,
                "items": [
                    {
                        "candidate_id": "本次编号",
                        "label": "3",
                        "kind": "digit",
                        "confidence": 0.9,
                        "status": "recognized",
                    }
                ],
                "unresolved": [
                    {
                        "candidate_id": "其他编号",
                        "reason": "non_music 或 ambiguous 或 unreadable",
                    }
                ],
            },
            ensure_ascii=False,
        )
        + " label只能是0,1,2,3,4,5,6,7,barline,unknown；kind只能是digit,barline,unknown。"
        + "本次编号："
        + json.dumps(request.candidate_ids)
    )


class CandidateClassifier(Protocol):
    def classify(self, request: CandidateBatchRequest) -> CompletionResult: ...


def parse_candidate_response(
    content: str, request: CandidateBatchRequest
) -> CandidateBatchResult:
    result = CandidateBatchResult(
        request.batch_id, request.registry.digest, raw_response=content
    )

    def invalid_all(reason: str) -> CandidateBatchResult:
        result.status = "batch_response_invalid"
        result.warnings.append(reason)
        result.items = [
            CandidateClassification(cid, status="candidate_invalid", reason=reason)
            for cid in request.candidate_ids
        ]
        return result

    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return invalid_all("JSON 无效，不修补截断的分类结果")
    if (
        not isinstance(data, dict)
        or type(data.get("schema_version")) is not int
        or data["schema_version"] != 3
    ):
        return invalid_all("响应协议不是 v3")
    if not isinstance(data.get("items"), list) or not isinstance(
        data.get("unresolved", []), list
    ):
        return invalid_all("items/unresolved 必须是数组")
    by_id = defaultdict(list)
    for item in data["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("candidate_id"), str):
            result.warnings.append("忽略无编号或格式错误的 item")
            continue
        by_id[item["candidate_id"]].append(item)
    for item in data.get("unresolved", []):
        if isinstance(item, dict) and isinstance(item.get("candidate_id"), str):
            by_id[item["candidate_id"]].append(
                {**item, "label": "unknown", "kind": "unknown", "status": "unresolved"}
            )
        else:
            result.warnings.append("忽略格式错误的 unresolved")
    registry = {c.candidate_id: c for c in request.registry.candidates}
    if set(by_id) - set(request.candidate_ids):
        result.warnings.append("响应包含其他批次或不存在的编号，已忽略")
    for cid in request.candidate_ids:
        entries = by_id.get(cid, [])
        if len(entries) != 1:
            reason = "模型遗漏候选" if not entries else "重复编号，全部拒绝"
            result.items.append(
                CandidateClassification(
                    cid,
                    status="candidate_unresolved"
                    if not entries
                    else "candidate_invalid",
                    reason=reason,
                )
            )
            continue
        item = entries[0]
        label, kind, status = item.get("label"), item.get("kind"), item.get("status")
        confidence = item.get("confidence")
        if confidence is not None and (
            type(confidence) not in (int, float)
            or not math.isfinite(confidence)
            or not 0 <= confidence <= 1
        ):
            result.items.append(
                CandidateClassification(
                    cid, status="candidate_invalid", reason="置信度格式错误"
                )
            )
            continue
        if label == "unknown" and kind == "unknown":
            result.items.append(
                CandidateClassification(
                    cid,
                    confidence=confidence,
                    reason=str(item.get("reason") or "unknown"),
                )
            )
        elif status != "recognized" or not (
            (label in tuple("01234567") and kind == "digit")
            or (label == "barline" and kind == "barline")
        ):
            result.items.append(
                CandidateClassification(
                    cid, status="candidate_invalid", reason="标签、类型或状态不合法"
                )
            )
        elif (
            cid not in registry or registry[cid].kind != kind or registry[cid].ambiguous
        ):
            result.items.append(
                CandidateClassification(
                    cid,
                    status="candidate_invalid",
                    reason="类型与本地候选不符或主体粘连",
                )
            )
        else:
            result.items.append(
                CandidateClassification(cid, label, kind, confidence, "recognized")
            )
    return result


def classify_batches(
    requests: list[CandidateBatchRequest],
    client: CandidateClassifier,
    *,
    concurrency: int = 2,
    on_result: Callable[[CandidateBatchRequest, CandidateBatchResult], None]
    | None = None,
) -> list[CandidateBatchResult]:
    if concurrency < 1:
        raise ValueError("concurrency must be positive")

    def classify(request: CandidateBatchRequest) -> CandidateBatchResult:
        try:
            completion = client.classify(request)
            if completion.finish_reason not in ("stop", None):
                result = parse_candidate_response("", request)
                result.raw_response = completion.content
                result.finish_reason = completion.finish_reason
                result.warnings = [f"模型输出未完成: {completion.finish_reason}"]
                return result
            result = parse_candidate_response(completion.content, request)
            result.finish_reason = completion.finish_reason
            return result
        except Exception as exc:
            return CandidateBatchResult(
                request.batch_id,
                request.registry.digest,
                [
                    CandidateClassification(
                        cid, reason=f"批次请求失败: {type(exc).__name__}"
                    )
                    for cid in request.candidate_ids
                ],
                status="batch_request_failed",
                warnings=[f"{request.batch_id}: 请求失败 ({type(exc).__name__})"],
            )

    results = {}
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(classify, request): request for request in requests}
        for future in as_completed(futures):
            request = futures[future]
            result = future.result()
            results[request.batch_id] = result
            if on_result:
                on_result(request, result)
    return [results[request.batch_id] for request in requests]
