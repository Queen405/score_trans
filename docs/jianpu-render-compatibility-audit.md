# 简谱 SVG 渲染兼容代码审查报告

审查日期：2026-07-18  
范围：`backend/score_trans/services/render/`、其后端调用方和 `tests/test_render.py`。  
目标：停止兼容重构前 SVG 渲染器，只保留 `engraving.PublicationRenderer`（`publication-2`）作为唯一实现。

实施状态（2026-07-19）：本报告中“可删除项”列出的 23 个无消费者配置字段、未使用主题对象、三个字符串列表包装函数和多声部别名已删除；其余“新引擎问题”仍待单独修复。

## 结论

旧渲染器的 Python 源码已经在提交 `15e21b6` 删除：`drawing/`、`items/`、`layout/`、`parsing/`、`svg/`、`utils/`、`render_map.py` 和 `constants.py` 均不再有 `.py` 源文件。当前 `engraving/renderer.py` 没有导入这些模块，因此不存在两套 SVG 引擎同时运行的兼容路径。

仍应继续清理的是旧引擎留下的“公开门面形状”：无效配置项、只做转发的旧函数名，以及已删除模块遗留的本地 `.pyc`。这些不改变当前出版引擎的渲染结果，但会让调用方误以为旧参数和旧入口仍受支持。

## 可删除项

### P1：`RenderOptions` 中没有消费者的旧布局参数

文件：[options.py](../backend/score_trans/services/render/options.py) 第 26-67 行定义了 33 个字段；当前唯一的映射函数 [main.py](../backend/score_trans/services/render/main.py) 第 338-358 行只消费 `title`、`width`、`margin`、`font_family`、`min_measure_width`、`note_min_gap`、`note_font_size`、`accidental_font_size`、`lyric_font_size` 和小节号选项。

以下字段在 `backend/`、`tests/` 和桌面端源码中均没有读取点，可以删除：

- `measure_width`、`line_height`、`max_measure_width`、`beat_gap`、`staff_space`
- `short_note_gap_ratio`、`short_note_slot_width_ratio`、`tuplet_gap_ratio`、`tuplet_slot_width_ratio`、`duration_spacing_ratio`
- `chord_gap`、`chord_token_width`
- `measure_number_font_size`、`measure_attribute_font_size`、`repeat_count_font_size`、`tuplet_font_size`
- `dynamic_font_size`、`ornament_font_size`、`technical_font_size`、`technique_font_size`
- `compact_measure_layout`、`show_beat_guides`、`show_staff_guides`

这 23 个字段属于旧的可调布局契约；新引擎将对应值固定在 `PublicationStyle` 与 `renderer.py` 中。删除前只需确认没有仓库外 Python 调用方以关键字传入它们；桌面端和当前 API 均未暴露它们。

### P1：未使用的主题对象

[options.py](../backend/score_trans/services/render/options.py) 第 8-23 行的 `A4RenderTheme` 与 `A4_RENDER_THEME` 没有任何消费者，也没有参与 `PublicationStyle` 的构造。可整段删除。

### P1：仅由测试覆盖的旧别名入口

[main.py](../backend/score_trans/services/render/main.py) 第 120-141 行的 `render_jianpu_a4_svgs`、`render_score_a4_svgs`、`render_scores_a4_svgs` 只是从 `RenderedA4Page` 取出 `svg` 字符串。生产调用方一律需要页面范围和 render-map，走 `PublicationRenderService` 的文件/页面结果接口；其中只有 `render_jianpu_a4_svgs` 被测试使用。

建议删掉这三个函数，并把第 442 行的测试改为 `render_scores_a4_pages(...)[0].svg`。若需要保留纯内存 API，只保留 `render_scores_a4_pages` 一个结构化入口。

### P2：只为旧命名保留的多声部别名

[main.py](../backend/score_trans/services/render/main.py) 第 162-168 行的 `render_multi_part_scores_a4_pages` 与 `render_scores_a4_pages` 完全等价，生产代码没有引用，仅 `tests/test_render.py` 第 384 行使用。删除别名并改测试即可；多声部能力已经由 `PublicationRenderer._normalize_parts` 自动判断，不需要独立入口。

