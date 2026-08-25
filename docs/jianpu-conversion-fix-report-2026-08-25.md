# MusicXML -> 简谱转换修复实施报告

实施日期：2026-08-25  
依据：`jianpu-conversion-fix-plan-2026-08-25.md` v3 及两份转换审计报告。

## 已实施

- MusicXML 单小节内按 exact `note@id` 去重；`multiple-rest` 保持为渲染指令，不展开。
- 显式还原号按当前调号计算领域 accidental，文本规范化为 `n`，MusicXML 导出保留 `natural`。
- 行首 `0.`-`7.` 按附点音符解释；冒号标签和大于 7 的点号标签继续剥离。
- 修复残留 tuplet span 遮蔽真实 start/stop，并用 `<type>` 校正未缩放的 time-modification 时值。
- chord 非首音上的 slur 合并到主事件；writer 只输出可闭合、非嵌套 slur。
- 跨 tuplet slur 使用 `($...$` / `$...$)`；parser、validator 和 UTF-16 anchor 同步支持。
- 带 accidental 的 tuplet 成员保留空格，避免 compact 形式的前后 accidental 歧义。
- 文本空小节保留为 generated+hidden whole rest；反复结束后的尾随 `|` 不产生伪空小节。
- MusicXML measure rest 统一为整小节时值；普通超长休止按当前小节剩余容量输出。
- `L:` 只收集 note 歌词，休止歌词不再导致后续歌词右移。
- writer 输出副本按 voice、start、原序分组；不修改调用方 score，不删除声部。
- 中途源调号变化记录 warning，目标简谱调保持请求值。
- 无 pitch note 降级为 rest；非标准力度从简谱输出中删除并记录 warning。
- 新增 `staccatissimo`、`turn`、`inverted-turn` token、MusicXML 映射和矢量渲染。
- 文档补充 `db7'` 词法、跨 tuplet slur 和新增奏法 token。

## 方案调整

以下 v3 建议未机械照搬，以免引入新的数据错误：

1. 不按“超拍”盲目截断 note。真实 XML 全部含多 voice，领域超拍常来自声部叠加；截断会删除合法音符。保留事件并记录现有 `validation_errors`。
2. 不把长休止余量写入后续 XML 小节。真实输入已经显式包含后续 measure，结转会重复；文本仅裁剪到当前小节容量。
3. 不把 writer 的附点上限从 3 强制降到 2。`15/64` 等小于一拍的时值无法用单 token、双附点和整拍 `-` 精确表示。保持精确时值，未来若增加多 token tie 表达再收紧上限。

## 真实数据门禁

对 `work/render` 的 10 个 XML/MXL 使用当前代码重新生成，未覆盖历史输出文件。结果：

- 10/10 `validate_jianpu_text()` 无诊断且可完整回解析。
- 10/10 XML measure 数等于简谱重解析 measure 数；28 个空小节位置全部保留。
- 10/10 全局 slur 栈平衡、无嵌套，`$...$` 内局部括号平衡。
- 10/10 XML -> 简谱 -> XML pitch multiset 完全一致，missing/extra 均为 0。
- 10/10 `normalize_jianpu_text()` 二次执行幂等。
- 无 `?`、无 `\molto` 等非法力度；最长休止延长串为 2 个 `-`。
- 10/10 新文本相对 2026-08-24 的历史 `_jianpu.txt` 有变化，符合修复预期。

## 验证

- 全量 pytest：775 passed，1 skipped。
- Ruff：通过。
- render/provenance/anchor：124 passed。
- performance mark render：88 passed。

## 明确范围外

方向文字、多段歌词、volta、bar-style、歌词 syllabic/extend、编号 slur 和 `@voice` 新语法仍按 v3 声明留作产品/语法扩展。本次没有迁移历史 render-map；旧转换结果需要重新生成。
