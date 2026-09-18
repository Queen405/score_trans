# trans-jp

独立的简谱图片识别引擎：本地 CV 分析真实主体并分配候选编号，视觉 LLM 引用编号转写语义，再输出原位音符 SVG。默认使用 v3 小批主体分类，不再让模型估算坐标或一次生成整行音乐语法。
实现采用分层处理管线，详见 [ARCHITECTURE.md](ARCHITECTURE.md)。后端与 desktop 的实际调用接入尚未包含在本轮修改中。

## 安装与运行

从 Score Trans 仓库根目录使用 Bash 和项目虚拟环境：

```bash
uv pip install -e 'third_party/trans-jp[test]' --python .venv/Scripts/python.exe

# 本地设置 TRANS_JP_API_KEY / TRANS_JP_BASE_URL / TRANS_JP_MODEL 后运行
.venv/Scripts/python.exe -m trans_jp \
  --input third_party/trans-jp/examples/image.png \
  --output-dir screenshots/trans-jp-output \
  --target-key C --concurrency 2 --debug
```

默认 `--recognition-mode bodies` 只确认数字 0–7 和小节线主体，属于诊断预览；`jianpu.txt` 含未确认时值/八度的提示，不能直接作为可播放的完整乐谱。需要旧整行语义识别时显式使用 `--recognition-mode notation`（v2）。没有新增 OCR 依赖，模型配置不变。

## 输出契约

| 文件 | 内容 |
|---|---|
| `jianpu.txt` | bodies 模式为主体预览；notation 模式为语义文本，保留未定位 token |
| `overlay.svg` | 原图大小、透明背景、数字字形路径及几何符号；不含可见源码或矩形 |
| `overlay-preview.png` | 同一份 SVG 与原图的彩色叠加 PNG，像素尺寸一致 |
| `score-link-map.json` | SourceMap v1，实测图形的原图坐标与命中区域 |
| `text_anchors.json` | UTF-16 文本锚点；数量可以大于 SourceMap 元素数量 |
| `rows/row_N.png` | 实际送识别的逻辑行裁剪图 |
| `rows/row_N.json` | 匹配前规范化响应；v2 含 `candidate_ids`、`unresolved_candidates`、`complete` |
| `requests/row_N-candidates.json` | 行局部工作坐标、确定性编号、基线带及互斥候选 |
| `requests/row_N-atlas_K.png` | v2 整行识别图册，每页最多 24 个候选 |
| `requests/row_N-response.txt` | v1/v2 模型原始返回文本，解析前保留 |
| `batches/rNNNN-bNNNN-*` | v3 每批最多 12 个主体：图册、请求、原始响应和规范化分类结果 |
| `manifest.json` | 源图/裁剪图/候选哈希、变换、版本及非敏感请求参数 |
| `overlay-debug.svg` | `--debug`：实测框及横/竖 filament 候选 |
| `overlay-diagnostics.json` | `--debug`：变换、阶段耗时、行结构、原始坐标、几何和警告 |

notation 模式支持数字、休止符、升降号、八度点、附点、减时线、延长线、和弦、小节线、同一行内的普通圆滑线和延音线。
标题、歌词保留在底图。跨行连线、连音组和复杂演奏法暂不重绘，记录诊断；不会为了凑拍数改写识别结果。

bodies 模式只绘制已确认的主体及实测减时线；八度、附点、升降号、连线和时值不推断，音符标为 `partial`。独立垂直列可作为视觉音符叠放，多基线按上下分组；这不能证明和弦或声部的时间关系。

定位状态：`matched` 为匹配完整，`partial` 为部分附属符号缺失，`unmatched` 为缺少可靠位置，
`ignored` 为不绘制的文字/语法，`unsupported` 为不支持的记法。它们不表示模型语义识别正确率。
非法编号、重复占用、阅读顺序/小节边界冲突的相关 token 均留空；不会退回坐标猜测。没有几何的 token 不绘制，也不创建点击区；共用减时线只画一次，点击区按相邻音符分开。

## 无网络回放

```bash
PYTHONPATH=third_party/trans-jp .venv/Scripts/python.exe \
  third_party/trans-jp/tools/replay_overlay.py \
  --input third_party/trans-jp/examples/image.png \
  --responses-dir third_party/trans-jp/tests/fixtures/liangzhu \
  --output-dir screenshots/trans-jp-layered
```

该样例只转写《梁祝》的三行，共 60 个 token，响应为人工核对的几何参考，并非在线模型输出。
用于确定性验证位置和绘制，不能当作整页或线上识别准确率。可以用自己一次运行的 `rows/` 替换响应目录，
但必须保持相同图片、预处理参数和引擎版本；输出目录应与输入分开。v2/v3 回放还需要与 `rows/` 同级的 `manifest.json` 和 `requests/`；v3 还需要完整 `batches/`，校验失败会在识别前终止。旧 v1 响应仍可回放，但缺失/退化坐标不会补位或裁剪，只接受唯一且双向最近的保守匹配，可能比旧版留空更多。

