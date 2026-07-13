# 五线谱标记删除/还原功能设计文档

> **项目**: Score Trans
> **目标**: 用户可在左侧五线谱图片上删除 OMR 误识别的标记（如错误的低音谱号、拍号），系统自动修正 MusicXML 并重新解析简谱，同时支持撤销还原。原有"重置简谱"按钮更名为"重置"，一键还原简谱和五线谱标记到刚识别完的状态。
> **日期**: 2026-07-08

---

## 目录

1. [功能概述](#1-功能概述)
2. [用户场景](#2-用户场景)
3. [核心架构](#3-核心架构)
4. [数据流](#4-数据流)
5. [后端实现](#5-后端实现)
6. [谱号音高转换算法](#6-谱号音高转换算法)
7. [前端实现](#7-前端实现)
8. [数据持久化与迁移](#8-数据持久化与迁移)
9. [文件清单](#9-文件清单)
10. [实施阶段](#10-实施阶段)
11. [风险矩阵](#11-风险矩阵)
12. [测试计划](#12-测试计划)

---

## 1. 功能概述

### 1.1 问题

Audiveris OMR 识别偶尔出现级联错误：一个标记（如低音谱号）识别错误后，后续所有音符的音高都基于错误的谱号推导，导致整段简谱作废。当前系统无法局部修正，只能整体重新识别。

### 1.2 解决方案

在 ConvertView（工作台）左侧五线谱图片上增加**标记编辑模式**：

- 用户点击误识别的标记（谱号、音符、拍号等）将其删除
- 系统从工作副本 MusicXML 中移除对应元素，重新解析简谱
- 删除谱号时自动转换后续音符的音高（从错误谱号 → 默认高音谱号）
- 用户可随时撤销删除，系统从原始副本 MusicXML 还原
- 原"重置简谱"按钮更名为"重置"，点击后同时还原简谱文本和五线谱上所有标记到刚识别完的状态

### 1.3 设计原则

- **双 XML 副本**：识别后保存原始 MusicXML（不可变）和工作副本 MusicXML（可编辑）
- **纯 MusicXML 操作**：不重新运行 OMR，不修改 .omr 文件，不需要修改 Audiveris Java
- **即时反馈**：补丁 + 重解析耗时 < 1 秒
- **逐标记撤销**：撤销某个标记的删除时，从原始 XML 重新应用所有剩余删除
- **一键全量重置**：现有"重置简谱"按钮更名为"重置"，清空所有标记删除 + 从原始 XML 重新解析简谱，回到刚识别完的状态

---

## 2. 用户场景

### 场景 1：删除错误的低音谱号

```
1. 用户在工作台看到五线谱图片，发现开头被误识别为低音谱号
2. 点击"编辑标记"按钮进入编辑模式
3. 所有识别到的标记以彩色方框显示（谱号=蓝色，音符=绿色，临时记号=紫色）
4. 点击错误的低音谱号方框 → 方框变红 + 显示删除标记
5. 点击"应用修正" → 系统从 MusicXML 删除谱号 + 自动转换后续音符音高 → 简谱刷新
6. 如果效果正确，继续其他操作
7. 如果效果不对，点击工具栏"重置"按钮 → 清空所有删除 + 从原始 XML 重新解析 → 简谱和标记全部还原
```

### 场景 2：删除多余的音符

```
1. 某个音符被错误识别（如多了一个装饰音）
2. 进入编辑模式，点击该音符方框
3. 应用修正 → MusicXML 中该音符变为等时值的休止符 → 简谱中该音符消失
```

### 场景 3：删除错误的拍号

```
1. 拍号被错误识别为 3/4（实际应为 4/4）
2. 删除错误的拍号标记
3. 应用修正 → MusicXML 中删除 <time> 元素 → 后续小节沿用前一个拍号
```

### 场景 4：一键重置到识别初始状态

```
1. 用户删除了多个标记并应用修正后，发现整体效果不理想
2. 点击工具栏"重置"按钮（原"重置简谱"按钮更名）
3. 系统：
   a. 清空所有已删除标记（deletedEntityIds 清空）
   b. 工作副本 MusicXML 从原始副本还原
   c. 从原始 MusicXML 重新解析简谱
   d. 退出编辑模式
4. 五线谱图片上所有标记恢复显示，简谱回到刚识别完的状态
```

---

## 3. 核心架构

### 3.1 双副本机制

```
识别完成
  │
  ▼
MusicXML 文本
  ├── original_musicxml (不可变备份，存入历史)
  └── working_musicxml  (可编辑副本，存入历史)
```

工作副本始终可通过以下方式重建：

```python
working_musicxml = patch(original_musicxml, current_deletions)
```

其中 `current_deletions` 是当前已删除的 `source_id` 列表。撤销操作 = 从列表移除 + 重新补丁。

### 3.2 标记类型与处理策略

| 标记类型 | .omr tag | MusicXML 元素 | 删除处理 |
|---|---|---|---|
| 谱号 | `clef` | `<clef>` in `<attributes>` | 删除元素 + **音高转换** |
| 拍号 | `time-whole` / `time-custom` | `<time>` in `<attributes>` | 删除元素 |
| 调号 | `key` | `<key>` in `<attributes>` | 删除元素 |
| 音符 | `head` | `<note>` with `<pitch>` | 替换为等时值休止符 |
| 休止符 | `rest` | `<note>` with `<rest>` | 删除元素 + 补 `<forward>` |
| 临时记号 | `alter` | `<accidental>` 子元素 | 删除 `<accidental>` |
| 其他 | `stem`, `beam`, `slur`, ... | 通过 provenance 定位 | 尽力删除关联元素 |

### 3.3 标记-MusicXML 映射来源

标记到 MusicXML 元素的映射依赖两个数据源：

**数据源 A — `score-link-map.json`（侧边栏文件）**

由 Audiveris 自定义 Java 导出器 `ScoreTransOverlayExporter.java` 生成。包含 13 类"可点击语义"元素（音符、临时记号、连音、装饰音等），每个元素携带 `musicxml_locator`，可用于在 MusicXML 中定位对应元素。

```json
{
  "source_id": "s0:i42",
  "inter_id": 42,
  "shape": "QUARTER_NOTE",
  "bounds": {"x": 100, "y": 200, "width": 30, "height": 40},
  "hit_path": "M100 200 L130 200 L130 240 L100 240 Z",
  "musicxml_locator": {"attribute": "id", "contains": "n-s0-i42"}
}
```

**数据源 B — `.omr` 文件（ZIP 归档）**

由 `OmrParser` 解析，包含所有 inters（包括谱号、拍号、调号——这些被侧边栏排除）。提供 `bounds`（像素坐标）和 `tag`（类型），但不提供 `musicxml_locator`。

```python
@dataclass(slots=True)
class InterData:
    id: str          # "236"（per-sheet 整数）
    tag: str         # "clef", "head", "time-whole", ...
    shape: str       # "G_CLEF", "F_CLEF", "SHARP", ...
    grade: float     # 置信度
    bounds: tuple[int, int, int, int]  # (x, y, w, h)
```

**合并策略**：`.omr` 提供完整标记列表（所有类型），`score-link-map.json` 补充 `musicxml_locator` 和 `hit_path`。通过 `inter_id` 匹配。

### 3.4 已验证的技术约束

| 约束 | 详情 | 影响 |
|---|---|---|
| XML 库 | 项目使用 `xml.etree.ElementTree`，无 lxml | 需手动遍历查找元素（无 `contains()` XPath），手动维护父节点引用 |
| Provenance 编码 | note `id` = `st__n-s0-i42__a-s0-i43__...` | 可通过正则 `r"(?:^\_\_)(?P<role>[a-z]+)\d*-s(?P<sheet>\d+)-i(?P<inter>\d+)"` 解析 |
| 谱号排除 | `score-link-map.json` 不含谱号/拍号/调号 | 结构标记需直接从 MusicXML `<attributes>` 定位 |
| 连音定位器不匹配 | 侧边栏用 `s-s0-i50`，note id 用 `ss-s0-i50` | 连音删除暂不支持（MVP 范围外） |
| 和弦结构 | chord 第一个 `<note>` 持有 `<duration>`/`<type>` | 删除 chord 首音符时需迁移时值到休止符 |
| 多声部 `<backup>` | 删除音符可能影响声部光标 | 单声部优先，多声部场景尽力处理 |
| 渲染性能 | 纯 Python SVG 引擎，数十毫秒 | 重解析后即时刷新 |
| .omr 持久化 | `audiveris_save` 默认关闭 | 需开启才能获取实体数据 |
| 多页 PDF | `OriginalPreview` 仅消费 `sheets[0]` | MVP 限制为单页/单图 |
| CI 类型检查 | `pnpm check:api-types` 检测 OpenAPI 类型漂移 | 后端 schema 变更后必须运行 `pnpm generate:api-types` |

---

## 4. 数据流

### 4.1 识别阶段（已有流程 + 新增持久化）

```
[用户上传图片] → POST /pipeline
  │
  ▼
Audiveris OMR → MusicXML
  │
  ├── uploads.register(musicxml) → musicxml_file_id
  ├── uploads.register(.omr)    → omr_file_id          ★ 新增
  ├── uploads.register(overlay PNG) → overlay_file_id
  └── uploads.register(score-link-map.json) → source_map_file_id
  │
  ▼
读取 MusicXML 文本
  ├── original_musicxml = musicxml_text                 ★ 新增
  └── working_musicxml  = musicxml_text                 ★ 新增
  │
  ▼
转换 → 简谱文本 + SVG 页面
  │
  ▼
POST /history (持久化)
  musicxml_file_id, original_musicxml, working_musicxml, ★ 新增
  omr_file_id, overlay_file_id, source_map_file_id,      ★ 新增
  jianpu_text, svg_file_ids, text_anchors, ...
```

### 4.2 标记删除阶段

```
[用户进入编辑模式]
  │
  ▼
GET /correct/entities?omr_file_id=...&source_map_file_id=...
  │
  ▼
后端合并 .omr inters + score-link-map elements → 统一实体列表
  │
  ▼
前端渲染所有实体方框
  │
  ▼
[用户点击标记删除] → deleted_source_ids.add(entity.source_id)
  │
  ▼
[用户点击"应用修正"]
  │
  ▼
POST /correct/apply
  {
    original_musicxml: "...",
    deleted_source_ids: ["s0:i236", "s0:i42"],
    source_map_file_id: "...",
    conversion_options: { target_key, accidental_mode, ... }
  }
  │
  ▼
后端补丁流程:
  1. working = original_musicxml 的深拷贝
  2. 对每个 deleted_source_id:
     ├── 查找对应 MusicXML 元素
     ├── 执行删除（休止符替换 / 谱号删除+音高转换 / ...）
     └── 修改 working XML 树
  3. musicxml_to_scores(working) → JianpuScore[]
  4. scores_to_jianpu_document → jianpu_text + text_anchors
  5. render_scores_a4_svg_pages → SVG 页面
  │
  ▼
返回 { working_musicxml, jianpu_text, text_anchors, svg_file_ids, ... }
  │
  ▼
前端更新显示
```

### 4.3 撤销阶段

```
[用户点击某标记的"还原"]
  │
  ▼
deleted_source_ids.remove(entity.source_id)
  │
  ▼
重新 POST /correct/apply（用更新后的 deleted_source_ids）
  │
  ▼
后端从 original_musicxml 重新补丁 → 新的 working_musicxml + 简谱
```

每次应用都是从原始 XML 重新补丁，保证幂等性和一致性。

### 4.4 一键重置阶段

```
[用户点击工具栏"重置"按钮（原"重置简谱"）]
  │
  ▼
前端执行 resetAll():
  1. deletedEntityIds.clear()              — 清空所有标记删除
  2. working_musicxml = original_musicxml  — 工作副本还原为原始
  3. editMode = false                      — 退出编辑模式
  4. 从原始 MusicXML 重新解析简谱
  │
  ▼
调用现有 musicxmlToJianpu 流程
（使用 store.musicxmlFileId — 指向识别时存储的原始 MusicXML 文件）
  │
  ▼
更新简谱文本 + SVG + text_anchors
  │
  ▼
五线谱上所有标记恢复显示，简谱回到刚识别完的状态
```

> "重置"按钮复用现有 `musicxmlToJianpu()` 的转换逻辑，只需额外清空 `deletedEntityIds` 并退出编辑模式。
> `musicxmlFileId` 指向识别时上传的原始 MusicXML 文件（始终不变），因此重新解析即可获得初始简谱。

---

## 5. 后端实现

### 5.1 MusicXML 双副本持久化

在历史页面模型中新增两个字段：

**`backend/score_trans/models/history/schemas.py`**

```python
class PageCreate(BaseModel):
    # ... 已有字段 ...
    omr_file_id: str = ""              # ★ 新增：.omr 文件 ID
    original_musicxml: str = ""        # ★ 新增：原始 XML 文本
    working_musicxml: str = ""         # ★ 新增：工作副本 XML 文本

class PageUpdate(BaseModel):
    # ... 已有字段 ...
    omr_file_id: str | None = None
    original_musicxml: str | None = None
    working_musicxml: str | None = None

class PageResponse(BaseModel):
    # ... 已有字段 ...
    omr_file_id: str = ""
    original_musicxml: str = ""
    working_musicxml: str = ""
```

同样更新 `models/history/entities.py` 的 `HistoryPage` dataclass。

### 5.2 .omr 持久化

**`backend/score_trans/exec/recognize/actions.py`** — `recognize_from_path` 方法

在 Audiveris 运行后，查找并注册 `.omr` 文件：

```python
def recognize_from_path(self, input_path, *, progress_callback=None):
    # ... 已有代码：运行 Audiveris，注册 MusicXML ...

    # ★ 新增：注册 .omr 文件
    omr_files = list(omr_dir.rglob("*.omr"))
    omr_file_id = self.uploads.register(omr_files[0]) if omr_files else None

    # ★ 新增：读取 MusicXML 文本
    musicxml_text = Path(musicxml_path).read_text(encoding="utf-8")

    return RecognizeResponse(
        musicxml_file_id=musicxml_id,
        musicxml_filename=musicxml_path.name,
        musicxml_text=musicxml_text,        # ★ 新增
        omr_file_id=omr_file_id,             # ★ 新增
        overlay_file_id=...,
        source_map_file_id=...,
        overlay_svg_file_id=...,
    )
```

同样修改 `exec/pipeline/actions.py` 的 `FullPipelineAction.execute` 和 `PipelineResponse`。

**前置条件**：需确保 `config.audiveris_save` 为 `True`（`-save` 标志），否则 `.omr` 不存在。在 `models/settings/config.py` 中将默认值改为 `True`，或在识别流程中强制启用。

### 5.3 实体提取服务

**新文件：`backend/score_trans/services/correct/entity_service.py`**

```python
from __future__ import annotations

from pathlib import Path

from ...models.common.paths import ...
from ...models.provenance.schemas import SourceMap
from ..overlay.omr_parser import OmrParser, InterData, SheetModel

# 结构标记 tag → 是否需要音高转换
STRUCTURAL_TAGS: frozenset[str] = frozenset({
    "clef",
    "time-whole",
    "time-custom",
    "key",
})

# 可删除标记 tag（排除 beam-group, head-chord 等容器）
DELETABLE_TAGS: frozenset[str] = frozenset({
    "clef", "time-whole", "time-custom", "key",
    "head", "rest", "alter",
    "augmentation-dot", "stem", "beam", "beam-hook", "flag",
    "slur", "articulation", "tuplet", "bow",
})


@dataclass(slots=True)
class CorrectableEntity:
    """统一的可纠正标记实体"""
    source_id: str           # "s0:i236"
    inter_id: str            # "236"
    sheet_index: int         # 0
    tag: str                 # "clef"
    shape: str               # "G_CLEF"
    grade: float             # 0.615
    bounds: tuple[int, int, int, int]  # (x, y, w, h)
    is_structural: bool      # True for clef/time/key
    musicxml_locator: str | None  # from score-link-map (e.g. "n-s0-i42")
    hit_path: str | None     # from score-link-map (SVG path geometry)


def extract_entities(
    omr_path: str | Path,
    source_map: SourceMap | None,
) -> list[list[CorrectableEntity]]:
    """
    合并 .omr inters 和 score-link-map，返回每页的实体列表。

    Returns: list[sheet_entities]，每个 sheet 是 CorrectableEntity 列表。
    """
    sheets = OmrParser().parse(omr_path)

    # 构建 inter_id → source_map_element 的查找表
    locator_map: dict[str, str] = {}   # inter_id → musicxml_locator.contains
    hit_path_map: dict[str, str] = {}  # inter_id → hit_path
    if source_map:
        for sheet in source_map.sheets:
            for elem in sheet.elements:
                locator_map[str(elem.inter_id)] = elem.musicxml_locator.contains
                hit_path_map[str(elem.inter_id)] = elem.hit_path

    result: list[list[CorrectableEntity]] = []
    for sheet in sheets:
        entities: list[CorrectableEntity] = []
        for inter in sheet.inters:
            if inter.tag not in DELETABLE_TAGS:
                continue
            inter_id_str = inter.id
            source_id = f"s{sheet.index}:i{inter_id_str}"
            entities.append(CorrectableEntity(
                source_id=source_id,
                inter_id=inter_id_str,
                sheet_index=sheet.index,
                tag=inter.tag,
                shape=inter.shape,
                grade=inter.grade,
                bounds=inter.bounds,
                is_structural=inter.tag in STRUCTURAL_TAGS,
                musicxml_locator=locator_map.get(inter_id_str),
                hit_path=hit_path_map.get(inter_id_str),
            ))
        result.append(entities)
    return result
```

### 5.4 MusicXML 补丁服务

**新文件：`backend/score_trans/services/correct/musicxml_patch.py`**

```python
from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ...utils.safe_xml import safe_xml_fromstring
from .clef_transform import transform_clef_region

# Provenance 正则（与 domain/parse/musicxml.py:44 一致）
_PROVENANCE_RE = re.compile(
    r"(?:^|__)(?P<role>[a-z]+)\d*-s(?P<sheet>\d+)-i(?P<inter>\d+)"
)


def apply_deletions(
    original_musicxml: str,
    deleted_source_ids: list[str],
    source_map_json: str | None = None,
) -> str:
    """
    对原始 MusicXML 应用删除操作，返回补丁后的 XML 文本。

    Args:
        original_musicxml: 不可变的原始 MusicXML 文本
        deleted_source_ids: 要删除的 source_id 列表（格式 "s0:i236"）
        source_map_json: score-link-map.json 内容（用于 musicxml_locator 查找）

    Returns:
        补丁后的 MusicXML 文本
    """
    root = safe_xml_fromstring(
        original_musicxml.encode("utf-8"),
        allow_musicxml_doctype=True,
    )
    ns = _detect_namespace(root)

    # 将 source_ids 按类型分类
    deletions = _classify_deletions(deleted_source_ids, source_map_json)

    # 1. 处理谱号删除（需音高转换）
    for source_id in deletions.clef_ids:
        _delete_clef_with_pitch_transform(root, ns, source_id)

    # 2. 处理拍号删除
    for source_id in deletions.time_ids:
        _delete_attribute_element(root, ns, source_id, "time")

    # 3. 处理调号删除
    for source_id in deletions.key_ids:
        _delete_attribute_element(root, ns, source_id, "key")

    # 4. 处理音符删除（替换为休止符）
    for source_id in deletions.note_ids:
        _replace_note_with_rest(root, ns, source_id)

    # 5. 处理临时记号删除
    for source_id in deletions.accidental_ids:
        _remove_accidental(root, ns, source_id)

    return _serialize(root)


def _classify_deletions(source_ids, source_map_json):
    """将 source_ids 按标记类型分类"""
    # 解析 source_map_json，查找每个 source_id 的 shape/tag
    # 结构标记（clef/time/key）不在 source_map 中，
    # 需要通过 .omr 的 tag 信息确定类型
    # ...
    pass


def _replace_note_with_rest(root, ns, source_id):
    """
    将 source_id 对应的 <note> 替换为等时值休止符。

    策略：保留 <duration>、<type>、<voice>、<staff>，
    移除 <pitch>、<accidental>、<beam>、<notations>，
    添加 <rest/>。

    和弦处理：如果删除的是 chord 的非首音符，直接删除该 <note>。
    """
    # 1. 通过 provenance 正则查找 note
    # 2. 检测是否为 chord 成员
    # 3. 替换或删除
    pass


def _delete_clef_with_pitch_transform(root, ns, source_id):
    """
    删除谱号并转换后续音符音高。

    1. 在 <attributes> 中找到 <clef> 元素
    2. 记录谱号信息（sign, line）
    3. 删除 <clef> 元素
    4. 从该小节到下一个谱号变更之间，转换所有音符音高
    """
    pass
```

### 5.5 API 端点

**新文件：`backend/score_trans/api/correct/routes.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends

from ...exec.correct.actions import CorrectActions
from ...models.correct.schemas import (
    EntitiesResponse,
    CorrectionRequest,
    CorrectionResponse,
)
from ..dependencies import get_correct_actions

router = APIRouter(prefix="/correct", tags=["correct"])


@router.get("/entities", response_model=EntitiesResponse)
async def get_entities(
    omr_file_id: str,
    source_map_file_id: str | None = None,
    actions: CorrectActions = Depends(get_correct_actions),
):
    """获取所有可纠正标记实体"""
    return await actions.get_entities(omr_file_id, source_map_file_id)


@router.post("/apply", response_model=CorrectionResponse)
async def apply_corrections(
    req: CorrectionRequest,
    actions: CorrectActions = Depends(get_correct_actions),
):
    """
    应用标记删除并返回修正后的结果。

    同步操作（<1 秒），不需要异步任务。
    """
    return await actions.apply_corrections(req)
```

**新文件：`backend/score_trans/models/correct/schemas.py`**

```python
from __future__ import annotations

from pydantic import BaseModel


class CorrectableEntityDTO(BaseModel):
    source_id: str
    inter_id: str
    sheet_index: int
    tag: str
    shape: str
    grade: float
    bounds_x: float
    bounds_y: float
    bounds_w: float
    bounds_h: float
    is_structural: bool
    musicxml_locator: str | None = None
    hit_path: str | None = None


class SheetEntitiesDTO(BaseModel):
    sheet_index: int
    width: int
    height: int
    entities: list[CorrectableEntityDTO]


class EntitiesResponse(BaseModel):
    sheets: list[SheetEntitiesDTO]


class ConversionOptionsDTO(BaseModel):
    target_key: str = "C"
    accidental_mode: str = "auto"
    instrument_profile: str = "general"
    start_measure_number: int | None = None
    show_measure_numbers: bool = True
    measure_number_mode: str = "all"
    title: str | None = None


class CorrectionRequest(BaseModel):
    original_musicxml: str
    deleted_source_ids: list[str]
    source_map_file_id: str | None = None
    options: ConversionOptionsDTO = ConversionOptionsDTO()


class CorrectionResponse(BaseModel):
    working_musicxml: str
    jianpu_text: str
    text_anchors: list[dict]
    text_hash: str
    svg_file_ids: list[str]
```

**`backend/score_trans/exec/correct/actions.py`**

> **架构注意**：`exec/` 层不允许直接导入 `domain/`。现有代码中 `exec/convert/actions.py`、`exec/pipeline/actions.py` 等已有此违规（列于 `test_architecture.py` 的 `KNOWN_LAYER_VIOLATIONS`）。`exec/correct/actions.py` 如需调用 `musicxml_path_to_scores` 等 domain 函数，有两种方案：
> - **方案 A（推荐）**：将转换逻辑封装在 `services/correct/` 中（services 层允许导入 domain），`exec/correct/actions.py` 调用 service
> - **方案 B**：直接在 `exec/correct/actions.py` 导入 domain，并在 `KNOWN_LAYER_VIOLATIONS` 中添加 `("exec/correct/actions.py", "domain")`（与现有 convert/pipeline/render 保持一致）

以下代码示例采用方案 B：

```python
class CorrectActions:
    def __init__(self, uploads, render_service):
        self.uploads = uploads
        self.render_service = render_service

    async def get_entities(self, omr_file_id, source_map_file_id):
        omr_path = self.uploads.get_path(omr_file_id)
        source_map = _load_source_map(source_map_file_id) if source_map_file_id else None
        sheets = extract_entities(omr_path, source_map)
        return _to_response(sheets)

    async def apply_corrections(self, req: CorrectionRequest) -> CorrectionResponse:
        # 1. 补丁 MusicXML
        source_map_json = _read_source_map(req.source_map_file_id)
        working_xml = apply_deletions(
            req.original_musicxml,
            req.deleted_source_ids,
            source_map_json,
        )

        # 2. 写入临时文件
        tmp_path = _write_temp_musicxml(working_xml)

        # 3. 转换为简谱
        scores = musicxml_path_to_scores(tmp_path, ...)
        document = scores_to_jianpu_document(scores, ...)

        # 4. 渲染 SVG
        svg_pages = self.render_service.render_scores_a4_svg_pages(scores, ...)

        # 5. 注册 SVG 文件
        svg_file_ids = [self.uploads.register(p) for p in svg_pages]

        return CorrectionResponse(
            working_musicxml=working_xml,
            jianpu_text=document.text,
            text_anchors=[a.model_dump() for a in document.anchors],
            text_hash=document.text_hash,
            svg_file_ids=svg_file_ids,
        )
```

### 5.6 依赖注入

**`backend/score_trans/api/app.py`** — 注册路由：

```python
from .correct.routes import router as correct_router
# ...
app.include_router(correct_router, prefix="/api")
```

**`backend/score_trans/api/dependencies.py`** — 添加工厂函数：

```python
def get_correct_actions() -> CorrectActions:
    return CorrectActions(
        uploads=shared_uploads(),
        render_service=shared_render_service(),
    )
```

---

## 6. 谱号音高转换算法

### 6.1 问题

MusicXML 存储的是**绝对音高**（`<step>F</step><octave>3</octave>`），不是五线谱位置。Audiveris 在 OMR 过程中已经根据谱号计算好了音高。删除谱号不会改变音符的音高值——需要手动转换。

### 6.2 原理

同一五线谱位置在不同谱号下对应不同音高。转换公式：

```
1. 计算音符在旧谱号下的五线谱位置（staff position）
2. 用新高音谱号（默认）重新计算该位置的音高
```

### 6.3 五线谱位置系统

```
Position 0 = 第一线（底线）
Position 1 = 第一间
Position 2 = 第二线
...
Position 8 = 第五线（顶线）
```

每种谱号的底线对应音符：

| 谱号 | MusicXML | 底线音符 | 底线 diatonic 值 |
|---|---|---|---|
| 高音谱号 G (line 2) | `<sign>G</sign><line>2</line>` | E4 | 30 |
| 低音谱号 F (line 4) | `<sign>F</sign><line>4</line>` | G2 | 18 |
| 中音谱号 C (line 3) | `<sign>C</sign><line>3</line>` | F3 | 24 |
| 次中音谱号 C (line 4) | `<sign>C</sign><line>4</line>` | D3 | 22 |

> diatonic 值 = `octave * 7 + step_index`，其中 C=0, D=1, E=2, F=3, G=4, A=5, B=6

### 6.4 转换公式

```python
DIATONIC_STEPS = ("C", "D", "E", "F", "G", "A", "B")

def _diatonic_value(step: str, octave: int) -> int:
    """计算音符的 diatonic 绝对值"""
    return octave * 7 + DIATONIC_STEPS.index(step.upper())

def _from_diatonic(value: int) -> tuple[str, int]:
    """从 diatonic 值还原 (step, octave)"""
    return DIATONIC_STEPS[value % 7], value // 7


def compute_clef_bottom_diatonic(sign: str, line: int) -> int:
    """
    计算谱号底线音符的 diatonic 值。

    Args:
        sign: "G", "F", "C"
        line: 1-5（谱号所在线）

    Returns: 底线音符的 diatonic 值
    """
    # 谱号参考音符的 octave 和 step
    clef_ref = {"G": ("G", 4), "F": ("F", 3), "C": ("C", 4)}[sign]
    clef_diatonic = _diatonic_value(clef_ref[0], clef_ref[1])
    # 底线位置 = 谱号线位置 - 2*(line-1) 个 diatonic step
    bottom_position = 2 * (line - 1)  # 谱号线在 staff 上的位置
    return clef_diatonic - bottom_position


def transform_pitch(
    step: str,
    alter: float,  # 保留不变
    octave: int,
    old_sign: str,
    old_line: int,
    new_sign: str = "G",
    new_line: int = 2,
) -> tuple[str, float, int]:
    """
    将音符从旧谱号转换到新谱号。

    Returns: (new_step, alter, new_octave)
    """
    old_bottom = compute_clef_bottom_diatonic(old_sign, old_line)
    new_bottom = compute_clef_bottom_diatonic(new_sign, new_line)

    # 音符的 diatonic 值
    note_diatonic = _diatonic_value(step, octave)

    # 计算五线谱位置
    staff_position = note_diatonic - old_bottom

    # 计算新音高
    new_diatonic = new_bottom + staff_position
    new_step, new_octave = _from_diatonic(new_diatonic)

    return new_step, alter, new_octave
```

### 6.5 验证

低音谱号底线 G2 → 高音谱号应为 E4：

```python
old_bottom = compute_clef_bottom_diatonic("F", 4)  # = 18 (G2)
new_bottom = compute_clef_bottom_diatonic("G", 2)  # = 30 (E4)
staff_position = _diatonic_value("G", 2) - 18       # = 18 - 18 = 0
new_diatonic = 30 + 0                               # = 30 = E4 ✓
```

低音谱号第四线 F3 → 高音谱号应为 D5：

```python
staff_position = _diatonic_value("F", 3) - 18       # = 24 - 18 = 6
new_diatonic = 30 + 6                               # = 36 = D5 ✓
```

> `alter`（升降号）保持不变：G#2 → E#4，Bb2 → G#4（因为 alter 是相对于自然音的偏移，不随谱号变化）

### 6.6 谱号删除时的音高转换流程

```python
def _delete_clef_with_pitch_transform(root, ns, source_id):
    """
    1. 在 MusicXML 中定位要删除的 <clef> 元素
    2. 记录其 sign 和 line
    3. 删除 <clef> 元素
    4. 遍历后续小节直到遇到下一个 <clef>：
       对每个 <note><pitch>，应用 transform_pitch()
    """
    # 遍历所有 <part> → <measure>
    # 在 <attributes> 中查找 <clef>
    # 根据谱号的 source_id / position 匹配
    # ...
```

谱号定位策略（因谱号不在 score-link-map 中）：

1. 解析 .omr 中谱号的 `bounds`（像素坐标）
2. 在 MusicXML 中遍历所有 `<clef>` 元素
3. 通过小节序号 ↔ 水平位置的近似匹配来确定哪个 `<clef>` 对应被删除的标记
4. 或：对初始谱号（第一个 `<attributes>` 中的 `<clef>`），直接按出现顺序匹配

### 6.7 8va/8vb 谱号变体

如果旧谱号是 `G_CLEF_8VA` 或 `F_CLEF_8VB`，转换时需额外 ±7 diatonic step（一个八度）。MusicXML 中表示为：

```xml
<clef>
  <sign>G</sign>
  <line>2</line>
  <clef-octave-change>1</clef-octave-change>   <!-- 8va -->
</clef>
```

---

## 7. 前端实现

### 7.1 OriginalPreview.vue 改造

**文件：`desktop/src/renderer/src/components/OriginalPreview.vue`**

新增 props：

```typescript
defineProps<{
  // ... 已有 props ...
  editable?: boolean                     // ★ 编辑模式开关
  entities?: CorrectableEntityDTO[]      // ★ 所有可纠正标记
  deletedEntityIds?: Set<string>         // ★ 已删除的 source_id 集合
}>()

defineEmits<{
  selectSource: [sourceId: string]
  toggleDelete: [sourceId: string]       // ★ 切换删除状态
}>()
```

新增 SVG 图层（位于 `.zp-inner` 内，`.source-hit-layer` 之后）：

```vue
<!-- ★ 新增：编辑模式实体图层 -->
<svg
  v-if="editable && entitySheet"
  class="entity-edit-layer"
  :viewBox="`0 0 ${entitySheet.width} ${entitySheet.height}`"
  :width="imgW || entitySheet.width"
  :height="imgH || entitySheet.height"
>
  <rect
    v-for="entity in entities"
    :key="entity.source_id"
    :x="entity.bounds_x"
    :y="entity.bounds_y"
    :width="entity.bounds_w"
    :height="entity.bounds_h"
    :class="[
      'entity-box',
      entity.tag,                           // clef / head / alter / ...
      { deleted: deletedEntityIds?.has(entity.source_id) },
    ]"
    @click.stop="$emit('toggleDelete', entity.source_id)"
  />
</svg>
```

CSS：

```css
.entity-edit-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
  pointer-events: none;
}

.entity-box {
  fill: transparent;
  stroke-width: 2;
  stroke: #00aa44;            /* 默认绿色 */
  vector-effect: non-scaling-stroke;
  pointer-events: visiblePainted;
  cursor: pointer;
  transition: fill 0.15s;
}

.entity-box.clef,
.entity-box.time-whole,
.entity-box.time-custom,
.entity-box.key {
  stroke: #0066ff;            /* 结构标记蓝色 */
}

.entity-box.alter {
  stroke: #cc00cc;            /* 临时记号紫色 */
}

.entity-box:hover {
  fill: rgba(0, 170, 68, 0.2);
}

.entity-box.deleted {
  stroke: #ff3333;
  fill: rgba(255, 51, 51, 0.3);
  stroke-dasharray: 6 4;
  /* 删除线效果 */
  position: relative;
}

/* 编辑模式下禁用 hit layer 的指针事件 */
.source-hit-layer.disabled {
  pointer-events: none;
}
```

### 7.2 编辑模式交互

**编辑模式开启时**：
1. `showOverlay` 自动设为 `true`（确保用户看到叠加层）
2. `.source-hit-layer` 添加 `disabled` class（禁用点击层指针事件）
3. `.entity-edit-layer` 可见且可交互

**编辑模式关闭时**：
1. `.entity-edit-layer` 隐藏
2. `.source-hit-layer` 恢复正常

### 7.3 ConvertView.vue 改造

**文件：`desktop/src/renderer/src/views/ConvertView.vue`**

在左侧面板头部（`.ws-left .ws-panel-head`，约 line 209-215）新增标记编辑控件：

```vue
<div class="ws-panel-head">
  <span class="ws-panel-title">原始五线谱</span>
  <span class="ws-panel-file">{{ store.originalFileName }}</span>

  <!-- ★ 新增：标记编辑控件 -->
  <div v-if="canEditMarkers" class="marker-edit-controls">
    <n-button
      size="tiny"
      :type="editMode ? 'primary' : 'default'"
      @click="toggleEditMode"
    >
      编辑标记
    </n-button>
    <template v-if="editMode">
      <span class="deleted-count">已删除 {{ deletedEntityIds.size }}</span>
      <n-button size="tiny" type="warning" :loading="applying" @click="applyCorrections">
        应用修正
      </n-button>
    </template>
  </div>
</div>
```

同时将主工具栏的"重置简谱"按钮更名为"重置"，并扩展其行为：

```vue
<!-- ★ 修改：ws-toolbar-right 中的按钮 -->
<n-button
  size="small"
  :loading="store.isBusy"
  :disabled="!store.hasMusicxml"
  type="primary"
  @click="resetAll"
>
  重置
</n-button>
```

> 注意：编辑工具栏中不再设置单独的"全部还原"按钮——主工具栏的"重置"按钮统一负责全量还原。

**`canEditMarkers`** 计算属性：需要 `omrFileId` 和 `originalMusicxml` 同时存在。

**`toggleEditMode`**：

```typescript
async function toggleEditMode() {
  editMode.value = !editMode.value
  if (editMode.value && correctableEntities.value.length === 0) {
    await loadEntities()
  }
}

async function loadEntities() {
  const { data, error } = await correctApi.getEntities(
    store.omrFileId,
    store.sourceMapFileId
  )
  if (error) { message.error(error); return }
  correctableEntities.value = data.sheets.flatMap(s => s.entities)
}
```

**`applyCorrections`**：

```typescript
async function applyCorrections() {
  applying.value = true
  try {
    const { data, error } = await correctApi.apply({
      original_musicxml: store.originalMusicxml,
      deleted_source_ids: [...deletedEntityIds.value],
      source_map_file_id: store.sourceMapFileId,
      options: { target_key: store.targetKey, /* ... */ },
    })
    if (error) { message.error(error); return }

    // 更新工作副本和显示（patch 键须用 camelCase 匹配 TaskPage 接口）
    await store.patchPageById(store.currentPage!.id, {
      workingMusicxml: data.working_musicxml,
      jianpuText: data.jianpu_text,
      textAnchors: data.text_anchors,
      textHash: data.text_hash,
      svgFileIds: data.svg_file_ids,
    })
    message.success('修正已应用')
  } finally {
    applying.value = false
  }
}
```

**`resetAll`**（替换原 `musicxmlToJianpu`）：

```typescript
async function resetAll(): Promise<void> {
  store.setBusy(true)
  try {
    // 1. 清空所有标记删除
    deletedEntityIds.value = new Set()

    // 2. 退出编辑模式
    editMode.value = false

    // 3. 从原始 MusicXML 重新解析简谱
    //    musicxmlFileId 始终指向识别时上传的原始 MusicXML 文件
    const result = await requireData(convertApi.musicxmlToJianpu({
      musicxml_file_id: store.musicxmlFileId,
      page_image_file_id: store.originalFileId || undefined,
      target_key: settings.targetKey,
      accidental_mode: settings.accidentalMode,
      start_measure_number: batchStartMeasureNumber.value ?? settings.startMeasureNumber ?? undefined,
    }))
    const split = splitJianpuAndOcr(result.jianpu_text)
    store.setJianpu(split.jianpuText)
    if (store.currentPage) {
      store.patchPageById(store.currentPage.id, {
        textAnchors: result.text_anchors ?? [],
        textHash: result.text_hash ?? '',
        // ★ 还原工作副本为原始
        workingMusicxml: store.originalMusicxml,
      })
    }
    store.setBatchJianpuText(composeJianpuPageText(store.currentBatchPages), false)
    store.setOcrText(split.ocrText || store.ocrText)
    store.setBatchRenderPageFileIds([])
    setFinalSvgFileIds([])
    log.addLog('已重置到识别初始状态')
    message.success('已重置')
  } catch (e: unknown) {
    const raw = e instanceof Error ? e.message : String(e)
    const msg = e instanceof ApiError ? handleMissingMusicxml(raw) : raw
    log.addError(`重置失败：${msg}`)
    message.error(msg)
  } finally {
    store.setBusy(false)
  }
}
```

> `resetAll` 在原 `musicxmlToJianpu` 基础上增加了三步：清空 `deletedEntityIds`、退出编辑模式、还原 `working_musicxml`。简谱解析逻辑完全复用现有代码。

### 7.4 Pinia Store 改造

**文件：`desktop/src/renderer/src/stores/workspace.ts`**

`TaskPage` interface 新增：

```typescript
export interface TaskPage {
  // ... 已有字段 ...
  omrFileId: string                    // ★ .omr 文件 ID
  originalMusicxml: string             // ★ 原始 XML 文本
  workingMusicxml: string             // ★ 工作副本 XML 文本
}
```

顶层 refs 新增：

```typescript
const omrFileId = ref('')
const originalMusicxml = ref('')
const workingMusicxml = ref('')
```

`syncCurrentFromPage` 中同步这些字段。

### 7.5 API 包装

**新文件：`desktop/src/renderer/src/api/correct.ts`**

```typescript
import { apiFetch } from './client'
import type { ApiResult } from './client'

const BASE = '/api/correct'

export const correctApi = {
  getEntities(
    omrFileId: string,
    sourceMapFileId?: string,
  ): Promise<ApiResult<EntitiesResponse>> {
    const params = new URLSearchParams({ omr_file_id: omrFileId })
    if (sourceMapFileId) params.set('source_map_file_id', sourceMapFileId)
    return apiFetch(`${BASE}/entities?${params}`)
  },

  apply(req: CorrectionRequest): Promise<ApiResult<CorrectionResponse>> {
    return apiFetch(`${BASE}/apply`, {
      method: 'POST',
      body: JSON.stringify(req),
    })
  },
}
```

---

## 8. 数据持久化与迁移

### 8.1 SQLite 迁移

**`backend/score_trans/dao/history/history_dao.py`**

1. `_SCHEMA_VERSION` 从 `2` 改为 `3`（当前版本已经是 2，包含 `engine_version`/`document_revision` 列）
2. `_create_tables` 中新增列：

```sql
ALTER TABLE history_page ADD COLUMN omr_file_id TEXT NOT NULL DEFAULT '';
ALTER TABLE history_page ADD COLUMN original_musicxml TEXT NOT NULL DEFAULT '';
ALTER TABLE history_page ADD COLUMN working_musicxml TEXT NOT NULL DEFAULT '';
```

3. `_migrate_db` 中添加幂等迁移逻辑（`if column not in columns` 守卫）
4. `_PAGE_FILE_ID_COLUMNS` 新增 `"omr_file_id"`（防止 GC 删除）
5. INSERT / UPDATE / `_row_to_page` 相应更新

### 8.2 OpenAPI 类型重新生成

后端 schema 变更后必须执行：

```bash
cd desktop
pnpm generate:api-types
```

否则 CI `check:api-types` 会失败。

### 8.3 向后兼容

- 旧历史页面没有 `omr_file_id` / `original_musicxml` → 默认空字符串
- `canEditMarkers` 计算属性检查这些字段是否非空 → 旧页面不显示编辑按钮
- `_row_to_page` 使用 `if "column" in row.keys() else ""` 模式（已有惯例）

---

## 9. 文件清单

### 9.1 新增文件

| 文件 | 用途 |
|---|---|
| `backend/score_trans/api/correct/__init__.py` | 模块初始化 |
| `backend/score_trans/api/correct/routes.py` | 2 个 API 端点 |
| `backend/score_trans/exec/correct/__init__.py` | 模块初始化 |
| `backend/score_trans/exec/correct/actions.py` | 纠正编排逻辑 |
| `backend/score_trans/services/correct/__init__.py` | 模块初始化 |
| `backend/score_trans/services/correct/entity_service.py` | 实体提取与合并 |
| `backend/score_trans/services/correct/musicxml_patch.py` | MusicXML 补丁 |
| `backend/score_trans/services/correct/clef_transform.py` | 谱号音高转换 |
| `backend/score_trans/models/correct/__init__.py` | 模块初始化 |
| `backend/score_trans/models/correct/schemas.py` | 请求/响应 DTO |
| `desktop/src/renderer/src/api/correct.ts` | 前端 API 包装 |
| `tests/test_correct.py` | 单元测试 |

### 9.2 修改文件

| 文件 | 变更 |
|---|---|
| `backend/score_trans/exec/recognize/actions.py:92` | 持久化 .omr + 读取 XML 文本 |
| `backend/score_trans/exec/pipeline/actions.py:64` | 同上 |
| `backend/score_trans/models/recognize/schemas.py:6` | 新增 `omr_file_id`, `musicxml_text` |
| `backend/score_trans/models/pipeline/schemas.py:26` | 同上 |
| `backend/score_trans/models/history/schemas.py` | `PageCreate`/`PageUpdate`/`PageResponse` 新增 3 字段 |
| `backend/score_trans/models/history/entities.py` | `HistoryPage` dataclass 新增 3 字段 |
| `backend/score_trans/dao/history/history_dao.py` | schema 迁移 + CRUD 更新 + GC 列表 |
| `backend/score_trans/api/app.py` | 注册 correct 路由 |
| `backend/score_trans/api/dependencies.py` | 注入 CorrectActions |
| `backend/score_trans/services/overlay/omr_parser.py` | 暴露 `DELETABLE_TAGS` 常量 |
| `tests/test_architecture.py` | 若采用方案 B，添加 `("exec/correct/actions.py", "domain")` 到 `KNOWN_LAYER_VIOLATIONS` |
| `desktop/src/renderer/src/components/OriginalPreview.vue` | 编辑模式 + 实体图层 |
| `desktop/src/renderer/src/views/ConvertView.vue` | 编辑工具栏 + 应用逻辑 + "重置"按钮更名与 `resetAll` |
| `desktop/src/renderer/src/stores/workspace.ts` | 新增状态字段 + 同步 |
| `desktop/src/renderer/src/models/openapi.ts` | 重新生成（`pnpm generate:api-types`） |
| `desktop/src/renderer/src/views/RecognizeView.vue:1318` | `persistPageResult` 传入新字段 |

---

## 10. 实施阶段

### 阶段 1：后端基础（可独立测试）

1. SQLite 迁移：新增 3 列 + 版本号升级
2. `.omr` 持久化：`recognize_from_path` 和 pipeline 中注册 .omr 文件
3. 读取 MusicXML 文本并存入 `original_musicxml` / `working_musicxml`
4. 更新所有 schema（recognize / pipeline / history）
5. 运行 `pnpm generate:api-types`

**验收**：识别后 `.omr` 文件存在于 uploads，history 页面有 XML 文本。

### 阶段 2：实体提取 + API

1. 实现 `entity_service.py`：合并 .omr + score-link-map
2. 实现 `correct/actions.py` 的 `get_entities` 方法
3. 注册 correct 路由
4. 测试 `GET /correct/entities` 返回正确实体列表

**验收**：API 返回所有标记（含谱号、拍号、音符），带 bounds 和类型。

### 阶段 3：MusicXML 补丁核心

1. 实现 `musicxml_patch.py`：音符→休止符替换（含和弦处理）
2. 实现 `clef_transform.py`：谱号音高转换算法
3. 实现谱号/拍号/调号删除
4. 实现 `correct/actions.py` 的 `apply_corrections` 方法
5. 测试 `POST /correct/apply` 各场景

**验收**：
- 删除音符 → 简谱中音符变为休止符
- 删除低音谱号 → 后续音符音高自动转换 → 简谱正确
- 删除拍号 → 后续小节沿用前拍号

### 阶段 4：前端编辑模式

1. `OriginalPreview.vue`：实体图层 + 编辑模式样式
2. `ConvertView.vue`：编辑工具栏 + 应用逻辑 + "重置简谱"→"重置"更名 + `resetAll` 实现
3. `workspace.ts`：新增状态 + 同步
4. `correct.ts`：API 包装

**验收**：
- 点击"编辑标记"→ 所有标记以彩色方框显示
- 点击方框 → 变红
- 点击"应用修正" → 简谱刷新
- 点击"重置" → 标记全部恢复 + 简谱回到识别初始状态 + 退出编辑模式

### 阶段 5：集成测试 + 完善

1. 端到端测试：识别 → 编辑 → 应用 → 重置
2. 边界情况：多声部、和弦、空小节
3. 性能测试：大谱面补丁 + 重解析耗时
4. 运行 `python -m pytest tests/test_render.py`（SVG 断言）
5. 运行 `.venv/Scripts/python.exe -m ruff check --fix backend/ tests/`

---

## 11. 风险矩阵

| 风险 | 严重度 | 概率 | 对策 |
|---|---|---|---|
| 谱号定位不准（不在 score-link-map 中） | 高 | 中 | 通过 .omr bounds + MusicXML 小节序号近似匹配；初始谱号按出现顺序匹配 |
| 和弦删除破坏小节时值 | 中 | 中 | 检测 `<chord/>` 标记，首音符替换为休止符保留时值 |
| 多声部 `<backup>` 场景异常 | 中 | 低 | MVP 单声部优先；多声部尽力处理 |
| 调号/拍号在 .omr 中不存在 | 中 | 低 | 取决于乐谱；不存在则不显示对应标记 |
| 旧页面无 omr_file_id | 低 | 高 | `canEditMarkers` 守卫，不显示编辑按钮 |
| GC 删除 .omr 文件 | 高 | 低 | `_PAGE_FILE_ID_COLUMNS` 必须包含 `omr_file_id` |
| CI 类型漂移 | 高 | 确定 | `pnpm generate:api-types` 纳入实施流程 |
| `audiveris_save` 关闭导致无 .omr | 高 | 中 | 默认开启或在识别流程中强制 |
| MusicXML DOCTYPE 丢失 | 低 | 确定 | `safe_xml_fromstring` 已处理，解析器兼容 |
| `xml.etree` 无 `getparent()` | 低 | 确定 | 手动遍历父节点列表进行删除 |

---

## 12. 测试计划

### 12.1 单元测试

**`tests/test_correct.py`**

```python
class TestClefTransform:
    """谱号音高转换测试"""

    def test_bass_clef_bottom_line_to_treble(self):
        """G2 (bass clef bottom line) → E4 (treble clef bottom line)"""
        step, alter, octave = transform_pitch("G", 0, 2, "F", 4, "G", 2)
        assert (step, octave) == ("E", 4)
        assert alter == 0

    def test_bass_clef_fourth_line_to_treble(self):
        """F3 (bass clef 4th line) → D5 (treble clef 4th line)"""
        step, alter, octave = transform_pitch("F", 0, 3, "F", 4, "G", 2)
        assert (step, octave) == ("D", 5)

    def test_alter_preserved(self):
        """升降号在转换后保留"""
        step, alter, octave = transform_pitch("G", 1, 2, "F", 4, "G", 2)
        assert alter == 1  # sharp preserved
        assert (step, octave) == ("E", 4)

    def test_alto_clef_to_treble(self):
        """中音谱号转换"""
        step, alter, octave = transform_pitch("F", 0, 3, "C", 3, "G", 2)
        assert (step, octave) == ("E", 4)


class TestMusicXmlPatch:
    """MusicXML 补丁测试"""

    def test_delete_note_replaced_by_rest(self):
        """删除音符后变为休止符"""
        xml = '<measure><note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration><type>quarter</type></note></measure>'
        result = apply_deletions(xml, ["s0:i1"], None)
        assert "<rest/>" in result
        assert "<duration>4</duration>" in result  # 时值保留

    def test_delete_clef_transforms_pitches(self):
        """删除低音谱号后音高转换"""
        xml = '''
        <measure number="1">
          <attributes><clef><sign>F</sign><line>4</line></clef></attributes>
          <note><pitch><step>G</step><octave>2</octave></pitch><duration>4</duration><type>whole</type></note>
        </measure>
        '''
        result = apply_deletions(xml, ["s0:i236"], None)
        assert "<clef>" not in result or "<sign>F</sign>" not in result
        assert "<step>E</step>" in result  # G2 → E4
        assert "<octave>4</octave>" in result

    def test_undo_restores_original(self):
        """撤销后恢复原始 XML"""
        original = "...原始 XML..."
        patched = apply_deletions(original, ["s0:i1"], None)
        re_patched = apply_deletions(original, [], None)  # 空删除列表
        assert re_patched == original  # 无删除 = 原始
```

### 12.2 集成测试

```python
class TestCorrectAPI:
    """API 端点集成测试"""

    async def test_get_entities_returns_all_types(self, client, uploaded_omr):
        """GET /correct/entities 返回所有类型标记"""
        resp = await client.get(f"/api/correct/entities?omr_file_id={uploaded_omr}")
        assert resp.status_code == 200
        data = resp.json()
        tags = {e["tag"] for e in data["sheets"][0]["entities"]}
        assert "head" in tags
        assert "clef" in tags  # 结构标记包含在内

    async def test_apply_corrections_returns_jianpu(self, client, musicxml_text):
        """POST /correct/apply 返回修正后的简谱"""
        resp = await client.post("/api/correct/apply", json={
            "original_musicxml": musicxml_text,
            "deleted_source_ids": ["s0:i1"],
            "options": {"target_key": "C"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "working_musicxml" in data
        assert "jianpu_text" in data
        assert len(data["svg_file_ids"]) > 0
```

### 12.3 回归测试

```bash
# 必须运行的测试
python -m pytest tests/test_render.py         # SVG 渲染断言
python -m pytest tests/test_architecture.py    # 架构规则（导入方向）
python -m pytest tests/test_correct.py         # 新增的补丁测试

# 代码质量
.venv/Scripts/python.exe -m ruff format backend/ tests/
.venv/Scripts/python.exe -m ruff check --fix backend/ tests/

# 前端
cd desktop && pnpm lint && npx vue-tsc --noEmit
```

---

## 附录 A：Audiveris 谱号音高公式参考

来源：`third_party/audiveris/app/src/main/java/org/audiveris/omr/sig/inter/ClefInter.java:144-161`

```java
private int absolutePitchOf(int intPitch) {
    return switch (shape) {
        case G_CLEF, G_CLEF_SMALL    -> 34 - intPitch;
        case G_CLEF_8VA               -> (34 + 7) - intPitch;
        case G_CLEF_8VB               -> (34 - 7) - intPitch;
        case C_CLEF                   -> (28 - (int) Math.rint(this.pitch)) - intPitch;
        case F_CLEF, F_CLEF_SMALL     -> (20 - (int) Math.rint(this.pitch)) - intPitch;
        case F_CLEF_8VA               -> (22 + 7) - intPitch;
        case F_CLEF_8VB               -> (22 - 7) - intPitch;
        case PERCUSSION_CLEF          -> 0;
        default -> 0;
    };
}
```

> 注意：Audiveris 的 `intPitch` 是 staff 内部的相对位置编号，与我们文档中的五线谱位置（0=底线）方向相反。本设计中使用更直观的位置系统，公式已重新推导。

## 附录 B：score-link-map.json 完整 Schema

来源：`backend/score_trans/models/provenance/schemas.py:20-40`

```python
class SourceMap(BaseModel):
    version: int = 1
    sheets: list[SourceMapSheet]

class SourceMapSheet(BaseModel):
    sheet_index: int
    width: int
    height: int
    overlay_file: str
    elements: list[SourceElement]

class SourceElement(BaseModel):
    source_id: str          # "s1:i236"
    inter_id: int           # 236
    shape: str              # "G_CLEF", "QUARTER_NOTE", ...
    grade: float            # 0.0-1.0
    bounds: BoundingBox     # {x, y, width, height}
    hit_path: str           # SVG path data
    musicxml_locator: MusicXmlLocator  # {attribute: "id", contains: "n-s1-i236"}
```

> 谱号、拍号、调号**不在**此文件中（被 `isClickableSemantic` 排除）。这些结构标记仅通过 .omr 获取。
