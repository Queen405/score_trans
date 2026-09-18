# 单旋律属性实验验证（2026-09-18）

## 当前结论

已实现实验性 `--recognition-mode melody`：复用 v3 主体、局部上下文重新裁剪、附属点线候选、几何归属、疑难 VLM 复核、分数时值、局部变音状态、保守文本、melody.json 及哈希回放。默认仍是 bodies。

**本阶段质量验收未通过，不能作为完整简谱转写或播放入口。** 保留集的完整局部属性正确覆盖率为 67.80%，低于计划 85%；局部复核有增益也引入了八度错误。整页调号模型读数仍存在错误，现统一记为 observed，不作为已确认音高依据。

## 条件属性基准

人工从原图转写 6 张页面、299 个音符/休止符：开发集 181，保留集 118。页面级分割记录在 `tests/fixtures/melody/split.json`，真值为 `transcriptions.json`。图片来源、像素框和主体编号固定；模型响应没有参与真值生成。

保留页是 `image copy 7.png`、`image copy 9.png`。先冻结开发实现并完成开发集规则修正，再首次运行保留评测；保留结果没有用于调整几何阈值。保留页在测量前人工查看以制作真值，因此这不是第三方双盲评测。开发页包括 `image copy 4` 的独立旋律带，不能据此证明整页复调解析能力。

| 路径 | 音符数 | 完整属性被确认 | 完整属性正确 | 确认结果正确率 | 正确覆盖率 |
|---|---:|---:|---:|---:|---:|
| 开发集，本地 | 181 | 153 | 153 | 100% | 84.53% |
| 开发集，本地＋局部复核 | 181 | 154 | 153 | 99.35% | 84.53% |
| 保留集，本地 | 118 | 76 | 76 | 100% | 64.41% |
| 保留集，本地＋局部复核 | 118 | 82 | 80 | 97.56% | 67.80% |

“完整属性”在本表仅指给定人工主体下的八度、显式变音、减时线、附点、延长线及其计算时值均正确。不包含有效调号、声部时间关系、连线、整曲或绝对 MIDI 音高；**不能将表中 97.56% 当成完整音符端到端准确率**。

保留集加复核的逐属性结果：八度 82/85、显式变音 84/84、减时线 84/84、附点 84/84、延长线 84/84、时值 82/82（分母是该属性被确认的数量，不是全部 118）。有 3 个已确认八度属性错误，其中一个因超出支持八度范围没有生成完整音符。开发集亦出现一个高音被读成双高音，以及休止符附近墨迹被判断为降号；后者未生成完整音符。

开发阶段发现并修复：点状墨迹干扰行级尺度导致细减时线被丢弃；延长线距离上限导致长间隔的最后一条线被漏计。采用实测细连通域补充和同小节/下一主体边界限定，没有根据拍数修改音符。

局部复核共 30 请求：26 reviewed、2 invalid、2 failed。整页另外 72 请求：68 reviewed、2 failed、2 invalid。测试期间接口出现 429 限流和超时，因此在线结果包含真实失败，不是模型能力的纯净上限。冻结首轮原始响应保留失败，不重采样挑选结果。

## 整页接入试跑

复用已有 v3 在线主体，重新进行属性识别；未重复主体模型调用。

| 页面 | 进入属性计算的音符 | 完整属性被确认 | 局部复核请求 | 本次耗时 |
|---|---:|---:|---:|---:|
| image（梁祝） | 66 | 52 | 13 | 59.79 秒 |
| image copy 2（神话） | 198 | 166 | 13 | 88.44 秒 |
| image copy 10 | 216 | 118 | 46 | 281.69 秒 |

这些是处理数量，不是正确数量，不能以“52/66”当作端到端准确率。主体预览仍保留其他区域；完整小节状态更严格，有遗漏候选、多带或未解决墨迹时退回预览。

元数据：梁祝模型读到 Bb、4/4；神话因请求失败保持 unknown；image copy 10 把图中转调 C# 误读成 F#，还未正确报告变化。最终版本将所有整页读数降为 observed 并展示证据页，不参与确定的调号继承/拍数判断。三张的 melody_complete 均为 false。

## 产物和使用

```bash
source .venv/Scripts/activate
# 本地属性分析，复用 v3，不需要 API 配置
python -m trans_jp \
  --input 'third_party/trans-jp/examples/image.png' \
  --output-dir 'screenshots/trans-jp-melody/local-new/image' \
  --recognition-mode melody \
  --body-responses-dir 'screenshots/trans-jp-coordinate-v3/online/image/rows' \
  --no-melody-review --debug

# 需要局部复核时配置 TRANS_JP_* 并移除 --no-melody-review。
# 对已完成的 melody 输出指定其 rows 即可校验并冻结回放，无需联网：
python -m trans_jp \
  --input 'third_party/trans-jp/examples/image.png' \
  --output-dir 'screenshots/trans-jp-melody/replay-again/image' \
  --recognition-mode melody \
  --body-responses-dir 'screenshots/trans-jp-melody/final-replay/image/rows' \
  --no-melody-review --debug

python third_party/trans-jp/tools/evaluate_melody.py \
  --split holdout --output-dir screenshots/trans-jp-melody/holdout-local-repeat
```

在线凭据仍通过环境变量或 CLI 输入，不写入任何证据产物。生产代码不会自动读取其他模块的 .env。

