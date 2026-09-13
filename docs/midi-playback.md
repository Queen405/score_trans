# MIDI 播放与原谱定位

MIDI 使用已展开反复的演奏时间轴。SVG 的 `data-playback-tick` 和音符组仍属于未展开的原谱时间轴。音频调度、时长、进度条与拖动使用演奏时间；谱面高亮和翻页使用映射后的原谱时间。

`domain/playback_timeline.py` 统一生成总谱小节演奏序列和原谱音符组。各 part 共享反复顺序；同一反复结束处的显式次数发生冲突时拒绝导出。普通反复默认两遍，孤立结束记号从曲首反复；本协议不新增一二房或 D.C./D.S. 解释。

## 第一轨 marker 协议

前缀为 `score-trans-playback:`，其后为 JSON。marker 的 MIDI 绝对 tick 是演奏位置，所有 tick 采用文件头 PPQ。

| kind | 字段 | 含义 |
| --- | --- | --- |
| document | version=1, source_kind, text_hash | tick 0；来源为 text 或 score。文本来源附原始 UTF-8 文本的 SHA-256，否则 hash 为 null |
| measure | score_tick, end_tick, source_index | 每次进入小节；原谱起点、本次演奏区间终点、原谱小节索引 |
| onset | score_tick, score_group, ranges | 每个发声音符组；原谱起拍、原谱组号、全部同拍音符的文本范围 |

区间为 `[marker.tick, end_tick)`。当前位置由 `score_tick + performanceTick - marker.tick` 得到；发声音符的原谱 onset 单独根据其演奏 onset 查表，不能用当前小节偏移转换上一个音符。

`ranges` 元素为 `{start, end}`，使用提交文本中的 UTF-16 偏移。part 内事件的局部坐标只在导出定位表时加上 part 起点和 BOM 长度，不改变原事件坐标。MusicXML 来源没有可靠的文本范围，列表为空。

## 前端行为

- `midiSourceMap.ts` 验证第一轨 marker，并按小节区间二分定位。
- `usePlayer` 保持音频时间独立，只向界面输出原谱位置。休止时清除音符高亮，仍可定位页面。
- 编辑器按文本指纹验证后使用后端范围，不重新计算反复或复调音符组。
- 修改文本立即卸载旧播放，防抖后重生成；加载代次和取消信号阻止旧请求覆盖新状态。
- 旧 MIDI 缺少定位且源谱可用时重生成。无法可靠定位的 MIDI 仍可播放，但关闭高亮和自动翻页。

回归入口：`tests/test_repeat_playback.py`、`desktop/scripts/test-midi-source-map.mjs`。后者通过项目 `.venv` 生成 MIDI，并经实际 `@tonejs/midi` 解析器验证跨语言协议；播放器行为测试模拟音频 Transport，不等同于实机试听。
