# Score Trans 代码精简与分层重构执行报告

> 调研日期：2026-08-23
> 基线：当前工作树 HEAD
> 目标：删除无效代码、合并重复实现、降低模块耦合，避免把“代码少”误当成“代码好”。

## 1. 结论先行

当前项目不是单纯的“死代码堆积”，而是三种问题叠加：

1. 少量可确认的孤立符号和重复包装函数；
2. 核心解析器、渲染器和工作区状态集中在少数巨型文件；
3. 一些跨层门面、兼容字段和历史数据逻辑承担真实行为，不能直接删除。

推荐目标不是一次性大删，而是按“证据确认 → 测试保护 → 小批删除 → 全量验证”的顺序推进。

当前可立即进入候选清理的范围约为 100-180 行；可以通过重构减少维护重复、但不能简单删除的范围约为 250-500 行。巨型文件拆分主要改善可维护性，短期不应以净删行数为验收指标。

## 2. 当前规模与审计边界

| 范围 | 当前数量 |
|---|---:|
| 后端 Python 文件 | 232 |
| 后端 Python 行数 | 25,328 |
| 前端 desktop/src 源码文件 | 79 |
| 前端源码行数 | 24,682 |
| tests 与 desktop/scripts 测试脚本 | 46 |
| 最大后端文件 | services/render/engraving/renderer.py，2,206 行 |
| 最大前端业务文件 | ConvertView.vue，约 2,410 行 |

### 2.1 证据等级

- A 级：全仓引用扫描、AST/符号检查和目标实现阅读都能确认。
- B 级：实现逻辑明确，但需要新增行为测试或性能基准。
- C 级：设计判断、公共 API 风险或未来维护建议，不能直接当成 bug。

本报告使用全仓文件清单、引用扫描、函数骨架提取、架构核心文件阅读和关键模块逐段阅读。不能诚实地把 49,000 多行代码在报告中逐字复述为“已全部人工逐行阅读”；因此，删除建议只对 A 级证据直接放行，其余必须先补验证。

## 3. 目标分层

目标依赖方向：

~~~text
api -> exec -> services -> dao
                 \-> domain
所有层 -> models
~~~

### models/

只放 DTO、实体、协议、错误类型和跨层公共类型。不得依赖业务模块。

### domain/

只做纯解析、转换、布局计算和领域规则。理想状态是不直接读写文件、不访问数据库、不发 HTTP。

### dao/

只负责持久化和数据库迁移。JSON 编解码可以保留在 DAO 内，但必须有明确的兼容测试。

### services/

负责外部工具、HTTP、文件、渲染、OCR、AI 和持久化服务生命周期。

### exec/

负责请求级业务编排和跨服务流程，不承载底层算法，也不直接处理 HTTP 响应细节。

### api/

只负责 HTTP 请求解析、依赖注入、异常到响应的转换。

## 4. 第一批：可确认删除或收敛的代码

这些项目必须在删除前再次运行引用扫描。内部零引用不等于公共 API 零影响。

### 4.1 孤立符号

当前全仓只看到定义或 re-export 的候选：

| 符号 | 文件 | 判断 |
|---|---|---|
| DEGREE_TO_MAJOR_OFFSET | domain/constants.py | A 级孤立 |
| PREFIX_SLASHES | domain/jianpu_tokens.py | A 级孤立 |
| first_ocr_measure_number() | domain/text_attachments.py | A 级孤立 |
| jianpu_to_html() | domain/jianpu.py | A 级孤立，但可能是公共 API |
| score_to_musicxml() | domain/write/musicxml.py | 仅 re-export，需确认公共 API |
| musicxml_path_to_score() | domain/parse/musicxml.py | 仅 re-export，生产使用复数版本 |

删除门槛：

1. git grep 覆盖 backend、tests、desktop；
2. 检查 README、示例、脚本和插件入口；
3. 确认没有对外发布的 Python API 承诺；
4. 删除后运行全量后端测试和类型检查。

### 4.2 包根 re-export

domain/__init__.py、domain/parse/__init__.py、domain/write/__init__.py 目前主要提供包级 re-export，仓库内部没有发现生产引用。

建议分两步：

1. 先把 __all__ 和 re-export 标记为“兼容 API”并补导入测试；
2. 在确认没有外部调用者后，改为空包或删除不必要的导出。

不建议第一批直接删除，因为这会破坏外部脚本的 from score_trans.domain 导入，即使仓库内部没有引用。

### 4.3 纯委托包装

以下函数当前没有附加行为：

