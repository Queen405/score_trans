"""Manual prompt-tuning script for AI vision transcription.

Sends examples/pic/* to the configured vision model, validates the returned
Jianpu syntax, and writes a JSON report under work/prompt_test_results.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Ensure backend is importable when the script is run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from score_trans.domain.parse.jianpu_text import parse_jianpu_score
from score_trans.services.ai.providers.xiaomi_mimo import XiaomiMiMoProvider
from score_trans.services.ai.transcription.normalization import (
    clean_jianpu_text,
    ensure_jianpu_header,
)

PIC_DIR = Path(__file__).resolve().parent.parent / "examples" / "pic"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "work" / "prompt_test_results"


def validate_jianpu(text: str) -> list[str]:
    """Parse jianpu text and return list of validation error strings."""
    try:
        score = parse_jianpu_score(text)
    except ValueError as exc:
        return [f"PARSE FAILED: {exc}"]
    errors: list[str] = []
    for idx, measure in enumerate(score.measures, start=1):
        for err in measure.validation_errors:
            errors.append(f"第{idx}小节: {err}")
    return errors


def run_single_image(image_path: Path, provider: XiaomiMiMoProvider) -> dict:
    """Test one image and return a result dict."""
    print(f"\n{'=' * 60}")
    print(f"Testing: {image_path.name}")
    print(f"{'=' * 60}")

    t0 = time.time()
    try:
        result = provider.transcribe_page(
            image_path,
            target_key="C",
            title="瑞雪迎春",
            page_index=0,
        )
    except Exception as exc:
        elapsed = time.time() - t0
        print(f"  API ERROR ({elapsed:.1f}s): {exc}")
        return {
            "file": image_path.name,
            "status": "api_error",
            "error": str(exc),
            "elapsed": elapsed,
        }

    elapsed = time.time() - t0
    jianpu_text = result.jianpu_text
    cleaned = clean_jianpu_text(jianpu_text)
    with_header = ensure_jianpu_header(
        cleaned,
        target_key=result.key or "C",
        meter=result.meter,
    )

    errors = validate_jianpu(with_header)

    print(f"  Time: {elapsed:.1f}s")
    print(f"  Confidence: {result.confidence}")
    print(f"  Warnings from AI: {result.warnings}")
    print(f"  Jianpu text length: {len(with_header)} chars")
    print(f"  First 200 chars:\n    {with_header[:200]}")
    if errors:
        print(f"  *** VALIDATION ERRORS ({len(errors)}):")
        for err in errors[:10]:
            print(f"      - {err}")
        if len(errors) > 10:
            print(f"      ... and {len(errors) - 10} more")
    else:
        print("  OK - no validation errors")

    return {
        "file": image_path.name,
        "status": "validation_error" if errors else "ok",
        "elapsed": elapsed,
        "confidence": result.confidence,
        "ai_warnings": result.warnings,
        "jianpu_text": with_header,
        "validation_errors": errors,
        "raw_response": jianpu_text,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    images = sorted(PIC_DIR.glob("*.png"))
    if not images:
        print(f"No PNG images found in {PIC_DIR}")
        return

    test_images = images[:3]
    print(f"Testing {len(test_images)} of {len(images)} images...")

    provider = XiaomiMiMoProvider(timeout=300)

    results = []
    for index, img in enumerate(test_images):
        result = run_single_image(img, provider)
        results.append(result)
        if index < len(test_images) - 1:
            time.sleep(2)

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    ok_count = sum(1 for result in results if result["status"] == "ok")
    err_count = sum(1 for result in results if result["status"] == "validation_error")
    api_err = sum(1 for result in results if result["status"] == "api_error")

    print(f"  OK: {ok_count}, Validation errors: {err_count}, API errors: {api_err}")

    all_errors: list[str] = []
    for result in results:
        all_errors.extend(result.get("validation_errors", []))

    if all_errors:
        print(f"\nAll validation errors ({len(all_errors)}):")
        for err in all_errors:
            print(f"  - {err}")

    output_file = OUTPUT_DIR / "results.json"
    output_file.write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nDetailed results saved to {output_file}")


if __name__ == "__main__":
    main()