- `melody.json`：每音各属性值/状态、证据编号、分数时值、区域与元数据状态。
- `melody-evidence/`：附属候选、原图框、复核图册/请求/响应、区域关系及元数据来源图。
- `melody-manifest.json`：主体 manifest 绑定及全部证据文件哈希。
- 原有 SVG、SourceMap、文本锚点不改 source_id。只有整个区域局部属性均确认才替换其文本，未知区域保留主体并警告。
- v1/v2/v3 回放保持兼容；melody 只能基于 v3，不能把旧整行响应默认为可靠主体。

本地预览和结果在 `screenshots/trans-jp-melody/`：条件基准目录为 `benchmark-*`，整页原始在线为 `online-bodies-review/`，最终离线投影为 `final-replay/`。冻结复核 fixture 为 `tests/fixtures/melody/frozen_reviews.json`；回归不需要网络。

## 已实现与未完成的边界

已实现：上下文填充、候选编号、独占符号与共享线区分、未知与零的区分、局部复核不猜坐标、未知休止符保护、精确分数计算、冲突留空、请求失败隔离、证据和回放、主体 ID 稳定、独立实验模式。

尚未完成：

1. **元数据局部确认及中途变化生效**：已补本地等号笔画候选、编号裁剪图和局部声明转写；两页局部测试分别正确读到 Bb/4/4 与 C#，但均为 observed_local，尚无独立局部验证或跨区域生效映射；不能完成调号依赖的音高及有效拍数校验。
2. **独立的附属符号实例/归属标注**：现有 299 样本标注属性数量和主体框，没有人工逐个点线框及 owner 真值；不能宣称符号归属正确率已被独立测得。
3. **整谱端到端完整音符定量指标**：新增在线主体＋局部属性在重叠标注子集的对齐评测，98 个目标中 85 个完整局部属性正确（86.73%）；只覆盖 image/image copy 2 开发页面的选定行，不能代替保留集或整谱的独立评测。
4. **符号类别覆盖**：真实升号样本少，降号、还原号类别没有足够实谱标注；连音组、倚音、跨行延音、透视畸变、复杂多声部不支持。
5. **确认零属性仍依赖启发式**：短/断/粘连墨迹可能漏检，搜索区完整不等于识别完美。局部 VLM 会把歌词或邻近墨迹误认成八度点。
6. **85% 覆盖率验收未达到**：保留集只有 67.80%，默认 bodies 未替换，melody_complete 保守为 false，禁止宣称成品乐谱。

本轮保留完整实验和失败证据。后续优先制作点线归属真值、收窄八度复核候选，以及元数据局部确认；不能单靠放宽 unknown 或默认一拍提高数字。

最终校验：子项目测试加根架构测试 **185 passed**；Ruff 检查及格式检查通过。三张整页已用最终代码离线重放并校验 melody manifest，结果入口为 `screenshots/trans-jp-melody/index.html`。本轮未达到完整方案的质量及元数据/归属真值要求，以上未完成项仍需后续工作。


### 局部元数据补充验证

最终实现新增本地等号笔画配对，提出带实测边界的 metadata 区域，每批最多六个；VLM 只转写局部声明文本，不返回位置。谱面内独立拍号变化若没有等号仍可能漏检，因此本轮不宣称完整元数据检测。

使用同一模型的两页局部复核：`image.png` 读到 `1=bB`、`4/4`，规范化为 Bb、4/4；`image copy 10.png` 读到 `1=#C`，规范化为 C#。后者修正了之前整页请求的 F# 误读。这是额外小实验，没有覆盖或挑选替换此前属性基准结果。原图裁剪、请求与响应保存在 `screenshots/trans-jp-melody/local-metadata-check/`。

新在线 melody 运行会生成 local-metadata.json 和编号局部证据。旧冻结运行无局部 metadata 文件时保持原证据，不偷偷联网补齐。局部声明只给出可能后继主体和 activation_status=unknown，不自动成为调号/拍号生效事实。现有整页 final-replay 忠实保留先前整页观测值（包括 F# 错读），与局部实验分开展示。

`melody_complete` 仍固定为 false；当前用于字段级确认与错误分析的实验，不是完整可播放谱。原方案要求的独立附属关系真值、整曲状态和端到端完整音符质量仍未全部交付。


### 在线主体＋属性子集对齐

`tools/evaluate_melody_outputs.py` 校验冻结 melody manifest、源图哈希及主体候选框，再将真实 v3 主体结果与现有属性真值按编号对齐。对有重叠标注的 image/image copy 2 选定行，共 98 个目标，完整局部属性被确认 85 个且 85 个均正确。未进入属性处理或仍未知的目标计入总分母。其余已标注页面没有本轮整页在线主体产物，明确列在 excluded_pages_without_outputs；image copy 10 没有本轮属性真值，不加入分母。

该 86.73% 是开发页子集的主体＋局部属性覆盖率，不能作为保留集质量、完整音高或整曲准确率。结果为 `screenshots/trans-jp-melody/end-to-end-metrics.json`，仍不包含独立点线归属真值、有效调号、延音和声部时间。

```bash
source .venv/Scripts/activate
python third_party/trans-jp/tools/evaluate_melody_outputs.py   --root screenshots/trans-jp-melody/final-replay   --output screenshots/trans-jp-melody/end-to-end-metrics.json
```
