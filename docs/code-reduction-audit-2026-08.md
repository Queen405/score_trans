# Score Trans 代码删减与重构调研报告

> 调研日期：2026-08-23
> 调研范围：后端 `backend/score_trans/` 全部 232 个 Python 源文件、约 25,001 行（不含 `__pycache__`）
> 调研目的：以删减代码、消除冗余、理顺分层为目标的详尽分析
> 调研方法：domain 层由子代理逐文件完整通读；其余各层通过 Grep 全仓引用验证、大文件函数骨架提取、架构核心文件精读、与 `docs/AUDIT_REPORT.md`/`issues.md`/`project-code-deletion-plan.md` 历史结论交叉复核
> 基线：以当前工作树为准，不预设历史报告状态，所有结论以本次实际 Grep/Read 证据为据

---

## 〇、总体结论

项目自 2026-07 系列审计以来已修复大量问题（见第一章）。当前剩余的可删减/可重构项集中在三类：

1. **domain 层死代码与门面空转**：一批 re-export 门面（`domain/__init__.py`、`parse/__init__.py`、`write/__init__.py`）和仅在测试中使用的门面函数，全仓零生产引用，可直接删除约 150-200 行。
2. **跨文件重复实现**：变音记号映射、A4 尺寸常量、`_tuplet_normal_notes`、`_utf16_length`、HTTP `chat_completions`、`persisted_*_settings` 等重复散落 3-5 处，可集中收敛。
3. **巨型文件与分层边界**：`renderer.py`(2206)、`parse/musicxml.py`(1434)、`parse/jianpu_text.py`(1404)、`exec/render/actions.py`(1166) 仍偏大；`domain/xml_utils.py` 执行文件 I/O 违反 domain 零 I/O 原则；`show_measure_numbers`/`measure_number_mode` 双向耦合未清理。

以下按"可立即删除 → 重复合并 → 巨型拆分 → 架构违规 → 持久化/健壮性"顺序详述。

---

## 一、已修复确认（相对于历史报告，无需再动）

本次复核确认以下历史问题**已修复**，列入此章以免重复劳动：

| 历史编号 | 结论 | 证据 |
|---|---|---|
| R5 | exec 层 `HTTPException` 导入已清零 | `grep HTTPException backend/score_trans/exec` → 0 处 |
| 3.1 | `models/` 违规 import `config` 已清零 | `grep "from score_trans.config\|from ..config" backend/score_trans/models` → 0 处；`dao/` 同样 0 处 |
| 3.4 | `config`↔`utils` 循环导入已解除 | `utils/env.py` 现仅 `from ..models.common.paths import CONFIG_DIR, PROJECT_ROOT`，不再 import config |
| 7.1 (AI provider 三重复制) | 已重构为 `services/ai/providers/_vision.py` 基类 | `grep transcribe_page` → 仅 `_vision.py`(基类) + `mock.py` 两处实现 |
| 5.5 (chat_dao 拒绝 system) | CHECK 约束已含 system | `dao/ai/chat_dao.py:107` `CHECK(role IN ('system','user','assistant'))` |
| 7.4 (renderer 死代码) | `_render_beat_items`/`_render_articulation`/`_upper_mark_anchor_y` 已删 | 全仓 grep → 0 处 |
| 删除计划第一批 | `build_request`/`send_request`/`_render_batch_a4_without_page_ocr`/`RenderAnchor`/`SEMITONE_TO_STEP` 已删 | 全仓 grep → 0 处 |
| 3.3 (异步路由同步调用) | 大量路由已用 `asyncio.to_thread` | `grep asyncio.to_thread` 在 api/ 下 30+ 处 |
| 环境变量规范 | `config/settings.py` 用 `os.environ[name]`(必填) + `os.getenv(name, default)`(选填)，模块全局读取 | `config/settings.py:11-59` |
| ocr/client 瘦身 | `ocr/client/client.py` 从 ~78 行瘦身到 27 行，仅剩 `ocr_prompt_for_model` | 已 Read 确认 |

