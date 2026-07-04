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

_MOVEMENT_STEM_PATTERN = re.compile(r"^(?P<base>.+)\.mvt(?P<number>\d+)$", re.I)


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
            f"外部程序执行失败：{' '.join(args)}\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
        ) from exc
    return CommandResult(args=args, stdout=completed.stdout, stderr=completed.stderr)


def recognize_with_audiveris(
    input_file: Path, output_dir: Path, config: ToolConfig
) -> Path:
    input_file = input_file.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

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
