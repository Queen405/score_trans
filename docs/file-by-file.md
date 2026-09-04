# Score Trans 当前文件索引

> 本索引只描述当前实现。历史审计、旧渲染器设计和删除计划不再放在本文件中。
> 分层规则见 [architecture.md](architecture.md)，开放问题与待办见 [issues.md](issues.md)。

## 后端入口

| 目录 | 职责 |
|---|---|
| backend/score_trans/api | FastAPI 路由、依赖注入和统一异常响应 |
| backend/score_trans/exec | 请求级 Actions 和跨服务编排 |
| backend/score_trans/services | 外部工具、渲染、OCR、AI、文件、历史和任务服务 |
| backend/score_trans/domain | 简谱/MusicXML 解析、写出和领域计算 |
| backend/score_trans/models | DTO、实体、协议、错误和跨层类型 |
| backend/score_trans/dao | SQLite 持久化和迁移 |
| backend/score_trans/config | 环境变量、默认设置和 AI prompt 配置 |
| backend/score_trans/utils | XML、PDF、JSON、文本和环境加载辅助 |

## API 与 Actions

| 模块 | 入口 | 主要职责 |
|---|---|---|
| api/convert | ConvertActions | MusicXML 与简谱互转 |
| api/recognize | RecognizeActions | 图片/PDF 识别和 OMR 任务 |
| api/render | RenderActions | 简谱 SVG、A4 页面和归一化 |
| api/export | ExportActions | MIDI、MusicXML、PDF、PNG/JPEG 导出 |
| api/pipeline | PipelineActions | 识别到渲染的一键流程 |
| api/history | HistoryActions | 批次、页面、渲染页和 OCR 历史 |
| api/settings | SettingsActions | 设置读取、更新和缓存清理 |
| api/ai | AiActions | AI 转录和聊天会话 |
| api/syntax | SyntaxActions | 简谱语法诊断 |
| api/jianpu | JianpuActions | 换调号时按音高重记谱（自动转调） |
| api/correct | CorrectActions | 结构元素修正与 MusicXML patch |
| api/notation | NotationActions | 乐器画像（erhu/ruan/guzheng 等）目录 |
| api/files | FileActions | 上传、下载、删除和文件存在检查 |
| api/tasks | TaskActions | 后台任务 SSE 进度流 |

## Domain

| 文件 | 职责 |
|---|---|
| domain/jianpu.py | 简谱转换门面；组合 parse/write，不承担 HTTP |
| domain/musicxml.py | MusicXML 转换门面和稳定 re-export |
| domain/parse/jianpu_text.py | 简谱文本解析、分页、声部、语法诊断 |
| domain/parse/musicxml.py | MusicXML 到 JianpuScore 的解析和 provenance |
| domain/write/jianpu_text.py | JianpuScore 到简谱文本的写出 |
| domain/write/musicxml.py | JianpuScore 到 MusicXML 的写出 |
| domain/jianpu_tokens.py | 时值、附点、延长线、连音组与音高核心 span 定位 |
| domain/accidentals.py | 变音记号和调式转换 |
| domain/pitch_spelling.py | 音名、调号、书写音高转换与等音重拼 |
| domain/rekey.py | 换调号时按绝对音高重记谱，保留排版与非音符 token；删除调号按管辖调回退，无法转调时回传跳过原因 |
| domain/performance_marks.py | 演奏记号目录与查找 |
| domain/provenance.py | source anchor 和 provenance 合并 |
| domain/text_attachments.py | OCR 文字附件和源区域关联 |
| domain/text_placement.py | A4 文字附件布局 |
| domain/xml_utils.py | 安全 XML/MXL 读取辅助；文件 I/O 迁移候选 |

## Services