---

## 二、可立即删除的死代码（P1，附 Grep 验证）

以下符号在全仓（`backend/score_trans` + `tests`）中**除定义处与 re-export 外零引用**，删除前仍建议运行一次全量测试与 `grep` 复核。

### 2.1 三个无人使用的 domain 包根 re-export 门面

`from .domain import` / `from ..domain import` 在全仓 **0 处**引用（所有调用方都直接导入 `domain.jianpu`、`domain.parse.jianpu_text` 等子模块）：

| 文件 | 行数 | 内容 | 证据 |
|---|---|---|---|
| `domain/__init__.py` | 25 | re-export `Beat/Event/JianpuBeat/.../TextBlock` | `grep "from .domain import\|from ..domain import\|from score_trans.domain import"` → 0 处 |
| `domain/parse/__init__.py` | 17 | re-export `JianpuOptions/ParsedToken/parse_jianpu/parse_jianpu_score/parse_jianpu_scores` | `grep "from .domain.parse import\|from ..domain.parse import"` → 0 处 |
| `domain/write/__init__.py` | 16 | re-export `score_to_jianpu_text/score_to_jianpu_document/scores_to_jianpu_text/scores_to_jianpu_document/score_to_musicxml/scores_to_musicxml` | `grep "from .domain.write import\|from ..domain.write import"` → 0 处 |

**动作**：删除这三个 `__init__.py` 的全部 re-export 内容（保留空 `__init__.py` 或改为只导出真正被外部消费的符号）。需同步检查 `__all__` 引用。

### 2.2 全仓零调用的孤立符号

| 文件:行号 | 符号 | Grep 证据 |
|---|---|---|
| `domain/constants.py:78` | `DEGREE_TO_MAJOR_OFFSET` | 全仓仅定义处 1 处 |
| `domain/jianpu_tokens.py:19` | `PREFIX_SLASHES` | 全仓仅定义处 1 处 |
| `domain/text_attachments.py:17` | `first_ocr_measure_number()` | 全仓仅定义处 1 处 |
| `domain/jianpu.py:71` | `jianpu_to_html()` | 全仓仅 `__all__` + 定义处，无调用 |
| `domain/write/musicxml.py:23` | `score_to_musicxml()` | 仅定义 + `write/__init__.py` re-export，无生产调用（生产用 `scores_to_musicxml`） |
| `domain/parse/musicxml.py:140` | `musicxml_path_to_score()` | 仅定义 + `domain/musicxml.py` re-export + `__all__`，无调用（生产用 `musicxml_path_to_scores`） |

### 2.3 仅测试使用、生产绕过的门面函数

这些函数有引用但**仅来自 `tests/`**，生产代码已绕过它们直接调用底层实现。若要保留为公开 API 需明确标注，否则可移入测试辅助或删除：

| 文件:行号 | 符号 | 生产引用 | 测试引用 |
|---|---|---|---|
| `domain/parse/jianpu_text.py:100` | `parse_jianpu()` | 0 | `tests/test_jianpu.py` 3 处 |
| `domain/parse/jianpu_text.py:51` | `ParsedToken` | 0 | 随 `parse_jianpu` |
| `domain/parse/musicxml.py:159` | `musicxml_to_score()` | 0 | `tests/test_convert.py`/`test_export.py`/`test_provenance.py` 多处 |
| `domain/jianpu.py:28-47` | `musicxml_file_to_jianpu()` / `musicxml_to_jianpu()` / `musicxml_to_jianpu_multi()` | 0（`exec/convert/actions.py` 直接用 `musicxml_path_to_scores` + `scores_to_jianpu_document` 绕过） | 仅 `tests/test_jianpu.py` |

> 注意 `api/convert/routes.py` 中的 `musicxml_to_jianpu` 是路由函数名，并非调用 domain 门面。