### P2：工作区中的旧字节码

`services/render/` 下仍能看到已删除目录对应的 `__pycache__/*.pyc`，包括 `drawing`、`items`、`layout`、`parsing`、`svg`、`utils` 和 `render_map`。它们不受 Git 跟踪且正常导入不会使用，但会混淆代码搜索与本地调试。清理整个 `backend/score_trans/services/render/**/__pycache__/` 即可；不要把 `.pyc` 作为源码兼容层保留。

## 新引擎问题

### P1：跨系统、跨页的连音线续接状态丢失

[renderer.py](../backend/score_trans/services/render/engraving/renderer.py) 第 213 行为每个 system 新建 `_OpenSpanners`；第 272-274 行只在当前 system 的右边界画出终止片段。下一个 system 又从空状态开始，所以若 tie/slur/slide 在换行或换页后才停止，左半段不会被画出，直到停止事件时也不会连回前一行。

应将每个声部的 `_OpenSpanners` 状态提升到 `render_scores()` 的页面/system 循环之外，并在新 system 的左边界绘制 continuation start；跨页同理。新增回归测试时，强制第二小节 `new_system=True` 和 `new_page=True`，分别断言两侧 continuation 均出现，而不只是 SVG 中存在任意一个 `class="tie"`。

### P2：小节号的两个开关可产生互相矛盾的配置

[main.py](../backend/score_trans/services/render/main.py) 第 68-71 行把 `show_measure_numbers` 和 `measure_number_mode` 原样传入；[renderer.py](../backend/score_trans/services/render/engraving/renderer.py) 第 249-252 行同时判断二者。于是 `show_measure_numbers=False, measure_number_mode="all"` 与 `show_measure_numbers=True, measure_number_mode="none"` 都会隐藏小节号，语义不唯一。

保留 `measure_number_mode` 作为唯一来源（`none`/`all`/`row_start`），在边界层一次性转换旧布尔值；随后删除 `show_measure_numbers`。这也会减少 8 个包装函数中的重复默认值逻辑。

### P2：`RenderOptions` 对 A4 页的 `margin` 名不副实

[main.py](../backend/score_trans/services/render/main.py) 第 347-352 行仅在 `page_width != A4_PAGE_WIDTH` 时应用 `options.margin`。因此最常用 A4 路径忽略该参数，而自定义宽度路径同时改变左右边距。这是不可预测的公开配置行为；应删除该旧参数，或无条件映射并补充测试。

### P3：渲染映射不覆盖派生记号

[renderer.py](../backend/score_trans/services/render/engraving/renderer.py) 第 824 行仅为事件主体注册 `BBox`；节奏线、连音线、延音线、连音组括号和多数演奏记号只是 SVG 节点，不进入 `PublicationScene.source_boxes`。编辑器若依据 `.render-map.json` 高亮或命中这些记号，会只命中音符主体或完全没有锚点。应明确 render-map 的契约：若目标是“音符定位”，在文档中声明；若目标是“全部可编辑元素定位”，则为派生节点注册 source role 与几何范围。

## 测试情况与建议删除顺序

`.venv/Scripts/python.exe -m pytest tests/test_render.py` 已通过，26 项全部通过。系统 Python 的同一命令因缺少 `mido` 在测试收集阶段失败，不能代表渲染回归。

建议按以下顺序执行：

1. 先为跨 system/page spanner 和小节号模式互斥关系添加测试，修复 P1。
2. 删除 23 个无消费者字段、`A4RenderTheme`、三个字符串列表包装函数和多声部别名；运行 `tests/test_render.py` 与 `tests/test_architecture.py`。
3. 清理 `__pycache__`，并用 `git grep` 确认不存在对已删旧模块的 import。
4. 最后决定 render-map 是否需要覆盖派生记号；这会影响桌面端点击/高亮行为，应与前端交互契约一起验收。