| 子包 | 当前实现 |
|---|---|
| services/render | main.py 门面、render_service.py 文件输出门面、engraving 唯一渲染引擎 |
| services/ocr | OCR 协议、解析、provider、prompt 和 OCR service |
| services/ai | AI provider 注册、HTTP、视觉转录、合并和校验 |
| services/recognize | Audiveris subprocess、Java 检查和识别辅助 |
| services/export | MIDI 与图片/PDF 导出 |
| services/files | 文件读写、图片信息、上传索引和缓存 |
| services/history | HistoryDao 的服务门面 |
| services/settings | SettingsDao、环境 fallback 和 provider 配置 |
| services/correct | clef/key/time 修正和 MusicXML patch |
| services/overlay | OMR overlay、source map 和 SVG 生成 |
| services/tasks | 后台任务状态和 SSE 进度 |
| services/storage | 缓存清理与历史文件引用校验 |
| services/syntax | 简谱语法校验服务门面 |
| services/jianpu | 换调重记谱服务门面 |

### 重要渲染文件

- services/render/engraving/renderer.py：布局、分页、绘制和 spanner，当前最大后端文件。
- services/render/engraving/geometry.py：音符、记号、歌词和文字附件几何。
- services/render/engraving/scene.py：SVG 场景和 render-map 数据。
- services/render/main.py：稳定的公开渲染函数。
- services/render/render_service.py：文件型渲染门面。
- services/render/options.py：仍被 main.py 和 render_service.py 使用的 RenderOptions。

## Models 与 DAO

| 目录/文件 | 职责 |
|---|---|
| models/score.py | JianpuScore、Measure、Event、JianpuPitch、TextBlock |
| models/*/schemas.py | API 请求/响应模型 |
| models/history/entities.py | HistoryBatch、HistoryPage 等持久化实体 |
| models/common/errors.py | 外部工具、OCR、AI、渲染和校验错误 |
| models/common/paths.py | 项目、用户数据、缓存和旧目录迁移路径 |
| models/jianpu/types.py | RekeyResult 与跳过原因，供 domain/service/api 共用 |
| dao/history/history_dao.py | history schema、迁移、批次/页面 CRUD |
| dao/settings/settings_dao.py | key-value 设置和旧设置迁移 |
| dao/tasks/task_dao.py | 后台任务状态 |
| dao/ai/chat_dao.py | AI 会话和消息 |
| dao/storage.py | 旧 SQLite 文件迁移 |

## 桌面端

| 目录 | 职责 |
|---|---|
| desktop/src/main | Electron 主进程、后端生命周期、导出 IPC、存储迁移 |
| desktop/src/preload | window.api capability 类型和 contextBridge |
| desktop/src/renderer/src/api | typed API adapter，返回 ApiResult |
| desktop/src/renderer/src/models | OpenAPI 生成类型、contracts 语义别名、types 稳定重导出 |
| desktop/src/renderer/src/stores/workspace.ts | 多页、批次、历史身份和渲染 stale 状态 |
| desktop/src/renderer/src/stores/settings.ts | 设置加载、草稿和保存 |
| desktop/src/renderer/src/views/ConvertView.vue | 编辑、渲染、导出、历史恢复和保存 |
| desktop/src/renderer/src/views/RecognizeView.vue | 上传、识别任务、批次渲染和历史同步 |
| desktop/src/renderer/src/views/SyntaxView.vue | 语法指南和示例 |
| desktop/src/renderer/src/components/JianpuEditor.vue | 简谱编辑、诊断高亮和分页导航 |
| desktop/src/renderer/src/components/JianpuPlayer.vue | MIDI 生成和播放 |
| desktop/src/renderer/src/utils/batchRender.ts | 批量分页请求和渲染响应归一化 |
| desktop/src/renderer/src/utils/jianpuPageSections.ts | 分页标记、段落恢复和重排 |
| desktop/src/renderer/src/utils/recognitionHistory.ts | 识别批次历史快照 |

## 维护规则

1. 新增代码先确认是否属于现有职责，避免创建新的薄门面。
2. 删除文件前必须搜索生产、测试、动态注册和文档链接。
3. models/openapi.ts 是生成文件，不手工删字段；应从 Pydantic schema 改起再生成。
4. 旧数据迁移、OCR 旧格式和渲染兼容逻辑不能按文件名直接删除。
5. 大文件优先按职责移动，行为稳定后再删除重复代码。
