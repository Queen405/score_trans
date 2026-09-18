# 坐标修正验证记录（2026-09-17）

## 已实现

在线识别默认采用候选编号协议 v2。本地 CV 负责行局部真实坐标、基线带、线段与互斥关系；VLM 接收原行 PNG 和带编号候选图册，只返回内容及编号。编号通过当前行、类型、数量、重复占用、声部、和弦和阅读顺序校验后才能产生几何。冲突时相关 token 留空，不做最近邻兜底。

八度点、升降号、附点、减时线和延长线相对实测主体定位。共享减时线保留独立命中范围；多归属附属符号留空。SVG、SourceMap 沿用同一原图坐标变换；越界/无效几何在两种输出前统一拒绝。

旧响应支持保守回放：保留原坐标，不裁剪、等距填充或强行拉伸。只有双向唯一且位置接近的匹配可绘制。严重坐标错误需重新识别，旧响应没有足够信息可供可靠修复。

保存候选、原始响应、图册和运行 manifest；v2 回放检查图像、裁剪、变换、尺寸和候选哈希。既有 SourceMap v1、文件名及 source_id 格式保持兼容。

## 验证方法及边界

所有命令通过 Git Bash 和项目 `.venv/Scripts/python.exe` 执行。测试使用新建独立临时目录，未改变系统临时目录权限。

- 测试覆盖 211 个视觉核对主体、简单真实图片、非法/重复/跨行编号、顺序冲突、漏音、和弦、多声部、共享线、逆变换、PNG 请求、截断重试、v2 离线回放及篡改拒绝。
- 加上仓库架构测试，本次最终运行 **146 passed**；Ruff 检查通过。
- 原有《梁祝》60-token 人工几何 fixture 的回放和 desktop DTO 兼容测试继续通过。
- 新标注集包含 `sample_jianpu` 三行、`image copy 10` 四行、`image copy 12` 一行、`image copy 13` 一行，共 211 个主体。
- 框来自经过视觉核对的 CV 候选；`image copy 12` 中粘连的 0/5 单独标注。因此 IoU 是回归指标，不是独立检测器评测。标注不评价八度、时值、连线、歌词或整曲正确性。
- “正确”要求框 IoU ≥ 0.5、数字值或小节线类型一致、一对一匹配。相同数字之间的语义身份交换不一定可被该指标发现。

## 结果

| 数据路径 | 标注主体数 | 输出主体 | 符号与位置同时正确 | 输出主体一致率 | 正确定位覆盖率 |
|---|---:|---:|---:|---:|---:|
| 修改前代码＋用户保存的旧响应 | 211 | 63 | 15 | 23.81% | 7.11% |
| v2＋本次在线响应（最终代码离线复现） | 211 | 97 | 95 | 97.94% | 45.02% |
| v2＋视觉核对的主体/编号参考 | 211 | 209 | 209 | 100% | 99.05% |

旧响应没有记录可靠的模型来源，因此前后在线数据不是同模型、同响应的严格消融实验。纯几何参考仅验证坐标链路，不能当作模型识别准确率。

本地候选覆盖 209/211 个标注主体。缺少的两个是 `image copy 12` 中粘连的 0/5，代码将该宽框标记为歧义并留空，未将两音画进同一个框。

简单样例：旧输出 30 个应定位主体只画出 9 个，且其中只有 1 个符号及位置同时正确；本次在线输出 **30/30 正确对应**。其中 3 个 token 是 partial，因为样例用文本撇号表示高八度，不是印刷简谱的圆点，附属圆点未定位。

分图的在线标注结果：

| 图片 | 标注主体 | 输出主体 | 符号与位置同时正确 |
|---|---:|---:|---:|
| sample_jianpu | 30 | 30 | 30 |
| image copy 10 | 124 | 47 | 45 |
| image copy 12 | 33 | 15 | 15 |
| image copy 13 | 24 | 5 | 5 |

## 在线运行

使用仓库根 `.env` 已配置的模型 `agnes-3.0-flash`，仅本次验证脚本读取 SCORE_TRANS_AI_* 配置；未修改配置文件，生产 CLI 仍读取 TRANS_JP_*。

原行和图册均为 PNG，temperature=0，max_tokens=8192，并发 2，单请求 read timeout 90 秒。五张完整图片均产生输出，部分行出现服务端断连，重试后仍失败的行保留失败诊断。

| 图片 | 本次总耗时 | 仍失败的行（0 起始） |
|---|---:|---|
| sample_jianpu | 37.01 秒 | 无 |
| image（梁祝） | 189.97 秒 | 5 |
| image copy 10 | 339.98 秒 | 4 |
| image copy 12 | 411.21 秒 | 无 |
| image copy 13 | 164.89 秒 | 2 |

时长包含网络、重试、识别和本地处理；不作为性能基准。后续代码校验调整通过冻结响应重放验证，没有为提高分数反复重采样这些最终在线结果。

## 尚未达到的目标

**在线 99% 一致率目标未达到，复杂谱面还不能视为可靠成品。** 两个已绘制错误来自 `image copy 10`：模型在合法候选位置上返回了错误数字。其余缺口包括不受支持的合并 token、错误的声部/小节编号关系、粘连候选以及网络失败。

这次没有加入数字分类器来独立验证 VLM 语义；合法编号并不证明数字识别正确。复杂多声部和密集小音符的候选检测仍有局限。小型点状带过滤属于保守几何启发式，不能保证所有倚音字体都保留。

下一步应先做“候选 ID → 单个数字类别”的独立识别评测，再决定是否加入 OCR/小型分类器；不建议放宽冲突拒绝来提高覆盖率。

## 本地结果与复现

所有输出均在仓库 `screenshots/trans-jp-coordinate-v2/`，原 `screenshots/trans-jp-output/` 未覆盖。

- `baseline/`：修改前代码重放原响应，含对比预览与诊断。
- `final-online/`：五张原始在线运行，包含原始响应、候选和 manifest。
- `final-replay/`：当前代码重放上述在线响应，推荐查看此目录的覆盖图。
- `reviewed-geometry/`：视觉核对主体参考，仅检验几何。
- `baseline-metrics.json`、`online-metrics.json`、`geometry-metrics.json`：逐行指标及错字记录。

```bash
source .venv/Scripts/activate
python third_party/trans-jp/tools/replay_overlay.py \
  --input 'third_party/trans-jp/examples/image copy 10.png' \
  --responses-dir 'screenshots/trans-jp-coordinate-v2/final-online/image copy 10/rows' \
  --output-dir 'screenshots/trans-jp-coordinate-v2/replay-again/image copy 10'

python third_party/trans-jp/tools/replay_reviewed_bodies.py \
  --output-dir screenshots/trans-jp-coordinate-v2/reviewed-geometry

python third_party/trans-jp/tools/evaluate_coordinates.py \
  --root screenshots/trans-jp-coordinate-v2/final-replay \
  --output screenshots/trans-jp-coordinate-v2/online-metrics.json
```

截图产物是本地交付文件；可复现的标注、评测工具、测试和本文档已加入项目源代码。所有候选/回放格式变化均须更新算法版本并重新生成相应 fixture，不得绕过哈希检查。