**动作**：确认这些门面是否作为公开 API 承诺。若否，删除门面并让测试直接调用底层 `parse_jianpu_score`/`musicxml_path_to_scores` 等。

---

## 三、重复实现与可合并模块（P2）

### 3.1 `_utf16_length` 与 `_utf16_offset` 等价重复

- `domain/parse/jianpu_text.py:516` `_utf16_length(text)` = `len(text.encode("utf-16-le")) // 2`
- `domain/write/jianpu_text.py:586` `_utf16_offset(text, offset)` = `len(text[:offset].encode("utf-16-le")) // 2`

后者等价于 `_utf16_length(text[:offset])`。**建议**：合并为单个 `_utf16_length(text)`，置于 `jianpu_tokens.py` 共享，`_utf16_offset` 改为调用它。这是 `project-code-deletion-plan.md` 第一批第 5 项的残余（曾有两份 `_utf16_length`，现已演变为 length/offset 两种形态，仍可合并）。

### 3.2 `_tuplet_normal_notes` 三份完全相同实现

同一函数体（`while normal_notes * 2 <= actual_notes: normal_notes *= 2; return max(1, normal_notes)`）出现在：

- `domain/parse/jianpu_text.py:991`
- `domain/write/jianpu_text.py:738`
- `domain/write/musicxml.py:694`

**建议**：移入 `jianpu_tokens.py`，三处统一导入。

### 3.3 变音记号 Fraction↔token 映射散落 5+ 处

| 位置 | 方向 | 备注 |
|---|---|---|
| `accidentals.py:105-119` `_accidental_text` | Fraction→str | 含四分音 |
| `accidentals.py:122-130` `_accidental_value` | str→Fraction | |
| `parse/musicxml.py:1410-1417` `_matching_accidental_text` | str→Fraction | **与 `_accidental_value` 完全等价** |
| `parse/musicxml.py:1424-1434` `_matching_accidental_text` | Fraction→str | **与 `_accidental_text` 完全等价** |
| `write/musicxml.py:638-648` `_musicxml_accidental_name` | Fraction→str | 几乎相同，仅 `Fraction(0,1)→"n"` 而非 `""` |
| `parse/jianpu_text.py:1183-1218` `_parse_pitch` 内联 | 硬编码 | 同一映射的内联展开 |

**建议**：在 `constants.py` 定义 `TOKEN_TO_ALTER`（含全量 bb/b/n/#/x + 微记号）和 `ALTER_TO_TOKEN`（反向），各文件统一引用。`constants.py` 已有 `MICROTONAL_TOKEN_TO_ALTER` 但未整合全量。

### 3.4 A4 页面尺寸 `1240`/`1754` 散落 5 文件 14 处

`grep "1240\|1754"` 确认：

| 文件 | 形式 |
|---|---|
| `domain/text_placement.py:15-16` | `_A4_WIDTH=1240.0` / `_A4_HEIGHT=1754.0` |
| `exec/pipeline/actions.py:342-343` | `page_width=1240` / `page_height=1754` 裸数字 |
| `exec/render/actions.py:720-721,749-750,1085,1110` | `1240`、`1754`、`1754-84` 裸数字 |
| `services/render/main.py:15-16` | `A4_PAGE_WIDTH=1240` / `A4_PAGE_HEIGHT=1754` |
| `services/render/engraving/style.py:10-11` | `page_width=1240.0` / `page_height=1754.0` |

**建议**：在不破坏分层的前提下（`models/render/schemas.py` 或新增公共常量模块），统一定义 A4 常量与安全边距（`exec/render/actions.py:1085` 的 `1754-84` 与 `text_placement.py` 的 `_SAFE_X=84.0`/`_SAFE_TOP=120.0`/`_SAFE_BOTTOM=84.0` 应关联）。此为 `project-code-deletion-plan.md` 第二批第 4 项，尚未执行。

