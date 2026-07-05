from __future__ import annotations

import os
import re
import shlex
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from zipfile import BadZipFile

from ...domain.parse.musicxml import read_musicxml_text
from ...models.common.errors import ExternalToolError
from ...models.common.paths import PROJECT_ROOT
from ...models.settings.config import ToolConfig
from ...utils.safe_xml import UnsafeXmlError, safe_xml_fromstring
from .image_preprocess import (
    ensure_min_resolution,
    is_pdf,
    is_raster_image,
    parse_low_interline,
    retry_scale_from_interline,
    upscale_by_factor,
)

_MOVEMENT_STEM_PATTERN = re.compile(r"^(?P<base>.+)\.mvt(?P<number>\d+)$", re.I)

_RESCALE_MIN_EDGE_FALLBACK = 2500
_RESCALE_MAX_PIXELS_FALLBACK = 20_000_000


@dataclass(slots=True)
class CommandResult:
    args: list[str]
    stdout: str
    stderr: str


def _run(
    args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None
) -> CommandResult:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
    except FileNotFoundError as exc:
        raise ExternalToolError(f"找不到外部程序：{args[0]}") from exc
    except PermissionError as exc:
        raise ExternalToolError(
            f"无法执行外部程序（权限被拒绝或路径无效）：{args[0]}\n"
            f"请检查设置中的路径是否正确。"
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr or ""
        stdout = exc.stdout or ""
        raise ExternalToolError(
            "外部程序执行失败，请查看完整日志定位原因。",
            stdout=stdout,
            stderr=stderr,
        ) from exc
    return CommandResult(args=args, stdout=completed.stdout, stderr=completed.stderr)


def recognize_with_audiveris(
    input_file: Path, output_dir: Path, config: ToolConfig
) -> Path:
    input_file = input_file.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    effective_input, preprocessed_path = _apply_preventive_upscale(
        input_file, output_dir, config
    )

    try:
        _run_audiveris(effective_input, output_dir, config)
    except ExternalToolError as first_error:
        retry_path = _maybe_retry_after_low_interline(
            first_error, effective_input, output_dir, config
        )
        if retry_path is None:
            raise ExternalToolError(
                _summarize_audiveris_failure(
                    first_error.stdout or "", first_error.stderr or "", output_dir
                ),
                stdout=first_error.stdout,
                stderr=first_error.stderr,
            ) from first_error
        _run_audiveris(retry_path, output_dir, config)
        effective_input = retry_path

    return _select_musicxml_output(output_dir, effective_input)


def _run_audiveris(input_file: Path, output_dir: Path, config: ToolConfig) -> None:
    audiveris_path = Path(config.audiveris_path)
    env = _java_env(config)
    audiveris_args = _audiveris_args(input_file, output_dir, config)
    if audiveris_path.name.lower() in {"gradlew", "gradlew.bat"}:
        args = [
            str(audiveris_path),
            ":app:run",
            f"-PcmdLineArgs={','.join(audiveris_args)}",
            f"-PaudiverisMaxHeap={_validated_max_heap(config)}",
        ]
        _run(args, cwd=audiveris_path.parent, env=env)
    else:
        args = [config.audiveris_path or "audiveris", *audiveris_args]
        _run(args, env=env)


def _select_musicxml_output(output_dir: Path, input_file: Path) -> Path:
    candidates = (
        sorted(output_dir.rglob("*.musicxml"))
        + sorted(output_dir.rglob("*.mxl"))
        + sorted(output_dir.rglob("*.xml"))
    )
    if not candidates:
        raise ExternalToolError("Audiveris 已执行，但没有找到 MusicXML 输出文件。")
    movement_group = _select_movement_group(candidates, input_file.stem)
    if movement_group is not None and len(movement_group) > 1:
        base_name, movements = movement_group
        merged_path = movements[0].parent / f"{base_name}.musicxml"
        _merge_movement_musicxml(movements, merged_path)
        return merged_path
    return candidates[0]


def _apply_preventive_upscale(
    input_file: Path, output_dir: Path, config: ToolConfig
) -> tuple[Path, Path | None]:
    if not getattr(config, "audiveris_auto_upscale", True):
        return input_file, None
    if not is_raster_image(input_file):
        return input_file, None
    min_edge = getattr(config, "audiveris_min_image_edge", _RESCALE_MIN_EDGE_FALLBACK)
    max_pixels = _max_pixels_or_default(config)
    try:
        upscaled = ensure_min_resolution(
            input_file,
            output_dir,
            min_edge=min_edge,
            max_pixels=max_pixels,
        )
    except Exception:
        return input_file, None
    if upscaled is None:
        return input_file, None
    return upscaled, upscaled


def _maybe_retry_after_low_interline(
    error: ExternalToolError,
    input_file: Path,
    output_dir: Path,
    config: ToolConfig,
) -> Path | None:
    if not getattr(config, "audiveris_auto_upscale", True):
        return None
    if not is_raster_image(input_file) or is_pdf(input_file):
        return None
    raw_output = (error.stdout or "") + "\n" + (error.stderr or "")
    measured = parse_low_interline(raw_output)
    if measured is None or measured <= 0:
        return None
    factor = retry_scale_from_interline(measured)
    if factor <= 1.0:
        return None
    max_pixels = _max_pixels_or_default(config)
    try:
        return upscale_by_factor(
            input_file,
            output_dir,
            factor=factor,
            max_pixels=max_pixels,
        )
    except Exception:
        return None


_AUdiveris_STAGE_BY_CLASS = {
    "MultipleRestsBuilder": "多小节休止符",
    "BeamsStep": "连音线",
    "ClefBuilder": "谱号",
    "KeyBuilder": "调号",
    "TimeBuilder": "拍号",
    "TimeColumn": "拍号",
    "StemSeedsStep": "符干",
    "ChordBuilder": "和弦",
    "SlurBuilder": "连奏线",
    "NoteStep": "音符",
    "SymbolsStep": "符号",
}

_AUdiveris_LOW_INTERLINE_RE = re.compile(
    r"too low interline value of\s*(\d+)\s*pixels", re.IGNORECASE
)
_AUdiveris_NPE_CLASS_RE = re.compile(
    r"at org\.audiveris\.omr\..*?\((\w+)\.java:"
)


def _summarize_audiveris_failure(
    stdout: str, stderr: str, output_dir: Path
) -> str:
    """把 Audiveris 的原始输出提炼成一句人话。

    优先级：低分辨率 > 内部错误(定位阶段) > 转换未完成 > 通用兜底。
    末尾附上 .log 文件路径（若存在）供进阶排查。
    """
    blob = f"{stdout}\n{stderr}"

    log_hint = ""
    logs = sorted(
        output_dir.glob("*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if logs:
        log_hint = f"\n完整日志：{logs[0]}"

    low = _AUdiveris_LOW_INTERLINE_RE.search(blob)
    if low:
        return (
            f"谱面分辨率过低（行间距仅 {low.group(1)} 像素），"
            f"请在设置中调高「最小长边像素」后重试。{log_hint}"
        )

    if "NullPointerException" in blob:
        stage = "识别"
        for m in _AUdiveris_NPE_CLASS_RE.finditer(blob):
            if m.group(1) in _AUdiveris_STAGE_BY_CLASS:
                stage = _AUdiveris_STAGE_BY_CLASS[m.group(1)]
                break
        return (
            f"识别引擎在「{stage}」阶段内部出错，可能是该页谱面存在引擎无法处理的结构。"
            f"可尝试改用 AI 转录，或对该页单独处理。{log_hint}"
        )

    if "Could not export since transcription did not complete successfully" in blob:
        return (
            "谱面转换未完成，Audiveris 无法导出 MusicXML。"
            f"可尝试改用 AI 转录。{log_hint}"
        )

    return f"Audiveris 执行失败，请查看完整日志定位原因。{log_hint}"


def _max_pixels_or_default(config: ToolConfig) -> int:
    raw = (config.audiveris_max_pixel_count or "").strip()
    if not raw.isdigit():
        return _RESCALE_MAX_PIXELS_FALLBACK
    value = int(raw)
    return value if value > 0 else _RESCALE_MAX_PIXELS_FALLBACK


def _select_movement_group(
    candidates: list[Path], input_stem: str
) -> tuple[str, list[Path]] | None:
    groups: dict[tuple[Path, str], dict[int, Path]] = {}
    for candidate in candidates:
        match = _MOVEMENT_STEM_PATTERN.fullmatch(candidate.stem)
        if match is None:
            continue
        key = (candidate.parent, match.group("base"))
        number = int(match.group("number"))
        groups.setdefault(key, {}).setdefault(number, candidate)

    if not groups:
        return None

    matching_input = [
        (key, movements)
        for key, movements in groups.items()
        if key[1].casefold() == input_stem.casefold()
    ]
    choices = matching_input or list(groups.items())
    (_parent, base_name), indexed_movements = max(
        choices,
        key=lambda item: (
            len(item[1]),
            item[0][1].casefold(),
            str(item[0][0]).casefold(),
        ),
    )
    return base_name, [
        indexed_movements[number] for number in sorted(indexed_movements)
    ]


def _merge_movement_musicxml(movements: list[Path], output_path: Path) -> None:
    try:
        roots = [
            safe_xml_fromstring(
                read_musicxml_text(movement),
                source=movement.name,
            )
            for movement in movements
        ]
    except (
        BadZipFile,
        ET.ParseError,
        KeyError,
        OSError,
        StopIteration,
        UnicodeError,
        UnsafeXmlError,
    ) as exc:
        raise ExternalToolError(f"无法读取 Audiveris 乐章输出：{exc}") from exc

    for movement, root in zip(movements, roots, strict=True):
        if _local_name(root.tag) != "score-partwise":
            raise ExternalToolError(
                f"Audiveris 乐章输出格式不受支持：{movement.name} 不是 score-partwise。"
            )

    merged_root = roots[0]
    target_parts = _child_parts(merged_root)
    for movement, source_root in zip(movements[1:], roots[1:], strict=True):
        source_parts = _child_parts(source_root)
        if len(source_parts) != len(target_parts):
            raise ExternalToolError(
                f"无法合并 Audiveris 乐章 {movement.name}：声部数量不一致。"
            )
        target_parts_by_id = {
            part_id: part
            for part in target_parts
            if (part_id := part.get("id")) is not None
        }
        for index, source_part in enumerate(source_parts):
            source_id = source_part.get("id")
            target_part = (
                target_parts_by_id.get(source_id)
                if source_id is not None
                else target_parts[index]
            )
            if target_part is None:
                raise ExternalToolError(
                    f"无法合并 Audiveris 乐章 {movement.name}："
                    f"找不到声部 {source_id!r}。"
                )
            for child in source_part:
                if _local_name(child.tag) == "measure":
                    target_part.append(child)

    namespace = _namespace(merged_root.tag)
    if namespace:
        ET.register_namespace("", namespace)
    ET.indent(merged_root, space="  ")
    ET.ElementTree(merged_root).write(
        output_path,
        encoding="utf-8",
        xml_declaration=True,
    )


def _child_parts(root: ET.Element) -> list[ET.Element]:
    return [child for child in root if _local_name(child.tag) == "part"]


def _namespace(tag: str) -> str:
    if tag.startswith("{"):
        return tag[1:].split("}", 1)[0]
    return ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if tag.startswith("{") else tag


def _audiveris_args(
    input_file: Path, output_dir: Path, config: ToolConfig
) -> list[str]:
    args = ["-batch"]
    if config.audiveris_step.strip():
        args.extend(["-step", config.audiveris_step.strip()])
    if config.audiveris_force:
        args.append("-force")
    if config.audiveris_save:
        args.append("-save")
    if config.audiveris_swap:
        args.append("-swap")
    if config.audiveris_transcribe:
        args.append("-transcribe")
    if config.audiveris_sheets.strip():
        args.extend(["-sheets", config.audiveris_sheets.strip()])
    for constant in _merged_audiveris_constants(config):
        args.extend(["-constant", constant])
    args.extend(_split_extra_args(config.audiveris_extra_args))
    args.extend(
        [
            "-export",
            "-score-trans-overlay",
            "-output",
            str(output_dir),
            str(input_file),
        ]
    )
    return args


def _split_audiveris_constants(raw: str) -> list[str]:
    return [item.strip() for item in raw.replace("\n", ";").split(";") if item.strip()]


def _validated_max_pixel_count(config: ToolConfig) -> str:
    value = config.audiveris_max_pixel_count.strip()
    if not value:
        return ""
    if not value.isdigit():
        raise ExternalToolError(
            f"SCORE_TRANS_AUDIVERIS_MAX_PIXEL_COUNT 值无效："
            f"{config.audiveris_max_pixel_count!r}。需为非负整数（0 表示不限制）。"
        )
    return value


_MAX_PIXEL_COUNT_QNAME = "org.audiveris.omr.step.LoadStep.maxPixelCount"
_IMPLICIT_TUPLETS_QNAME = "org.audiveris.omr.sheet.ProcessingSwitches.implicitTuplets"


def _merged_audiveris_constants(config: ToolConfig) -> list[str]:
    constants = _split_audiveris_constants(config.audiveris_constants)
    constants = [c for c in constants if not _is_max_pixel_count_entry(c)]
    if not any(_is_implicit_tuplets_entry(c) for c in constants):
        constants.append(f"{_IMPLICIT_TUPLETS_QNAME}=true")
    pixel_count = _validated_max_pixel_count(config)
    if pixel_count:
        constants.append(f"{_MAX_PIXEL_COUNT_QNAME}={pixel_count}")
    return constants


def _is_max_pixel_count_entry(entry: str) -> bool:
    key = entry.split("=", 1)[0].strip().lower()
    return key == "maxpixelcount" or key.endswith(".maxpixelcount")


def _is_implicit_tuplets_entry(entry: str) -> bool:
    key = entry.split("=", 1)[0].strip().casefold()
    return key == _IMPLICIT_TUPLETS_QNAME.casefold()


def _split_extra_args(raw: str) -> list[str]:
    if not raw.strip():
        return []
    try:
        return shlex.split(raw)
    except ValueError as exc:
        raise ExternalToolError(
            "SCORE_TRANS_AUDIVERIS_EXTRA_ARGS 格式错误，请检查引号是否成对。"
        ) from exc


_VALID_HEAPS = {"1g", "2g", "3g", "4g"}


def _validated_max_heap(config: ToolConfig) -> str:
    heap = config.audiveris_max_heap.strip().lower()
    if heap not in _VALID_HEAPS:
        raise ExternalToolError(
            f"SCORE_TRANS_AUDIVERIS_MAX_HEAP 值无效：{config.audiveris_max_heap!r}。"
            f"可选值：{', '.join(sorted(_VALID_HEAPS))}。"
        )
    return heap


def _java_env(config: ToolConfig) -> dict[str, str] | None:
    if not config.java_home:
        return None
    java_home = Path(config.java_home)
    java_exe = java_home / "bin" / "java.exe"
    if not java_exe.exists():
        raise ExternalToolError(f"配置的 Java 路径无效：{java_home}")
    env = os.environ.copy()
    env["JAVA_HOME"] = str(java_home)
    env["PATH"] = str(java_home / "bin") + os.pathsep + env.get("PATH", "")
    # 使用捆绑的 Gradle 缓存（打包时由 build-app.py 预填充）
    bundled_gradle_home = PROJECT_ROOT / "third_party" / "gradle_home"
    if bundled_gradle_home.exists():
        env["GRADLE_USER_HOME"] = str(bundled_gradle_home)
    _apply_java_proxy_options(env)
    return env


def _apply_java_proxy_options(env: dict[str, str]) -> None:
    proxy_url = (
        env.get("https_proxy")
        or env.get("HTTPS_PROXY")
        or env.get("http_proxy")
        or env.get("HTTP_PROXY")
    )
    if not proxy_url:
        return

    parsed = urlparse(proxy_url if "://" in proxy_url else f"http://{proxy_url}")
    if not parsed.hostname or not parsed.port:
        return

    proxy_options = (
        f"-Dhttp.proxyHost={parsed.hostname} -Dhttp.proxyPort={parsed.port} "
        f"-Dhttps.proxyHost={parsed.hostname} -Dhttps.proxyPort={parsed.port}"
    )
    current = env.get("JAVA_TOOL_OPTIONS", "")
    if "-Dhttp.proxyHost" not in current and "-Dhttps.proxyHost" not in current:
        env["JAVA_TOOL_OPTIONS"] = f"{current} {proxy_options}".strip()
