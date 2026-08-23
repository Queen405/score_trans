# Ruff 后端 Python 代码质量调研报告

> **日期**：2026-08-24
> **方式**：3 个并行调研单元（安全正确性深查 / 风格复杂度分析 / 配置方案实测设计），全部结论基于 ruff 实际运行输出 + 逐条人工读码判定，未修改任何仓库文件。
> **范围**：`backend/score_trans`、`tests/`、`scripts/`、`build-app.py`、`pyinstaller_entry.py`（共 ~270 个 .py 文件）。
> **关键前提**：pyproject.toml 目前**没有任何 `[tool.ruff]` 配置**——lint 走 ruff 内置默认规则集（E4/E7/E9/F），CI 固定 `uvx ruff@0.15.22`，本地 venv 为 0.16.4。

---

## 一、基线现状（已亲自复核仲裁）

| 检查项 | 命令 | 结果 |
|---|---|---|
| CI lint 门禁 | `uvx ruff@0.15.22 check ...`（默认规则） | ✅ **All checks passed（0 错误）** |
| 本地 venv 同命令 | `0.16.4 check`（默认规则） | ⚠️ **185 个错误** —— 纯版本行为差异，非代码退化 |
| CI format 门禁 | `uvx ruff@0.15.22 format --check` | ❌ **4 个文件需重排**：`domain/write/jianpu_text.py`、`services/recognize/external_tools.py`、`services/render/__init__.py`、`engraving/style.py` |
| 全规则普查 | `select=ALL, preview=false` | **7810 条**（理论天花板，绝大多数不适用） |
| 扩展规则集 | E,F,W,I,N,UP,B,A,C4,T20,DTZ,EM,RET,SIM,ARG,PTH,PL*,RUF,S,PT,TC | **~202 条有效发现** |

### 三个必须先知道的真相

1. **"CI lint 全绿"是版本锁定的功劳，不是代码干净**。换成本地新版 ruff 立刻冒出 185 个错误。两版在默认规则下就有行为分歧（BLE001/S310 等 ±5 条），当前处于"本地绿 CI 红 / CI 绿本地红"随时翻转的状态。
2. **format 门禁的漂移根因是混合行尾**：仓库无 `.gitattributes` 且 Windows 下 `core.autocrlf=true`，WIP 文件出现 CRLF/LF 混块时 formatter 按"主导行尾归一化"报警。全仓统一行尾的文件不受影响。
3. **`.ruff_cache` 会返回过期结果**：曾缓存出 2×F821 + 1×F841 的幽灵错误，`--no-cache` 下为 0。CI 无缓所以权威；本地排查务必带 `--no-cache`。

---

## 二、安全与正确性类发现逐条研判（重点）

> 结论总表：扩展扫描中真正值得关注的**正确性问题只有 2 处**（B905 zip 截断风险 ×1、RUF006 测试悬空任务 ×1），其余全部为误报/惯用法/已缓解。

| 规则 | 数量 | 真阳性 | 判定摘要 |
|---|---:|---:|---|
| S314 xml.etree | 34 | 1（已缓解） | 生产侧唯一解析出口 `utils/safe_xml.py:56` 防护完备（DOCTYPE 默认拒绝、Recordare DTD fullmatch 白名单、禁内部子集防 XXE/实体攻击、64MB 上限防 zip-bomb）；其余 33 处全是 tests 自造数据。建议加 `# noqa: S314` 说明性豁免并保留规则拦截未来裸解析 |
| S608 SQL 拼接 | 13 | **0** | 全部为常量表名/列名拼接 + 值走 `?` 参数化（settings_dao TABLE_NAME ×10、history_dao 列元组 join 等）。无注入面。history_dao 的 f-string 字段名循环属"脆弱模式"，建议加注释固化约束 |
| S105 hardcoded-password | 3 | 0 | 全误报：音乐记号变量 `"n"`、测试假 token、字段名撞车 |
| S603 subprocess | 3 | 提示级 | 全部 list 参数 shell=False；Audiveris 参数含用户可配置 extra_args/constants（单机桌面威胁模型可接受，多用户化前需收敛）；heap 参数已有白名单校验 |
| B019 lru_cache 方法 | 3 | 条件性误报 | `fonts.py:54,58,106` 三方法挂 lru_cache——因 FontRegistry 是模块级单例永生，**现无泄漏**；但任何第二个实例化点（如测试直建）即变真泄漏，建议加单例注释或改模块级函数 |
| RUF006 悬空任务 | 1 | 半真 | 生产侧 `exec/tasks/background.py:28-30` 正确持引用✅；唯 `tests/test_tasks.py:44` 的 create_task 未存引用，可能被 GC——一行修复 |
| PLW 系列 | ~10 | 1 | PLW2901×2 是 in-place 清洗惯用法；PLW3301×4 是 clamp 风格；PLW0603 global×3 是惰性单例；PLW0108 lambda 可 autofix |
| B905 zip 无 strict | 2 | **1 真** | `domain/write/jianpu_text.py:513`：`zip(sources, marks)` 两列表来自独立去重增长路径，无等长保证 → 不等长时**静默截断**，部分 anchor 缺失导致 SVG 点击定位降级。真实数据完整性缺陷，建议 strict=True + 兜底或按 index 配对（geometry.py:99 处为恒等长，补 strict 固化不变量即可） |
| UP035 弃用导入 | 2 | 2 | `typing.Callable`（registry.py:3）、`typing.Mapping`（scene.py:5）→ 改 `collections.abc.*`，autofixable |
| DTZ 时区 | 0 | — | **人工确认真干净**：backend 无任何 datetime.now/utcnow/fromtimestamp；时间存储用 time.time() epoch（UTC 本质），SQL localtime 仅作展示。建议把 DTZ 纳入门禁锁定现状 |
| B008 Depends 默认值 | ~68 | 0 | FastAPI 官方惯用法，须用 `extend-immutable-calls` 豁免（见第四节配置） |