### 3.5 `chat_completions` 在 AI 与 OCR 两个 `_http.py` 重复

- `services/ai/providers/_http.py:14` `chat_completions(...)` 含 `extra_body` 参数 + 流式 `chat_completion_chunks`
- `services/ocr/providers/_http.py:12` `chat_completions(...)` 是 AI 版**子集**（少 `extra_body`，无流式）

两者都直接 `httpx.post` 模块级调用，无连接池复用（N26 仍存在）。

**建议**：OCR 直接复用 AI 版 `chat_completions`（或提取到 `utils/openai_response.py` 旁的共享 http client），删除 OCR 版。同时引入由 composition/service 生命周期持有的 `httpx.Client` 以复用连接。

### 3.6 `persisted_ai_settings` 与 `persisted_ocr_settings` 完全相同

- `services/ai/core/prompts.py:72-78`
- `services/ocr/core/utils.py:31-37`

两者实现完全相同：`SettingsService().get_all()` 包在 `try/except Exception: return {}` 中。

**建议**：合并为单个 `persisted_settings()`（置于 `services/settings/` 或 `utils`），AI/OCR 共用。同时将 `except Exception: return {}` 改为记录日志后再返回空，避免静默吞错。

### 3.7 `first_present` 两处定义

- `utils/dict_tools.py:8` `first_present(raw: dict, keys: tuple)` — 字典版，OCR parser 使用
- `services/ai/transcription/merging.py:79` `first_present(values: list[str|None])` — 列表版，AI transcription 使用

签名不同但概念重复。**建议**：保留 utils 版作为通用工具，AI 版可改名为 `first_non_blank` 或就地内联（仅 3 行）。

### 3.8 小节归一化逻辑近乎完全重复

- `domain/parse/jianpu_text.py:1239-1260` `_normalize_parsed_measure`
- `domain/parse/musicxml.py:1059-1083` `_normalize_measure`

两者均：计算 `target = Fraction(beats*4, beat_type)` → `beat_duration = Fraction(4, beat_type)` → 创建 Beat 列表 → 按 `int(event.start / beat_duration)` 分配 → 处理少拍/超拍。唯一差异：前者记 `validation_errors`，后者插入生成休止符。**建议**：抽取共享函数，参数控制少拍行为。

### 3.9 滑行方向推断逻辑重复

- `domain/parse/jianpu_text.py:1339-1357` `_set_slide_direction`（含古筝验证）
- `domain/parse/musicxml.py:979-999` `_restore_slide_directions` + `_infer_slide_direction`（简化版）

核心逻辑相同（比较首末 pitch.rank 设置 up/down）。**建议**：提取到 `domain` 共享辅助。

### 3.10 `_indent` 重新实现标准库

`domain/xml_utils.py:35-45` `_indent()` 是 `xml.etree.ElementTree.indent()` 的手工实现。项目用 Python 3.13，标准库自 3.9 起提供 `ET.indent`（`services/recognize/external_tools.py:353` 已在用）。**建议**：删除 `_indent`，`write/musicxml.py:18` 改为直接 `ET.indent(root, space="  ")`。

### 3.11 `DIATONIC_STEPS` 跨层重复

- `domain/pitch_spelling.py:7` — `("C","D","E","F","G","A","B")`
- `services/correct/clef_transform.py:3` — 完全相同

**建议**：在 `pitch_spelling.py` 导出，`clef_transform.py` 导入；或移入 `constants.py`。

### 3.12 四个无意义 trivial 包装函数

| 包装函数 | 被包装函数 | 文件:行号 |
|---|---|---|
| `_consume_duration_prefix` | `consume_duration_prefix` | `parse/jianpu_text.py:1235` |
| `_duration_parts` | `safe_duration_affixes` | `write/jianpu_text.py:745` |
| `_mark_token` | `mark_token` | `write/jianpu_text.py:749` |
| `_pitch_to_token` | `pitch_to_token` | `write/jianpu_text.py:753` |

