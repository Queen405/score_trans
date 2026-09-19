from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from .pipeline.runner import run as _pipeline_run
from .recognition.row_recognizer import RowTranscriber
from .io.output_writer import write_outputs as write_outputs
from .models.contracts import CliConfig, LlmConfig, TransJpResult
from .models.errors import EngineError

_ENV_API_KEY = os.getenv("TRANS_JP_API_KEY", "")
_ENV_BASE_URL = os.getenv("TRANS_JP_BASE_URL", "")
_ENV_MODEL = os.getenv("TRANS_JP_MODEL", "")
_ENV_LYRICS_KEY = os.getenv("TRANS_JP_LYRICS_API_KEY", "")
_ENV_LYRICS_URL = os.getenv("TRANS_JP_LYRICS_BASE_URL", "")
_ENV_LYRICS_MODEL = os.getenv("TRANS_JP_LYRICS_MODEL", "")

logger = logging.getLogger("trans_jp")


def run(config: CliConfig, llm_client: RowTranscriber | None = None) -> TransJpResult:
    """Compatibility facade; pipeline remains free of process exits."""
    try:
        return _pipeline_run(config, llm_client)
    except EngineError as exc:
        raise SystemExit(exc.exit_code) from exc


EXIT_OK = 0
EXIT_IMAGE_LOAD_FAILED = 1
EXIT_NO_ROWS = 2
EXIT_LLM_ALL_FAILED = 3
EXIT_OUTPUT_WRITE_FAILED = 4
EXIT_ARG_ERROR = 5


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="trans-jp",
        description="简谱图片识别引擎：逐行调用视觉大模型，输出简谱文本 + 来源映射 + SVG 叠加层",
    )
    parser.add_argument(
        "--input", required=True, type=Path, help="输入简谱图片路径（PNG/JPG）"
    )
    parser.add_argument("--output-dir", required=True, type=Path, help="输出目录路径")
    parser.add_argument(
        "--api-key", default=_ENV_API_KEY, help="LLM API 密钥（或 TRANS_JP_API_KEY）"
    )
    parser.add_argument(
        "--base-url",
        default=_ENV_BASE_URL,
        help="LLM API 基地址（或 TRANS_JP_BASE_URL）",
    )
    parser.add_argument(
        "--model", default=_ENV_MODEL, help="模型名称（或 TRANS_JP_MODEL）"
    )
    parser.add_argument("--target-key", default="C", help="目标调号（如 C, G, F）")
    parser.add_argument("--title", default=None, help="曲名提示")
    parser.add_argument("--extra-prompt", default=None, help="额外识别要求")
    parser.add_argument(
        "--prompt-config", default=None, type=Path, help="外部 prompt YAML 配置路径"
    )
    parser.add_argument(
        "--max-tokens", default=4096, type=int, help="LLM 最大输出 token 数"
    )
    parser.add_argument("--temperature", default=0.1, type=float, help="LLM 温度参数")
    parser.add_argument(
        "--timeout", default=120.0, type=float, help="单次 LLM 请求超时（秒）"
    )
    parser.add_argument("--concurrency", default=2, type=int, help="并发行识别数")
    parser.add_argument(
        "--min-image-edge",
        default=2500,
        type=int,
        help="预防性放大：整图长边低于该像素数时先放大再分割/识别（0 表示不放大，上限 4 倍）",
    )
    parser.add_argument(
        "--recognition-mode",
        choices=("bodies", "notation", "melody"),
        default="bodies",
        help="bodies: v3 主体预览（默认）；notation: v2 语义；melody: 实验性单旋律属性",
    )
    parser.add_argument(
        "--body-responses-dir", type=Path, help="复用已保存 v3 rows，省去主体请求"
    )
    parser.add_argument(
        "--no-melody-review", action="store_true", help="melody 仅本地处理，疑点留空"
    )
    parser.add_argument(
        "--lyrics",
        choices=("off", "recognize"),
        default="off",
        help="歌词识别与音符误识别拦截；默认关闭",
    )
    parser.add_argument(
        "--lyrics-responses-dir", type=Path, help="回放歌词证据根目录，不调用文字服务"
    )
    parser.add_argument(
        "--lyrics-base-url",
        default=_ENV_LYRICS_URL,
        help="歌词 OCR/文字模型 OpenAI 兼容基地址，默认复用 --base-url",
    )
    parser.add_argument(
        "--lyrics-model",
        default=_ENV_LYRICS_MODEL,
        help="歌词 OCR/文字模型，默认复用 --model",
    )
    parser.add_argument(
        "--lyrics-api-key",
        default=_ENV_LYRICS_KEY,
        help="歌词 OCR/文字模型密钥，默认复用 --api-key",
    )
    parser.add_argument("--debug", action="store_true", help="启用调试日志")
    args = parser.parse_args(argv)

    for flag, value, env_name in (
        ("--api-key", args.api_key, "TRANS_JP_API_KEY"),
        ("--base-url", args.base_url, "TRANS_JP_BASE_URL"),
        ("--model", args.model, "TRANS_JP_MODEL"),
    ):
        if not value and not (args.body_responses_dir and args.no_melody_review):
            parser.exit(
                EXIT_ARG_ERROR,
                f"trans-jp: error: {flag} 必填（或设置环境变量 {env_name}）\n",
            )
    if args.lyrics_responses_dir and args.lyrics != "recognize":
        parser.exit(
            EXIT_ARG_ERROR, "--lyrics-responses-dir 需要 --lyrics recognize" + chr(10)
        )
    return args


def setup_logging(log_path: Path, *, debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger("trans_jp")
    root.setLevel(level)

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    try:
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError as exc:
        root.warning("无法写入日志文件 %s: %s", log_path, exc)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_ARG_ERROR

    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.error("输出目录不可用: %s", exc)
        return EXIT_OUTPUT_WRITE_FAILED
    setup_logging(args.output_dir / "trans-jp.log", debug=args.debug)

    config = CliConfig(
        input_path=args.input,
        output_dir=args.output_dir,
        llm=LlmConfig(
            api_key=args.api_key,
            base_url=args.base_url,
            model=args.model,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            timeout=args.timeout,
        ),
        target_key=args.target_key,
        title=args.title,
        extra_prompt=args.extra_prompt,
        prompt_config=args.prompt_config,
        concurrency=args.concurrency,
        min_image_edge=args.min_image_edge,
        debug=args.debug,
        recognition_mode=args.recognition_mode,
        body_responses_dir=args.body_responses_dir,
        melody_review=not args.no_melody_review,
        lyrics_mode=args.lyrics,
        lyrics_responses_dir=args.lyrics_responses_dir,
        lyrics_ocr=(
            LlmConfig(
                api_key=args.lyrics_api_key or args.api_key,
                base_url=args.lyrics_base_url or args.base_url,
                model=args.lyrics_model or args.model,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                timeout=args.timeout,
            )
            if args.lyrics == "recognize"
            else None
        ),
    )

    try:
        result = _pipeline_run(config)
        write_outputs(result, args.output_dir)
    except FileNotFoundError as exc:
        logger.error("图片加载失败: %s", exc)
        return EXIT_IMAGE_LOAD_FAILED
    except EngineError as exc:
        logger.error("%s", exc)
        return exc.exit_code

    if result.warnings:
        logger.warning("识别有 %d 个警告", len(result.warnings))
        for warning in result.warnings:
            logger.warning("  %s", warning)

    logger.info("trans-jp 完成")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
