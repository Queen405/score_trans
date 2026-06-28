from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = PROJECT_ROOT / "backend" / "score_trans" / "config" / "env.example"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the Score Trans OpenAPI schema")
    parser.add_argument("output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    schema_state = output.parent / "openapi-state"
    os.environ.setdefault("SCORE_TRANS_DATA_DIR", str(schema_state / "data"))
    os.environ.setdefault("SCORE_TRANS_CACHE_DIR", str(schema_state / "cache"))

    from score_trans.utils.env import load_project_env

    load_project_env(ENV_EXAMPLE)

    from score_trans.api.app import create_app
    from score_trans.models.ai.schemas import AiTranscribeResponse
    from score_trans.models.pipeline.schemas import PipelineResponse
    from score_trans.models.recognize.schemas import RecognizeResponse
    from pydantic import TypeAdapter

    schema = create_app().openapi()
    task_result_schema = TypeAdapter(
        AiTranscribeResponse | PipelineResponse | RecognizeResponse
    ).json_schema(ref_template="#/components/schemas/{model}")
    schema["components"]["schemas"].update(task_result_schema.get("$defs", {}))
    output.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