函数体仅 `return 被包装函数(*args)`，无附加逻辑。**建议**：直接调用原函数，删除包装。

---

## 四、巨型文件与拆分建议（P2）

### 4.1 `services/render/engraving/renderer.py`（2206 行，全项目最大）

60+ 个模块级函数 + 1 个 `PublicationRenderer` 类（4 方法）。函数划分相对细，但文件过大。按职责可拆分为：

| 拟拆分模块 | 函数 | 行数估算 |
|---|---|---|
| `layout.py`（布局/分页） | `_paginate`/`_break_systems`/`_best_break`/`_system_extra_height`/`_page_chrome`/`_normalize_parts`/`_assign_*_measure_numbers`/`_flatten_measures`/`_build_cells`/`_intrinsic_measure_width`/`_event_positions`/`_bounded_event_positions` | ~600 |
| `drawing.py`（绘制） | `_draw_system`/`_draw_measure`/`_draw_event`/`_draw_pitch`/`_draw_duration`/`_draw_marks`/`_draw_rhythm_*`/`_draw_barline`/`_draw_explicit_beam_level` | ~700 |
| `spanners.py`（延音线/圆滑线） | `_route_spanners`/`_start_spanner_continuations`/`_finish_spanners`/`_spanner`/`_spanner_layout`/`_span_attrs`/`_register_span_node`/`_draw_tuplets`/`_event_tuplet_spans` | ~300 |
| `text.py`（文本布局） | `_measure_text_layout`/`_draw_measure_text`/`_event_notation_top` | ~200 |
| `renderer.py`（核心入口） | `PublicationRenderer` + `render_scores`/`write_pages`/`_style_for_page` | ~400 |

最大的单个函数：`_draw_measure`(314-424, 110行)、`_draw_event`(1006-1115, 109行)、`_draw_system`(214-313, 99行)、`_event_positions`(861-957, 96行)。

### 4.2 `domain/parse/musicxml.py`（1434 行）

- `_read_measure_events`(444-653, 209行)：单函数处理 backup/forward/direction/note/chord/rest/tuplet/dynamics/lyric/provenance 所有事件类型。可按事件类型拆分为 dispatch + 各类型 handler。
- `_direction_text_blocks`(1117-1254, 137行)：words/rehearsal/dynamics/metronome/wedge/pedal/octave-shift 分支平铺，可改为数据驱动映射表 + 循环。

### 4.3 `domain/parse/jianpu_text.py`（1404 行）

- `parse_jianpu_score`(421-683, 262行)：含两个嵌套闭包 `flush_measure`(35行) 和 `append_event`(79行)，修改 10+ 个 nonlocal 变量。**建议**：提取为 `_MeasureBuilder` 类，将闭包变为方法，状态作为实例属性。

### 4.4 `exec/render/actions.py`（1166 行）

3 个 Action 类 + 大量模块级辅助。注意一组 OCR 文本处理函数（`_parse_ocr_text`(781)、`_serialize_ocr_text`(823)、`_parse_ocr_text_lenient`(1018)、`_merge_rendered_and_legacy_ocr_texts`(1025)、`_load_legacy_ocr_items`(1056)、`_manual_render_page_ocr_text`(1068)）—— 经 grep 验证**都有活跃调用者**，是历史 OCR 文本兼容代码，非死代码，但可考虑提取到独立 `ocr_text_compat.py` 模块以瘦身本文件。

另有 `_request_measure_number_mode`(1118)/`_show_measure_numbers`(1124)/`_request_show_measure_numbers`(1128) 三个 `show_measure_numbers`/`measure_number_mode` 双向耦合辅助（见 5.3）。

### 4.5 `dao/history/history_dao.py`（931 行）