- domain/parse/jianpu_text.py 的 _consume_duration_prefix
- domain/write/jianpu_text.py 的 _duration_parts
- domain/write/jianpu_text.py 的 _mark_token
- domain/write/jianpu_text.py 的 _pitch_to_token

可以直接改为调用底层函数，但必须先检查调试入口、测试 monkeypatch 和模块级 API。

## 5. 第二批：重复实现合并

### 5.1 连音组归一化

_tuplet_normal_notes() 在 Jianpu 解析、Jianpu 写出和 MusicXML 写出中有三份相同实现。

建议移动到 domain/jianpu_tokens.py 或新的 domain/duration.py。验收：

- 现有连音组测试全部通过；
- 2、3、4、5、6、7、8、9 音符的 normal count 结果保持不变；
- 不引入 parse/write 反向依赖。

### 5.2 UTF-16 偏移

_utf16_length() 和 _utf16_offset() 的底层计算相同，但要先确认 offset 的单位。推荐：

- 建立一个命名明确的 utf16_length_prefix(text, codepoint_offset)；
- 所有调用点显式声明输入单位；
- 增加中文、emoji、代理对和 CRLF 测试。

### 5.3 变音记号

变音记号映射分布在：

- domain/accidentals.py
- domain/parse/musicxml.py
- domain/write/musicxml.py
- domain/parse/jianpu_text.py

可以集中“原始 token ↔ Fraction”的基础映射，但不能把简谱显示 token、MusicXML accidental 名称、written alter 和微分音兼容逻辑强行合并成一个函数。推荐先建立共享表，再保留各协议层的薄转换函数。

### 5.4 A4 尺寸和安全区域

1240/1754 当前散落在 14 处。建议在 models/render 或专门的无 I/O 常量模块中统一：

- A4 宽高；
- 安全边距；
- 文本层可用区域。

必须保留不同坐标系统的语义测试，不能只替换数字。

### 5.5 AI/OCR HTTP 客户端

AI 与 OCR 的 _http.py 都使用 httpx.post，但 AI 还支持 extra_body、流式响应和 reasoning chunk。

推荐提取“构造请求 body、解析 completion”的共享部分，不要让 OCR 直接依赖完整 AI provider 模块。第二阶段再引入由 service/composition 持有的 httpx.Client。

### 5.6 persisted settings

persisted_ai_settings() 与 persisted_ocr_settings() 逻辑相同，可以提取共享函数。但必须先决定异常策略：

- 配置文件读取失败应记录日志；
- 只有明确允许的缺省场景才返回空字典；
- 不能继续无条件吞掉所有 Exception。

## 6. 第三批：行为相似但不能直接合并

### 6.1 小节归一化

_normalize_parsed_measure() 与 _normalize_measure() 结构相似，但行为不同：

- Jianpu 解析记录少拍/超拍诊断；
- MusicXML 解析会生成补足休止符；
- 两者的输入状态和错误策略不同。

只能抽取“按 beat 分桶”的纯算法，少拍策略通过参数或策略对象注入。

### 6.2 滑行方向

两个解析器都比较首尾音高，但 Jianpu 版本还包含古筝限制和语法错误，MusicXML 版本是结构恢复逻辑。建议只共享 infer_slide_direction(start, stop)，不要合并整个流程。

### 6.3 first_present

字典版本表示“第一个存在且非 None 的字段”，列表版本表示“第一个 truthy 字符串”。建议改名，而不是强行合并。

## 7. 第四批：架构整改

### 7.1 domain 文件 I/O

domain/xml_utils.py 直接使用 Path、ZipFile 和 XML 文件读取；domain/jianpu.py 也提供文件路径门面。

建议：

1. services/files 负责读取 XML/MXL；
2. domain 只接收 XML 字符串或已解析对象；
3. 保留一个明确的 service 级文件门面；
4. 先补 MXL、DOCTYPE、安全 XML 和文件不存在测试。

### 7.2 MusicXML 修正索引

services/correct/musicxml_patch.py 对多个删除 ID 重复遍历 XML 树。可建立一次性 parent_map、source_id 到 element 的 locator，以及必要的祖先索引。

验收必须包括结果等价测试和大 XML 基准，不能只看代码行数。

### 7.3 measure number 双字段

当前 API、settings、render DTO 同时保留 show_measure_numbers 与 measure_number_mode。

建议迁移顺序：

1. 先统一内部模型只使用 measure_number_mode；
2. 在 API 边界兼容旧布尔字段；
3. 增加冲突组合测试；
4. 最后删除旧字段和数据库兼容代码；
5. 重新生成并校验 openapi.ts。

