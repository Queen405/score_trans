from __future__ import annotations

from pathlib import Path

from trans_jp.prompt_builder import PromptBuilder
from trans_jp.row_recognizer import recognize_rows
from trans_jp.schemas import RowSegment


def _make_rows(tmp_path: Path, count: int) -> list[RowSegment]:
    rows = []
    for i in range(count):
        path = tmp_path / f"row_{i}.png"
        path.touch()
        rows.append(
            RowSegment(
                index=i,
                y_top=i * 100,
                y_bottom=i * 100 + 50,
                image_path=path,
                width=800,
                height=50,
            )
        )
    return rows


def test_recognize_single_row(mock_llm_client, tmp_path):
    rows = _make_rows(tmp_path, 1)
    builder = PromptBuilder()
    results = recognize_rows(
        rows,
        mock_llm_client,
        builder,
        target_key="C",
        title=None,
        concurrency=1,
    )
    assert len(results) == 1
    result = results[0]
    assert result.row_type == "notation"
    assert result.jianpu_text == "1 2 3 4 |"
    assert len(result.tokens) == 5
    assert result.tokens[0].text == "1"
    assert result.tokens[0].index == 0
    assert result.tokens[4].role == "barline"
    assert result.confidence == 0.9


def test_concurrent_results_ordered_by_row_index(mock_llm_client, tmp_path):
    rows = _make_rows(tmp_path, 4)
    builder = PromptBuilder()
    results = recognize_rows(
        rows,
        mock_llm_client,
        builder,
        target_key="G",
        title="测试",
        concurrency=3,
    )
    assert [r.row.index for r in results] == [0, 1, 2, 3]


def test_failed_row_does_not_break_others(tmp_path):
    class FailingClient:
        def transcribe_row_with_retry(self, image_path, prompt, **kwargs):
            if "row_1" in str(image_path):
                raise RuntimeError("boom")
            from trans_jp.llm_client import CompletionResult

            return CompletionResult(
                content='{"row_type": "notation", "row_text": "1 |", "tokens": [], "warnings": [], "confidence": 0.8}',
                finish_reason="stop",
            )

    rows = _make_rows(tmp_path, 3)
    builder = PromptBuilder()
    results = recognize_rows(
        rows,
        FailingClient(),
        builder,
        target_key="C",
        title=None,
        concurrency=2,
    )
    assert len(results) == 3
    assert results[0].jianpu_text == "1 |"
    assert results[1].jianpu_text == ""
    assert any("识别失败" in w for w in results[1].warnings)
    assert results[2].jianpu_text == "1 |"


def test_prompt_contains_context(mock_llm_client, tmp_path):
    rows = _make_rows(tmp_path, 2)
    builder = PromptBuilder()
    recognize_rows(
        rows,
        mock_llm_client,
        builder,
        target_key="F",
        title="欢乐颂",
        extra_prompt="注意力度记号",
        concurrency=1,
    )
    _, prompt = mock_llm_client.calls[0]
    assert "第 0 行" in prompt
    assert "共 2 行" in prompt
    assert "1=F" in prompt
    assert "欢乐颂" in prompt
    assert "注意力度记号" in prompt


def test_progress_callback_invoked(mock_llm_client, tmp_path):
    rows = _make_rows(tmp_path, 3)
    builder = PromptBuilder()
    calls: list[tuple[int, int]] = []
    recognize_rows(
        rows,
        mock_llm_client,
        builder,
        target_key="C",
        title=None,
        concurrency=2,
        progress_callback=lambda done, total: calls.append((done, total)),
    )
    assert calls[-1] == (3, 3)
    assert len(calls) == 3
