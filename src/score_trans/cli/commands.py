from __future__ import annotations

import argparse
from pathlib import Path

from ..services.ocr_provider import OpenAICompatibleOCRProvider
from ..services.settings import ToolConfig
from ..services.file_service import FileService
from ..use_cases import (
    ConvertJianpuToMusicXmlUseCase,
    ConvertMusicXmlToJianpuUseCase,
    FullPipelineUseCase,
    RenderJianpuTextUseCase,
    RenderMusicXmlJianpuUseCase,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score Trans 五线谱 / 简谱互转")
    subparsers = parser.add_subparsers(dest="command")

    to_jianpu = subparsers.add_parser("to-jianpu", help="MusicXML 转简谱")
    to_jianpu.add_argument("input", type=Path)
    to_jianpu.add_argument("-o", "--output", type=Path)
    to_jianpu.add_argument("--target-key", default="C", help="简谱调，默认 C")
    to_jianpu.add_argument("--start-measure-number", type=int, help="显示用起始小节号")

    to_musicxml = subparsers.add_parser("to-musicxml", help="简谱文本转 MusicXML")
    to_musicxml.add_argument("input", type=Path)
    to_musicxml.add_argument("-o", "--output", type=Path, required=True)
    to_musicxml.add_argument("--title", default="Jianpu Import")

    render_jianpu = subparsers.add_parser("render-jianpu", help="简谱文本渲染为 SVG 谱面")
    render_jianpu.add_argument("input", type=Path)
    render_jianpu.add_argument("-o", "--output", type=Path, required=True)
    render_jianpu.add_argument("--title", default="简谱")

    render_musicxml = subparsers.add_parser("render-musicxml", help="MusicXML/MXL 转结构化简谱 SVG")
    render_musicxml.add_argument("input", type=Path)
    render_musicxml.add_argument("-o", "--output", type=Path, required=True)
    render_musicxml.add_argument("--title", default=None)
    render_musicxml.add_argument("--target-key", default="C", help="简谱调，默认 C")
    render_musicxml.add_argument("--start-measure-number", type=int, help="显示用起始小节号")
    render_musicxml.add_argument("--ocr-image", type=Path, help="用于补充文字/小节号 OCR 的页面图片")
    render_musicxml.add_argument("--ocr-dry-run", action="store_true", help="只验证 OCR 请求构造，不发起网络调用")

    recognize = subparsers.add_parser("recognize", help="图片/PDF 识别并导出 MusicXML、简谱文本和 SVG")
    recognize.add_argument("input", type=Path)
    recognize.add_argument("-o", "--output-dir", type=Path, default=Path("work") / "converted")
    recognize.add_argument("--target-key", default="C", help="简谱调，默认 C")
    recognize.add_argument("--start-measure-number", type=int, help="显示用起始小节号")
    recognize.add_argument("--title", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    file_service = FileService()

    if args.command == "to-jianpu":
        result = ConvertMusicXmlToJianpuUseCase().execute(
            args.input,
            target_key=args.target_key,
            start_measure_number=args.start_measure_number,
        )
        if args.output:
            file_service.write_text(args.output, result)
        else:
            print(result)
        return 0

    if args.command == "to-musicxml":
        result = ConvertJianpuToMusicXmlUseCase().execute_file(args.input, title=args.title)
        file_service.write_text(args.output, result)
        return 0

    if args.command == "render-jianpu":
        RenderJianpuTextUseCase().execute(args.input, args.output, title=args.title)
        return 0

    if args.command == "render-musicxml":
        RenderMusicXmlJianpuUseCase().execute(
            args.input,
            args.output,
            target_key=args.target_key,
            start_measure_number=args.start_measure_number,
            title=args.title,
            image_path=args.ocr_image,
            ocr_provider=OpenAICompatibleOCRProvider(dry_run=args.ocr_dry_run) if args.ocr_image else None,
        )
        return 0

    if args.command == "recognize":
        outputs = FullPipelineUseCase().execute(
            args.input,
            args.output_dir,
            config=ToolConfig.from_env(),
            target_key=args.target_key,
            start_measure_number=args.start_measure_number,
            title=args.title,
        )
        print(f"MusicXML: {outputs.musicxml_path}")
        print(f"Jianpu text: {outputs.jianpu_text_path}")
        print(f"Jianpu SVG: {outputs.jianpu_svg_path}")
        return 0

    try:
        from ..views.main_window import run_app
    except ImportError as exc:
        print('缺少 GUI 依赖，请先运行：python -m pip install -e ".[test]"')
        print(exc)
        return 2
    return run_app()