### 7.4 SQLite DAO 配置

当前 SettingsDao 没有 WAL/busy timeout；TaskDao 有 WAL、没有 busy timeout；AiChatDao 两者都有；HistoryDao 两者都有。

建议抽取统一 SQLite connection helper，但要保留 DAO 特有的事务边界和迁移行为。

### 7.5 异常 stage

api/app.py 对 ExternalToolError 固定返回 audiveris。当前异常主要来自 Audiveris 链路，因此这是扩展性风险，不是已证明的当前错误。

如果未来该异常复用到其他外部工具，再让异常携带 stage；不要为尚不存在的路径提前引入复杂抽象。

## 8. 巨型文件拆分顺序

### 8.1 后端

1. exec/render/actions.py：OCR 文本兼容、请求参数兼容、batch render 编排。
2. domain/parse/jianpu_text.py：MeasureBuilder、token 校验、文档/分页结构。
3. domain/parse/musicxml.py：measure event handlers、direction/text handlers、provenance handlers。
4. services/render/engraving/renderer.py：layout、drawing、spanners、text placement。
5. dao/history/history_dao.py：schema migration、batch/page persistence、serialization helpers。

拆分原则：先移动函数、保持 API 不变、每批只改一个职责组；不要在同一批次同时改数据结构和协议。

### 8.2 前端

优先级：

1. ConvertView.vue：历史恢复、渲染导出、保存、编辑器协调；
2. RecognizeView.vue：识别任务、批量渲染、历史同步；
3. workspace.ts：页面状态、批次状态、渲染缓存；
4. SyntaxView.vue：语法指南数据和编辑状态；
5. App.vue：布局和全局抽屉。

建议先提取组合函数和纯状态模块，不要先拆模板。每个提取模块必须有独立测试。

## 9. 删除执行规则

每个删除批次必须满足：

1. 删除前记录全仓引用结果；
2. 新增或确认回归测试；
3. 只删除一个逻辑单元；
4. 运行后端测试、前端 typecheck 和工具测试；
5. 再次运行引用扫描；
6. 检查 OpenAPI 是否漂移；
7. 检查 git diff --check；
8. 保留独立提交，避免一次提交混合删除和重构。

禁止以下做法：

- 只因为函数短就删除；
- 只因为测试没有引用就删除公共门面；
- 只通过 grep 判断动态导入或字符串注册点不存在；
- 在解析器重构时同时修改语法；
- 在数据库迁移和前端协议迁移中混入无关删减。

## 10. 推荐执行批次

### 批次 A：零行为风险清理

- 孤立常量；
- 确认无外部 API 后的 re-export；
- 纯委托包装；
- _indent 替换为 ET.indent。

验收：全量后端测试、引用扫描、API 导入兼容测试。

### 批次 B：低风险重复合并

- _tuplet_normal_notes；
- UTF-16 辅助；
- DIATONIC_STEPS；
- A4 常量。

验收：解析/写出 round-trip、UTF-16、渲染 SVG 字符串断言。

### 批次 C：协议与生命周期

- AI/OCR HTTP；
- persisted settings；
- SQLite connection；
- measure number 双字段。

验收：网络失败、流式关闭、并发写入、旧配置迁移、OpenAPI 漂移。

### 批次 D：分层迁移

- domain 文件 I/O；
- MusicXML 修正索引；
- history DAO 拆分。

验收：MXL、XML 安全、纠错结果等价、迁移回滚、性能基准。

### 批次 E：巨型文件拆分

- 先移动、后简化；
- 每次只拆一个职责；
- 不以净删行数作为唯一指标。

## 11. 不建议删除的代码

以下代码虽然较大，但有明确活跃消费者：

- render/jianpu-svg、render/jianpu-text-svg、render/batch-a4；
- PublicationRenderService 门面；
- OCR 文本兼容处理；
- performance_marks.py 的内聚数据目录；
- workspace.ts 的批次状态；
- ConvertView.vue 与 RecognizeView.vue 的核心流程。

这些模块适合拆分，不适合直接删掉。

## 12. 最终判断

项目真正需要的不是“尽可能删除行数”，而是：

1. 先删除 A 级确定孤立代码；
2. 再合并完全相同的纯函数；
3. 把协议兼容代码集中到边界；
4. 把 domain 的文件 I/O 上移；
5. 最后拆分巨型文件。

