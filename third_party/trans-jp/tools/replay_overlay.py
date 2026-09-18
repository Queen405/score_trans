from __future__ import annotations
import argparse
from pathlib import Path
from trans_jp.io.replay_reader import ReplayClient
from trans_jp.io.output_writer import write_outputs
from trans_jp.models.contracts import CliConfig, LlmConfig
from trans_jp.pipeline.runner import run


def main() -> None:
    parser = argparse.ArgumentParser(
        description="不调用模型，使用已保存的行 JSON 回放定位和绘制"
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--responses-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--min-image-edge", type=int, default=2500)
    args = parser.parse_args()
    if args.responses_dir.resolve() == (args.output_dir / "rows").resolve():
        parser.error("回放输入 rows 目录不能与输出 rows 目录相同")
    config = CliConfig(
        args.input,
        args.output_dir,
        LlmConfig("", "", ""),
        min_image_edge=args.min_image_edge,
        debug=True,
    )
    result = run(config, ReplayClient(args.responses_dir))
    write_outputs(result, args.output_dir)
    print(
        f"{len(result.source_map['sheets'][0]['elements'])} located; {len(result.warnings)} warnings; {args.output_dir}"
    )


if __name__ == "__main__":
    main()
