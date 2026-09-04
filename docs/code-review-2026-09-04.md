# 代码审查报告 — 多声部修复（F1+F4+F3+F2-A）

> 审查时间：2026-09-04
> 审查范围：工作区未提交改动（11 文件改 + 4 文件新增），对应 `docs/multi-part-fix-plan.md` 的 F1/F2-A/F3/F4
> 基线：Ruff 全绿；`pytest` 1007 passed, 1 skipped, 1 xfailed

---

## 总体评价：高质量，可合并

这批改动修复了四个 P0 级多声部缺陷，整体工程质量很高：

- **架构合规**：新异常放 `models/common/errors.py`，校验逻辑放 `domain/`，渲染入口调整放 `exec/`，符合分层依赖约束。
- **异常体系设计好**：`MultiVoiceNotSupportedError` 继承 `CodedValidationError`，API 层已有的统一 handler（`app.py:162`）会自动返回 `400 + error_code`，**无需在 API 层额外注册**。
- **守护测试专业**：`xfail(strict=True)` 机制保证"修好后强制删标记"，不会出现"修好了但标记还挂着"。
- **改名防误用**：`build_score → first_score` 并加文档警告，语义显式化。

---

## 需要处理的问题

> **处理决策（2026-09-04，用户拍板）**：P1 已处理完毕；P2/P3 均暂不修复，代码保持原样，待后续跟进。

### ✅ P1 — `exec/convert/actions.py:49` 的 `build_score` 是死代码且未按计划改名（已处理）

fix-plan F1 第 3 点明确要求把 `exec/convert/actions.py` 的 `build_score()` 改名为 `first_score()`，但实际**只改了 render 模块的，convert 模块的没动**。

更关键的是：在整个项目里 `grep '\.build_score\b'` **零调用方**（仅文档引用）——它已经是死代码。且它和 render 的一样返回 `scores[0]`，语义上同样丢弃多声部。

**处理结果**：已直接删除该方法（无人调用，删除最干净），并同步修正 `docs/architecture.md:73` 的过时引用（`build_score()` → `build_scores()`，该引用本身也描述错了 pipeline 实际走的路径）。删除后 Ruff 全绿、全量测试 1007 passed 不变。

### 🟡 P2 — `render_scores_svg` 高度估算公式 magic number 密集，且可能让正常谱子渲染失败【暂缓】

`services/render/main.py`：

```python
estimated_height = max(420.0, 270.0 + measure_count * 150.0 * part_count)
```

`270.0 / 150.0 / 420.0` 全是硬编码。当多声部 + 多小节导致实际内容超出估算高度时，后续 `if len(pages) != 1: raise RenderError(...)` 会**直接抛错**，而非降级处理——用户会看到"单页渲染空间不足"而不是谱面。

**建议**：把常量提为命名常量；给估算留更大余量；或采用"先渲染、页数超了就按比例放大高度重试一次"的兜底策略。

### 🟢 P2 — `clefs_by_staff` 在 staff 分谱里冗余复制【暂缓】

`_split_part_by_staff` 中 `staff_score.clefs_by_staff = dict(score.clefs_by_staff)` 把整个 part 的 clef 字典复制给每个 staff 分谱。但 staff 分谱已经有自己的 `clef_sign/clef_line`（已单独赋值），这个字典副本语义上冗余。

不影响正确性。若保留用于溯源，建议加一行注释说明用途；否则可只保留在 part 级。

### 🟢 P3 — 疑似 flaky test【暂缓】

第一次 `pytest tests/ -q` 进度条出现 1 个 `F`，第二次同样命令却是 1007 passed 全绿。可能存在依赖执行顺序或共享临时状态的 flaky 用例。

**建议**：跑 `pytest tests/ -p randomly` 多次复现，定位是哪个用例；CI 偶发飘红会很烦人。

### 🟢 P3 — 单声部输出 `@part` 的前端兼容性未验证【暂缓】

F4 让所有单声部导出都带上 `// @part 1 name="..."` 前缀（破坏性格式变更）。后端测试已更新，但**前端无对应测试改动**。`jianpuPlayback.ts`、`sourceAnchorSelection.ts`、`SyntaxView.vue` 都涉及 `@part` 解析。

**建议**：补一个前端单测验证"单声部带 @part"的解析路径（默认选中第一声部、锚点偏移、播放对齐等），避免上线后才发现前端解析异常。

---

## 做得好的地方（继续保持）

1. **异常继承复用**：新异常挂到已有 `CodedValidationError` 树下，API 层零改动即可友好响应——这是分层架构的红利。
2. **xfail(strict=True) 守护**：缺陷修复后 XPASS 强制删标记，流程闭环。
3. **谱号链路补全**：解析→存储→写出三段式补齐，F3 第一阶段达成。
4. **测试覆盖全面**：正向（声部数/名/音高/小节/时长不变）、反向（多 voice 报错）、边界（单 voice 不误报、报错信息含声部名与 error_code）均有覆盖。
5. **附带修复**：顺带修了 `render_score_page_file_to_svg` 缺 `initial_measure_number` 参数导致单声部调用崩溃的既存 bug。

---

## 结论

四个 P0 修复方向正确、实现扎实、测试到位，**可以合并**。

处理状态：P1（删死代码 + 更新架构文档）已处理；P2/P3 按用户决定暂不修复，保留原样，建议作为后续小任务跟进。