## 验证和字形构建

```bash
.venv/Scripts/python.exe -m pytest third_party/trans-jp/tests -q
.venv/Scripts/python.exe -m ruff check third_party/trans-jp

# 仅重新构建字形资产时使用（需要 fontTools，项目 .venv 已提供）
.venv/Scripts/python.exe third_party/trans-jp/tools/build_glyphs.py
```

字形取自仓库现有 Noto Serif CJK 和 Bravura，13 个所需字形的路径和源文件哈希存于包内 `assets/glyphs.json`。
OFL 许可证随包分发。运行时无需字体文件、fontTools、OpenCV、Java 或 Score Trans 后端。

Windows Git Bash 手动设置多个 `PYTHONPATH` 时，Windows Python 仍使用分号：
`PYTHONPATH='backend;third_party/trans-jp'`。

## 坐标回归与实际质量

```bash
source .venv/Scripts/activate
python third_party/trans-jp/tools/replay_reviewed_bodies.py   --output-dir screenshots/trans-jp-coordinate-v2/reviewed-geometry
python third_party/trans-jp/tools/evaluate_coordinates.py   --root screenshots/trans-jp-coordinate-v2/reviewed-geometry   --output screenshots/trans-jp-coordinate-v2/geometry-metrics.json
```

`reviewed_bodies.json` 冻结了四张图片中 211 个经视觉核对的数字/小节线主体。
主体框来自核对后的 CV 候选，指标用于坐标绑定回归，不是独立检测器泛化评测；不评价八度、时值或完整乐曲。
纯几何参考回放和在线模型识别必须分开比较。2026-09-17 的结果、已知缺陷及复现方法见 [COORDINATE_REVIEW.md](COORDINATE_REVIEW.md)。

在线运行沿用 `TRANS_JP_API_KEY / TRANS_JP_BASE_URL / TRANS_JP_MODEL`，不会自动加载其他模块的 `.env`。
使用 `--debug` 保存完整定位诊断。旧注入客户端可继续实现 `transcribe_row_with_retry`；新版客户端实现 `transcribe_request_with_retry(RowRecognitionRequest, prompt, ...)`。

## v3 主体分类结果与回放

2026-09-18 对 8 张谱面进行在线测试；已有 211 主体标注中，输出 208 个，206 个符号与位置正确，2 个额外误标，5 个目标主体未正确输出。主体覆盖率 97.63%，输出一致率 99.04%。这些指标不包括节奏、八度、歌词或完整音乐语义。详细范围、批次失败和局限见 [BODY_RECOGNITION_REVIEW.md](BODY_RECOGNITION_REVIEW.md)。

```bash
source .venv/Scripts/activate
python third_party/trans-jp/tools/replay_overlay.py   --input 'third_party/trans-jp/examples/image copy 6.png'   --responses-dir 'screenshots/trans-jp-coordinate-v3/online/image copy 6/rows'   --output-dir 'screenshots/trans-jp-coordinate-v3/replay-again/image copy 6'
python third_party/trans-jp/tools/evaluate_coordinates.py   --root screenshots/trans-jp-coordinate-v3/final-replay   --output screenshots/trans-jp-coordinate-v3/metrics.json
```

v3 注入客户端实现 `CandidateClassifier.classify(CandidateBatchRequest) -> CompletionResult`；严格解析后形成 `CandidateBatchResult`。请求失败最多重试两次，其他批次继续；所有请求失败或响应非法时保存诊断后返回退出码 3。所有请求成功但主体未知时允许输出空预览，unknown 不改写为休止符。

## 实验性单旋律属性（melody）

新增 `--recognition-mode melody`，默认仍为 bodies。可用 `--body-responses-dir <v3 rows>` 复用主体，使用 `--no-melody-review` 进行纯本地分析。配置现有 TRANS_JP_* 后可启用每批最多六个主体邻域的局部复核。

新增 melody.json、melody-evidence/ 和 melody-manifest.json；未知属性不补成 0 或一拍，时值用分子/分母表示，完整区域之外保留主体预览。整页模型调号/拍号仅为 observed，不是验证过的音乐上下文；不提供默认可播放导出。全部模式保留原有 SourceMap v1 和主体 source_id。

299 个人工属性样本中，保留集本地＋局部复核完整局部属性正确 80/118（67.80%），未达到 85% 目标。此数字假定主体正确，不能替代完整乐谱准确率。实施范围、未完成项、命令和失败样例见 [MELODY_REVIEW.md](MELODY_REVIEW.md)。


局部元数据可通过本地等号候选裁剪复核，局部模型读数为 observed_local（不是已验证调号）；变化的生效范围不确定时继续留空。185 项测试通过不等于乐谱质量达标，完整验收缺口详见 MELODY_REVIEW.md。