建议把“净减少多少行”降为次要指标，改用生产引用是否减少、模块依赖是否减少、重复逻辑是否唯一、失败行为是否可观察、测试是否覆盖行为、公共 API 是否保持兼容。

这是本项目从“屎山风险”走向可维护结构的稳妥路径。

## 13. 推荐验证命令

在 Windows Git Bash 中使用仓库本地环境：

~~~bash
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m ruff check backend tests
cd desktop
node_modules/.bin/vue-tsc.cmd --noEmit -p tsconfig.web.json
node_modules/.bin/vue-tsc.cmd --noEmit -p tsconfig.node.json
node_modules/.bin/eslint.cmd --config eslint.config.mjs src/
node_modules/.bin/electron-vite.cmd build
~~~

报告文件本身不应在任何删除批次中被自动改写；每次批次应另行记录变更、测试结果和回滚点。

## 14. 文件级清理审计

### 14.1 当前没有可无条件删除的生产源码整文件

对 backend/score_trans 和 desktop/src 做了文件级引用扫描后，当前没有发现“仓库内零引用且可以无条件删除”的生产源码文件。

几个容易被误判为无用的文件都有实际消费者：

| 文件 | 当前消费者 | 判断 |
|---|---|---|
| services/ocr/client/client.py | 两个 OCR provider 使用 ocr_prompt_for_model | 保留 |
| services/storage/cache_service.py | exec/settings/actions.py 与 tests/test_cache_service.py | 保留 |
| desktop/src/renderer/src/utils/recognitionHistory.ts | RecognizeView.vue 与前端脚本测试 | 保留 |
| desktop/src/renderer/src/models/contracts.ts | models/types.ts 和全部 API adapter | 保留 |
| desktop/src/renderer/src/models/types.ts | API、stores、views、components 大量类型导入 | 保留 |
| services/render/main.py | export、pipeline、tests 使用公开渲染门面 | 保留 |
| domain/jianpu.py | convert、export、AI validation、render、tests 使用 | 保留 |
| domain/musicxml.py | convert、files、recognize、tests 使用 | 保留 |

空的或很薄的 package __init__.py 也不应直接删除。它们影响 Python 包边界、re-export、测试导入和潜在外部调用者；应先确认打包方式和公共 API。

### 14.2 可直接进入“归档/删除候选”的文档

这些不是运行时代码，但会制造过时路线和重复结论：

| 文件 | 当前问题 | 建议 |
|---|---|---|
| docs/jianpu_render_rewrite_design.md | 文档附录已明确说明该旧设计基于已删除的 drawing 架构，当前实际使用 engraving | 保留视觉规范后归档，或删除旧实施章节 |
| docs/project-code-deletion-plan.md | 其中的 OCR client build_request/send_request 删除项已经完成，计划与当前代码不一致 | 将未完成项迁入本报告后归档 |
| docs/code-reduction-audit-2026-08.md | 已被本报告替代，且基线早于当前代码 | 本报告验收后归档旧审计 |
| docs/AUDIT_REPORT.md | 历史审计，包含已被 issues.md 标记为不成立或已修复的结论 | 移到 docs/archive/audit/，不要继续作为当前规范 |
| docs/AUDIT_REMEDIATION_STATUS.md | 实施流水账，适合保留历史证据，不适合作为当前入口 | 归档 |
| docs/AUDIT_VERIFICATION_6.1.md | 旧阶段验证记录 | 归档 |
| docs/AUDIT_VERIFICATION_REPORT.md | 旧阶段验证记录 | 归档 |

归档前必须：

1. 检查 README、development.md、issues.md 和其他文档链接；
2. 给归档文件加明确的历史日期；
3. 只保留一个当前有效的架构文档、问题清单和删减计划。

### 14.3 必须更新、不能直接删除的文档

| 文件 | 已确认的过时内容 |
|---|---|
| docs/architecture.md | 后端约 70 个文件、服务数量和 API 数量已明显落后当前代码 |
| docs/file-by-file.md | 仍写 OCR client 约 78 行、存在 common/env_file.py、RecognizeActions 使用旧 start_measure_number 形态 |
| desktop/AGENTS.md | 仍列出已删除的 MeasureNumberPicker.vue 和 JianpuSyntaxGuide |
| docs/issues.md | 当前权威日期停留在 2026-07-18，部分测试数量和修复基线已变化 |

这些文件被 README 或开发流程引用，正确动作是更新，不是删除。

## 15. 过时或兼容代码审计

### 15.1 当前仍有真实用户价值的兼容代码

以下代码虽然带有 legacy、fallback 或兼容命名，但当前不能删除：

