"""Iterative test: send examples/pic/* to the AI vision model,
validate that each response is strictly conformant jianpu syntax,
and report violations for prompt tuning.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from score_trans.services.ai.providers.xiaomi_mimo import XiaomiMiMoProvider
from score_trans.domain.parse.jianpu_text import parse_jianpu_score
from score_trans.services.ai.transcription.normalization import clean_jianpu_text, ensure_jianpu_header

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


def test_single_image(image_path: Path, provider: XiaomiMiMoProvider) -> dict:
    """Test one image and return a result dict."""
    print(f"\n{'='*60}")
    print(f"Testing: {image_path.name}")
    print(f"{'='*60}")

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
    with_header = ensure_jianpu_header(cleaned, target_key=result.key or "C", meter=result.meter)

    # Validate
    errors = validate_jianpu(with_header)

    print(f"  Time: {elapsed:.1f}s")
    print(f"  Confidence: {result.confidence}")
    print(f"  Warnings from AI: {result.warnings}")
    print(f"  Jianpu text length: {len(with_header)} chars")
    print(f"  First 200 chars:\n    {with_header[:200]}")
    if errors:
        print(f"  *** VALIDATION ERRORS ({len(errors)}):")
        for e in errors[:10]:
            print(f"      - {e}")
        if len(errors) > 10:
            print(f"      ... and {len(errors)-10} more")
    else:
        print(f"  OK - no validation errors")

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


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    images = sorted(PIC_DIR.glob("*.png"))
    if not images:
        print(f"No PNG images found in {PIC_DIR}")
        return

    # Only test first 3 images to save API cost on initial run
    test_images = images[:3]
    print(f"Testing {len(test_images)} of {len(images)} images...")

    provider = XiaomiMiMoProvider(timeout=300)

    results = []
    for img in test_images:
        result = test_single_image(img, provider)
        results.append(result)
        # Brief pause between API calls
        if test_images.index(img) < len(test_images) - 1:
            time.sleep(2)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    ok_count = sum(1 for r in results if r["status"] == "ok")
    err_count = sum(1 for r in results if r["status"] == "validation_error")
    api_err = sum(1 for r in results if r["status"] == "api_error")

    print(f"  OK: {ok_count}, Validation errors: {err_count}, API errors: {api_err}")

    # Collect all unique error patterns
    all_errors: list[str] = []
    for r in results:
        all_errors.extend(r.get("validation_errors", []))

    if all_errors:
        print(f"\nAll validation errors ({len(all_errors)}):")
        for e in all_errors:
            print(f"  - {e}")

    # Save results
    output_file = OUTPUT_DIR / "results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nDetailed results saved to {output_file}")

    # Save raw texts for inspection
    for r in results:
        if r.get("raw_response"):
            txt_file = OUTPUT_DIR / f"{r['file']}.jianpu.txt"
            txt_file.write_text(r["raw_response"], encoding="utf-8")

    return results


if __name__ == "__main__":
    main()