- `_migrate_db`(581-697, 116行)：巨型迁移函数，含 `_clear_history_for_v5`(698) + `_drop_legacy_history_tables`(713)。
- 8 个 `_dump_*`/`_load_*` 序列化函数(827-918)：手写 JSON 序列化，可考虑用 `json` 模块 + dataclass 替代以减少手写编解码。
- `create_batch`(255-329)、`update_page`(395-484) 较大。

---

## 五、分层违规与架构问题（P2）

### 5.1 `domain/xml_utils.py` 执行文件 I/O — 违反 "domain 零 I/O"

AGENTS.md 明确："`domain/` 包含业务逻辑和域特定计算，**零 I/O**"。但：

- `domain/xml_utils.py:70-80` `_read_musicxml(path)` 直接打开文件 + `ZipFile`
- `domain/xml_utils.py:48-67` `_mxl_rootfile_name` 操作 `ZipFile`
- `domain/jianpu.py:29` `musicxml_file_to_jianpu` 调用 `_read_musicxml`
- `domain/jianpu.py:51` `jianpu_file_to_musicxml` 调用 `path.read_text(encoding="utf-8")`

**影响**：domain 层耦合文件系统与 Zip 解压，难以纯单元测试。

**建议**：将 `_read_musicxml`/`_mxl_rootfile_name` 移入 `services/` 或 `exec/` 层；domain 只接收已读取的 `xml_text: str`。`parse/musicxml.py` 的 `musicxml_path_to_scores` 改为接受 `str`，由调用方负责读取。

### 5.2 N25 仍存在：`correct/musicxml_patch.py` 全树遍历 O(k*n²)

`grep` 确认 `services/correct/musicxml_patch.py` 仍使用 `root.iter()` 全树遍历：

- `_matching_elements`(65) `for element in root.iter()`
- `_single_matching_element`(73) `for element in root.iter()`
- `_ancestor`(82-92) `for candidate in root.iter(tag)` + `element in candidate.iter()`
- `_parent`(93-99) `for candidate in root.iter()`
- `_delete_attribute_element`(176) `for candidate in target.iter()`

对每个删除 ID 重复全树搜索，最坏接近 O(k*n²)。

**建议**：单次解析后建立 `parent_map`（`{child: parent}`）和 locator 索引（按 entity ID 索引元素）。验收：结果等价测试 + 大型合成 MusicXML 基准，修复后随节点数近线性增长。

### 5.3 `show_measure_numbers` 与 `measure_number_mode` 双向耦合未清理

`project-code-deletion-plan.md` 第二批第 3 项，**尚未执行**。证据：

- `api/pipeline/routes.py:47-48`：Form 同时接受 `show_measure_numbers: bool` 和 `measure_number_mode: MeasureNumberMode`
- `api/pipeline/routes.py:60-61`：`show_measure_numbers=measure_number_mode != "none" and show_measure_numbers` + `measure_number_mode="none" if not show_measure_numbers else measure_number_mode` — 双向耦合，令人困惑
- `api/pipeline/routes.py:66-73`：`_request_measure_number_mode`/`_request_show_measure_numbers` 兼容函数
- `exec/render/actions.py:1118-1132`：`_request_measure_number_mode`/`_show_measure_numbers`/`_request_show_measure_numbers` 三个辅助

两者表达同一语义且存在冲突组合（`show=False, mode="all"` 与 `show=True, mode="none"` 都隐藏）。

**建议**：按删除计划执行——`measure_number_mode` 设为唯一字段（`none/all/row_start`），设置升级时一次性转换旧布尔值，删除 `show_measure_numbers` 的 DTO 字段/设置列/前端类型/兼容函数，重新生成 `openapi.ts`。

### 5.4 N26 仍存在：HTTP client 无连接复用

`services/ai/providers/_http.py:46` 和 `services/ocr/providers/_http.py:38` 均用模块级 `httpx.post`，每次请求新建连接，无法复用连接池/TLS。

