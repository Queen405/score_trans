# 中文标题预览消失修复

## 根因与真实输入

《海阔天空》截图对应的保存输出包含 `score-title`，内容是“简谱”。标题不是被顶部裁切：前端 `svgSanitizer.ts` 对全部属性统一限制为 4096 字符，两个中文字形的 SVG `d` 属性分别有 6771、6732 字符，因而都被移除。透明的辅助文本仍存在，不能只用 `aria-label` 或容器 `getBBox()` 判断标题可见。

该旧记录的简谱文本、MusicXML 均未包含曲名，OCR 文本和标题附件也为空。修复显示后原记录显示的是“简谱”；不会根据文件名猜测曲名。验证副本在第一个 `// @part` 标记下加入 `title=海阔天空`，没有改写用户数据库。

## 修改

- 仅为 `path.d` 提供 256 KiB 上限，同时继续校验路径命令；其他属性保留 4096 字符上限及原有安全检查。
- 批量请求区分显式标题与通用标题后备值。识别完成、最终重渲染、历史重建不再把“简谱”作为整份文档的强制标题。解析出的 `title=` 保留优先级；OCR 标题附件可以补足缺失的曲名；纯 MusicXML 输入保留文件自己的标题。
- 已作为原生标题绘制的同名 OCR 标题不再生成第二个叠加块，其他附件及请求中的源数据保留。
- 新增真实字体生成的中文标题 SVG 固定样本；Electron 测试核对清理前后每个字形的路径与实际墨迹边界，继续测试恶意 SVG 清理。

## 验证

- `tests/test_render.py` 与 `tests/test_architecture.py`：209 passed。
- `tests/test_text_attachments.py` 与 `tests/test_provenance.py`：27 passed。
- 前端工具测试：335 passed，1 skipped。
- Electron DOM/字形测试、类型检查、生产构建及修改文件 Ruff 检查通过。前端 lint 为 0 error、57 条既有 warning。
- 实际历史 SVG 经旧版和修复后的清理函数分别在 Chromium 中截图，确认标题由空白恢复。
- 同一首曲子的隔离副本经真实批量渲染入口输出 2 页，并经前端清理后查看截图，确认曲名、调拍号与首行没有遮挡。

复查产物位于 `work/title-visibility-review/`：`comparison-final.png` 为原保存输出的前后对比；`actual-score-with-title.png` 为补入明确曲名后的实际谱面；`request-with-title.json` 为隔离验证请求。显示修复会应用到已缓存的 SVG，无需改变原谱布局或重新识别音符。

## 后续：请求封装仍然覆盖标题（publication-36）

用户补入 `title=海阔天空` 后仍显示“简谱”。核对保存文本确认标题位于第一声部正文，解析位置正确。上面的首次修复漏掉了 `usePublicationRender.ts`：`withDefaultTitle` 在所有请求离开前重新补上顶层 `title: '简谱'`，后端按显式请求优先规则再次覆盖了曲名。

移除这层隐式覆盖，标题意图原样传入 API；本地化后备值继续由批量页面构建器处理。新增测试经过真实 Vue composable、请求门控、API 包装与 JSON 序列化，在网络边界检查未设置标题、null、空字符串和显式标题。这项测试在修复前准确失败，修复后通过。

同步提升前后端引擎标记为 `publication-36` 并重新生成 API 类型，使历史记录中的旧输出在恢复时重建。新增历史旧版本缓存重建测试。

再次读取用户已经保存的《海阔天空》原文，未添加或改写曲名，经真实前端构建器、请求封装、API 序列化，再提交实际 FastAPI `/render/batch-a4` 路由；两页标题均为“海阔天空”。通过实际预览清理函数在 Chromium 中截图并查看，4 个中文字形完整可见。产物位于 `work/title-transport-review/`，其中 `saved-score-correct-title.png` 为实际页面，`request-from-frontend.json` 为序列化后的请求。