---

## 三、风格与复杂度治理分析

### 3.1 结构性误报（应全局 ignore）

- **RUF001/002/003 歧义 Unicode（405 条）**：字符级聚合后仅 10 种字符，100% 为中文全角标点（，：（）；！？''）+ 2 处乐谱弓法符号 `∨`（up-bow 记号映射表的功能性内容）。**无任何同形字母攻击混入**。直接 ignore，或改用 `allowed-confusables` 白名单保留防同形攻击能力。
- **EM101/EM102 异常消息格式（248 条）**：该规则的动机是惰性求值便于 APM 渲染 traceback，本项目是进程内桌面应用异常，中文 f-string 消息是刚需。ignore。
- **E501 行长（109→113 条）**：主因不是中文注释（仅 12 条），而是 history_dao 的 SQL DDL 占位符串与长 URL——不可断行。选择：formatter 保持 88 不动，E501 单独 `max-line-length = 110`（残余 12 条 noqa）或直接 ignore（残余为纯字符串字面量）。
- **PLC0415 函数内延迟导入**：30 处规避循环依赖的既定手法，分层由 test_architecture.py 把关。ignore。
- **PLR0917** 与 PLR0913 完全重叠上报，二选一即可。

### 3.2 应启用并修复的真问题

| 规则 | 数量 | 说明 |
|---|---:|---|
| I001 导入排序 | 66 | 抽验 3 处 diff 语义安全（无 TYPE_CHECKING 块、无环境变量顺序依赖配对），**可无脑 `--fix`** 后跑 pytest 回归 |
| SIM118 dict.keys() | 23 | 全部集中在 history_dao.py 单文件，机械修 |
| ARG 未用参数 | 104 | 三分类：8 处 api/app.py 异常处理器签名占位（per-file-ignore）、88 处 tests 替身占位（per-file-ignore）、**8 处 engraving 真实死参**（`_route_spanners(left,right)` 等，随 renderer 模块拆分清理） |
| TC001-003 仅类型导入 | 196 | ⚠️ **禁止盲目 autofix**：15 个 Pydantic schemas 的注解运行时求值，import 移入 TYPE_CHECKING 会炸模型构建。必须先配置 `runtime-evaluated-base-classes = ["pydantic.BaseModel"]` 再启用，且只在 service/domain 层人工应用 |
| PT/RUF043 pytest 风格 | ~26 | RUF043 的 match 正则歧义是真问题（7 处手工转义）；PT017 except 内 assert 掩盖断言错误（4 处改 pytest.raises） |
| SIM105/SIM300/RET504/C420 | ~15 | 量小皆真改进，SIM105 有 unsafe-fix 手工套 contextlib.suppress |

### 3.3 复杂度热点 Top 10（重构优先级）

| # | 位置 | 信号 | 优先级 |
|---|---|---|---|
| 1 | `domain/parse/jianpu_text.py::parse_jianpu_score` @L559 | 分支 31、语句 183 | **P0**：全仓最复杂函数，简谱解析主入口，按语法元素拆状态机 |
| 2 | `domain/parse/musicxml.py::_read_measure_events` @L425 | 分支 27、语句 111 | **P0**：按 event 类型拆 handler 分发表 |
| 3 | `models/score.py::__init__` @L152 | **21 个参数手写 __init__** | P1：改 `@dataclass(slots=True)` 一行消除两类告警（项目标准做法） |
| 4 | `jianpu_text.py::_parse_tuplet_token` @L1047 / `_read_new_syntax` @L849 | 分支 20/21 | P1 |
| 5 | `services/render/render_service.py` 全文件 | 8 个函数全是 9 参透传 | **P1**：引入 RenderRequest 参数对象收益最大 |
| 6 | `engraving/renderer.py`（2276 行） | 18×超参 + 11×位置超限 | P1："宽而不深"，按 system/spanner/glyph 切模块 |
| 7 | `exec/settings/actions.py::update_settings` @L46 | 分支 27 | P2：字段分组循环化 |
| 8 | `dao/history/history_dao.py::_migrate_db` @L606 | 分支 24 | P2：迁移步骤表驱动化 |
| 9 | `jianpu_text.py::parse_jianpu_parts` @L399 | 语句 67 | P2 |
| 10 | history 层 update_page（service+dao 各 20 参） | 超参 | P2：引入 DTO |