**建议**：由 composition/service 生命周期持有同步 `httpx.Client`，明确关闭时机。多次请求复用连接，异常与流式关闭路径不泄漏。**不要**无理由改成 AsyncClient（见 `issues.md` N26 验收要求）。

### 5.5 异常 handler 的 stage 硬编码

`api/app.py:123-172`：每个异常 handler 硬编码 `stage`（`"audiveris"`/`"ocr"`/`"ai"`/`"render"`/`"validation"`/`"files"`/`"upload"`）。`ExternalToolError` 总标 `stage: "audiveris"`，若异常来自非 Audiveris 路径会误导。

**建议**：让异常携带 stage（或在异常类中存储），API 层透传，而非硬编码。

### 5.6 模块命名冲突：`pitch_spelling`

`domain/pitch_spelling.py`（模块：调号音阶转换）与 `domain/accidentals.py:58` 的 `pitch_spelling()` 函数同名但职责完全不同。**建议**：将 `accidentals.py` 的函数改名为 `resolve_accidental_display`。

### 5.7 `exec/notation`、`exec/syntax` 极薄层

| 文件 | 行数 |
|---|---|
| `exec/syntax/actions.py` | 30 |
| `exec/notation/actions.py` | 168 |
| `api/syntax/routes.py` | 19 |
| `api/notation/routes.py` | 20 |
| `services/syntax/validator.py` | 9 |

syntax 整条链路（exec 30 + api 19 + service 9 = 58 行）非常薄。这是职责分层而非死代码，但若未来不扩展，可评估是否将 syntax 的 exec 层内联到 api 路由（仅一个 `validate` 方法）。**不建议立即删**，列为观察项。

---

## 六、数据持久化与健壮性（P3）

### 6.1 `history_dao.py` 迁移与序列化

- `_migrate_db`(581-697, 116行)：ALTER TABLE 迁移需确认事务保护（历史报告称中途失败导致部分迁移状态）。
- 8 个 `_dump_*`/`_load_*`(827-918) 手写序列化：可改用 `json` + dataclass 减少编解码代码。
- 历史 N+1 查询（`list_batches` 对每个 batch 单独查询页面）需复核是否仍在。

### 6.2 SQLite 配置不一致

`SettingsDao` 缺 WAL/busy_timeout；`TaskDao` 已有 WAL 但缺 busy_timeout；`chat_dao` 历史报告缺 WAL/busy_timeout（需复核当前状态）。并发写入可能 `database is locked`。**建议**：统一所有 DAO 的 PRAGMA 配置。

### 6.3 静默吞错

- `services/ai/core/prompts.py:77` 和 `services/ocr/core/utils.py:36`：`except Exception: return {}` 静默吞错（见 3.6）。
- 历史报告的 `exec/pipeline/actions.py`、`exec/recognize/actions.py` 多处 `except Exception: return None` 需复核是否仍静默。

---

## 七、删减优先级与执行顺序

### 第一批：可直接删除（低风险，每批独立提交 + 全量测试）

1. 删除三个 domain 包根 re-export 门面（`domain/__init__.py`、`parse/__init__.py`、`write/__init__.py` 的 re-export 内容）—— 约 58 行
2. 删除孤立死符号：`DEGREE_TO_MAJOR_OFFSET`、`PREFIX_SLASHES`、`first_ocr_measure_number`、`jianpu_to_html`、`score_to_musicxml`、`musicxml_path_to_score` —— 约 60 行
3. 删除 `_indent`，改用 `ET.indent` —— 约 11 行
4. 删除 4 个 trivial 包装函数 —— 约 12 行
5. 评估并删除/移入测试辅助的仅测试门面（`parse_jianpu`/`ParsedToken`/`musicxml_to_score`/`musicxml_file_to_jianpu` 等）

每批删除后运行 `python -m pytest` + `grep` 复核已删符号零引用。

### 第二批：重复收敛（需小范围重构，独立提交）