- dao/storage.py 和 models/common/paths.py 的旧用户目录、旧 SQLite、旧上传目录迁移；
- dao/history/history_dao.py 的旧表、旧字段和事务迁移；
- dao/ai/chat_dao.py 的旧 role CHECK 约束迁移；
- services/files/upload_service.py 的旧上传目录迁移；
- services/settings/settings_service.py 的旧工作目录重写；
- exec/render/actions.py 的旧 OCR 文字层合并；
- domain/write/jianpu_text.py 的旧 duration 和 source role 回退；
- API/render/main.py 中 show_measure_numbers 到 measure_number_mode 的兼容转换；
- desktop/main/storageMigration.ts 与 renderer API fallback 连接逻辑。

删除这些代码前必须先定义迁移窗口、版本下限和旧数据拒绝策略。否则“减代码”会变成用户数据不可恢复。

### 15.2 可以在迁移完成后删除的兼容代码

这些是候选，不是立即删除项：

1. show_measure_numbers 双字段兼容：完成 settings、render、pipeline、OpenAPI 和前端迁移后删除；
2. settings DAO 的 obsolete key 清理：确认所有受支持版本已迁移后删除；
3. history v4/v5 迁移分支：确认发布版本最低支持数据库版本后再删除；
4. 旧 OCR 文本格式转换：完成一次性历史数据迁移并加入版本标记后删除；
5. domain/write 中 legacy duration/source role fallback：完成旧历史重写或明确拒绝旧格式后删除。

每项都需要一个明确的“最早可删除版本”，不能只写“以后删除”。

### 15.3 不能凭文件名判断为过时的内容

以下名称看起来像旧代码，但实际仍是注册或公共入口：

- services/ai/providers/_chat.py 通过导入注册 chat provider；
- services/ai/providers/_vision.py 是视觉 provider 基类；
- services/ocr/providers/_http.py 是 OCR provider 的请求实现；
- services/render/options.py 仍被 render/main.py 和 render_service.py 使用；
- models/openapi.ts 是生成文件，不能手工删除；
- models/types.ts 是稳定重导出层，不能因为 contracts.ts 存在就删除。

## 16. 文件级执行顺序

### 第一阶段：只处理文档和明确孤立符号

1. 归档已被新设计取代的旧渲染设计文档；
2. 归档旧审计流水账；
3. 更新 architecture.md、file-by-file.md、desktop/AGENTS.md；
4. 删除已确认的孤立常量和纯委托包装；
5. 每个提交后运行全量测试和引用扫描。

### 第二阶段：处理兼容边界

1. 先为每个兼容分支增加版本/数据迁移测试；
2. 定义最低支持版本；
3. 只删除已经超过迁移窗口的分支；
4. 同步更新 OpenAPI、历史 schema 和用户文档。

### 第三阶段：处理整文件拆分

1. 先拆巨型文件，不删除行为；
2. 移动后确认生产引用和测试引用不变；
3. 再删除重复包装和无消费者私有函数；
4. 最后才考虑合并公共模块。

文件级清理的验收标准是“删除后仍能解释每个入口、每份历史数据和每条公共契约”，而不是单纯减少文件数量。

## 17. 本次执行结果

本次已实际完成以下低风险清理：

- 删除 3 个明确被新报告/新架构取代的旧文档：旧代码删减审计、旧代码删除计划、旧 drawing 架构渲染重写设计；
- 重写 docs/file-by-file.md 为当前目录索引；
- 更新 architecture.md、issues.md、desktop/AGENTS.md 和布局方案中的过时事实与链接；
- 删除无生产引用的常量、HTML 输出门面、单数 MusicXML 路径门面、OCR 小节号孤立函数；
- 删除 4 个纯委托包装函数；
- 删除 domain/xml_utils.py 手写缩进，改用标准库 ET.indent；
- 合并三份 _tuplet_normal_notes，并集中 DIATONIC_STEPS；
- 新增 tests/test_code_reduction.py，覆盖共享连音组行为和已删除符号不再暴露。

本次验证：

- 后端全量测试：547 passed, 1 skipped；
- 前端工具测试：55 passed；
- Vue web/node typecheck：通过；
- Electron/Vue production build：通过；
- 本批涉及 Python 文件 Ruff check：通过；
- git diff --check：通过。

全仓 Ruff 目前仍报告原有的 224 个问题，主要集中在未参与本批次的 API 路由、测试导入排序和历史代码风格；本批次没有为了追求 lint 数字而大范围改动无关代码。