> 对照已知大文件的修正认知：复杂度核心是 `jianpu_text.py` 与 `musicxml.py`，而 `exec/render/actions.py`（1281 行）控制流其实健康、`renderer.py` 是参数宽而非逻辑深。

---

## 四、推荐配置（已实测验证，可直接粘贴 pyproject.toml）

```toml
[tool.ruff]
target-version = "py311"
line-length = 88            # formatter 基准不动：改 100 会触发 106 文件一次性重排
preview = false             # 只吸收稳定规则
src = ["backend"]           # 否则 score_trans 被误判第三方库

[tool.ruff.lint]
select = [
    "E", "W", "F", "I", "N", "A", "DTZ", "G",
    "UP", "B", "C4", "SIM", "RUF",
    "S", "PTH", "TRY",
    "PLE", "PLW", "PLC", "ARG", "T20", "BLE",
]
ignore = [
    "RUF001", "RUF002", "RUF003",   # 中文全角标点结构性误报（~405 处）
    "EM101", "EM102", "EM103",      # 中文 f-string 异常消息是项目风格
    "TRY003",                        # 同上
    "E501",                          # 残余全是不可断行字符串字面量（LL=88 下 63 处）
    "PLC0415",                       # 延迟导入是既定解耦手法
]

[tool.ruff.lint.flake8-bugbear]
# FastAPI DI 惯用法精确豁免：真正的可变默认参数仍会被揪出
extend-immutable-calls = [
    "fastapi.Depends", "fastapi.Query", "fastapi.Path", "fastapi.Body",
    "fastapi.Header", "fastapi.Cookie", "fastapi.File", "fastapi.Form",
]

[tool.ruff.lint.pylint]
max-args = 10        # 先止血，热点重构后再收紧回 6

[tool.ruff.lint.per-file-ignores]
"tests/**" = [
    "S101", "S105", "S106",         # assert 与假凭据是测试本职
    "S314", "S608",                 # 自造 XML/SQL 无注入面
    "SLF001",                       # 白盒测试访问私有成员
    "ARG001", "ARG002", "ARG005",   # fixture/替身签名占位
    "INP001", "PLR2004",            # 无 __init__；断言魔数即被测对象
]
"build-app.py" = ["T201", "S603", "PLR2004"]
"scripts/**" = ["T201", "INP001"]
```

**实测效果**（沙盒验证）：引入前 202 条 → `--fix` 自动修 86 条（I001×72 等）→ **剩余 118 条全部为值得人工处理的真实项**（SIM118×23 机械修、ARG×16 改名 `_xxx` 即消、S608×13 已判定安全形态、BLE001×12 逐个确认收窄、B019×3 加单例注释等）。autofix 后 pytest 回归通过。

**暂缓启用的规则**（Phase 3 再说）：TC 系列（先配 `runtime-evaluated-base-classes = ["pydantic.BaseModel"]`）、ANN 子集、C901、FBT、FAST002。

---

## 五、分阶段落地路线

| 阶段 | 内容 | 工作量 |
|---|---|---|
| **1 清欠** | ① 重排 4 个漂移文件（`ruff format` 上述清单）；② 新增 `.gitattributes`（`* text=auto eol=lf`）根治混合行尾——这是 format 门禁反复飘红的根因 | ~30 分钟 |
| **2 引入配置** | 粘贴第四节 TOML → `--fix` 收割 86 条 safe fix → pytest 回归 → 剩余 118 条按第二节判定消化（约 60% 是 10 分钟级机械修） | 半天 |
| **3 加严** | TC（Pydantic 安全前提）、ANN 子集、max-args 收紧回 6、随 renderer/jianpu_text 重构逐档收紧 PLR09xx | 每子项独立 PR |

## 六、版本收敛策略（必须做，否则门禁不可信）

本地 venv 0.16.4 与 CI 0.15.22 实测存在行为分歧（同配置净差 5 条：BLE001 多 4、S310 少 1）。三管齐下：

1. **升级 CI pin 至 0.16.x**（`.github/workflows/ci.yml` 的 `uvx ruff@0.15.22`），更彻底的做法是把 ruff 列入 dev 依赖走 uv sync 单一事实源；
2. **加保险丝**：配置 `required-version = ">=0.16,<0.17"`——旧版本会显式报错而非静默给出不同结果；
3. **format 用精确锁**（`==0.16.*`）：0.x 阶段 formatter 样式可能随 minor 变化，升级必须是显式动作并重跑 format --check。