6. 合并 `_utf16_length`/`_utf16_offset`
7. 合并三份 `_tuplet_normal_notes` → `jianpu_tokens.py`
8. 收敛变音记号映射到 `constants.py` 的 `TOKEN_TO_ALTER`/`ALTER_TO_TOKEN`
9. 合并 `persisted_ai_settings`/`persisted_ocr_settings`
10. OCR `_http.py` 复用 AI 版 `chat_completions`
11. 统一 A4 尺寸常量（配合第二批第 4 项）
12. 合并小节归一化与滑行方向推断

### 第三批：跨协议迁移（高收益但跨层，单独提交）

13. 执行 `show_measure_numbers` → `measure_number_mode` 协议迁移（删除计划第二批第 3 项）

### 第四批：架构整改（中风险，需测试护航）

14. `domain/xml_utils.py` 的文件 I/O 上移到 services/exec
15. N25：`correct/musicxml_patch.py` 建立 parent_map + locator 索引
16. N26：引入生命周期持有的 `httpx.Client` 连接复用
17. 异常 handler stage 改为异常携带

### 第五批：巨型文件拆分（维护性重构，非删代码优先）

18. `renderer.py` 按职责拆分（layout/drawing/spanners/text/renderer）
19. `parse_jianpu_score` 提取 `_MeasureBuilder` 类
20. `_read_measure_events`/`_direction_text_blocks` 数据驱动重构
21. `history_dao.py` 手写序列化改用 json + dataclass

---

## 八、不建议删除的项目

以下虽体积大或名称旧，但**有活跃消费者，不得删除**：

- `/render/jianpu-svg`、`/render/jianpu-text-svg`、`/render/batch-a4` 及其 Action/模型：`ConvertView.vue`、`RecognizeView.vue`、`usePublicationRender.ts` 实际调用。
- `ocr_prompt_for_model`：两个 OCR provider 仍复用（`dashscope.py:65`、`openai_compatible.py:92`）。
- `services/render/render_service.py`（PublicationRenderService 门面）：是 `main.py` 的薄门面，委托合理，非冗余。
- `exec/render/actions.py` 的 OCR 文本处理函数组（`_parse_ocr_text`/`_serialize_ocr_text`/`_merge_rendered_and_legacy_ocr_texts` 等）：经 grep 验证都有活跃调用者，是历史 OCR 文本兼容代码。
- 大型 Vue 视图（RecognizeView 2624 行、ConvertView 2603 行、SyntaxView 1236 行）：体积大不等于死代码，应先建组件级测试再按职责拆分，属维护性重构。
- `services/overlay/`（svg_generator/omr_parser/overlay_service）：结构合理，职责清晰。
- `domain/performance_marks.py`（743 行）：虽长但高度内聚（30+ 数据实例 + 查找函数），不建议拆分。

---

## 九、调研方法说明与局限

- **domain 层**：由 general 子代理逐文件完整通读，覆盖全部 16 个文件，分析最详尽。
- **其余各层**（services/render+overlay+correct、ai+ocr+recognize+export、基础设施 dao/config/utils、exec/api）：原计划由 4 个并行子代理详读，但因 RPM/配额限制 3 个失败，改由本人用 Grep 全仓引用验证 + 大文件函数骨架提取（`grep -nE "^(def|class) "`) + 架构核心文件精读（app.py/composition.py/dependencies.py/routes）+ 与历史报告交叉复核完成。因此 services/exec 的**函数级内部逻辑细节**不如 domain 层详尽，但所有"死代码/重复/分层违规"结论均有 Grep 证据支撑。
- 所有 Grep 验证均排除 `__pycache__`，覆盖 `backend/score_trans` + `tests`。
- 建议第二批重构前，对 services 各子模块再做一次子代理逐文件通读以补充函数级细节。

*报告结束。本次共复核 232 个后端 Python 源文件（25,001 行），识别可立即删除死代码约 130-200 行、重复实现 12 项、巨型文件 5 个、架构违规 5 项。*
