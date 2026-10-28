# 开发环境搭建

本文档面向希望参与 Score Trans 开发或自行构建的开发者。

---

## 仓库结构

```text
backend/score_trans/
  api/          FastAPI 路由层：只声明 HTTP 接口并委托 exec
  exec/         执行层：识别、转换、渲染、导出、历史、设置等业务编排
  services/     服务层：文件、渲染、OCR、外部工具等可复用服务
  dao/          数据访问层：SQLite 建表、迁移、查询和 row mapping
  models/       数据参数层：DTO、配置、实体、简谱结构模型
  domain/       纯简谱/MusicXML 算法入口，不做 I/O
desktop/        Electron + Vue3 桌面前端
docs/           文档
third_party/    外部工具源码（Audiveris）
tests/          Python 测试
```

### 架构约束

导入权限（禁止反向导入）：

- `api/` 可导入 `exec/`、`models/`、`config/`
- `exec/` 可导入 `services/`、`models/`、`config/`、`utils/`
- `services/` 可导入 `dao/`、`domain/`、`models/`、`config/`、`utils/`
- `dao/`、`domain/` 可导入 `models/` 和 `utils/`
- `models/` 不能导入任何项目模块

架构测试在 [`tests/test_architecture.py`](../tests/test_architecture.py) 中强制执行。另外注意：**`exec/` 层禁止新增 `HTTPException` 导入**，这是已知的技术债务；新代码请使用标准异常并在 `api/` 路由中转换。

---

## Python 后端

### 环境要求

- Python 3.11、3.12 或 3.13
- [uv](https://docs.astral.sh/uv/) 包管理器（推荐）
- JDK 25（Audiveris 必需）

### 安装依赖

```powershell
uv venv .venv --python 3.13
uv pip install -e ".[test]" --python .venv\Scripts\python.exe
```

### 启动后端开发服务器

```powershell
$env:PYTHONPATH="backend"
$env:SCORE_TRANS_API_TOKEN="replace-with-a-random-token-at-least-32-characters"
.venv\Scripts\python.exe -m uvicorn score_trans.api.app:create_app --factory --reload --host 127.0.0.1 --port 19200
```

> 注意：原 README 中的 `$env:PYTHONPATH="src"` 已过时，应使用 `backend`。
> 独立启动后端时必须设置至少 32 字符的 token；仅测试可显式设置
> `SCORE_TRANS_API_AUTH_DISABLED=1`。Electron 正常启动时会自动生成随机 token。

### 运行测试

```powershell
# 全部测试
python -m pytest

# 使用项目虚拟环境
.venv\Scripts\python.exe -m pytest

# 单独运行敏感测试（SVG 断言较脆弱）
python -m pytest tests/test_render.py
python -m pytest tests/test_architecture.py
```

### 格式化与 Lint

```powershell
.venv\Scripts\python.exe -m ruff format backend/ tests/
.venv\Scripts\python.exe -m ruff check --fix backend/ tests/
```

---

## Electron / Vue 前端

### 环境要求

- Node.js 18+
- pnpm

### 安装依赖

```powershell
cd desktop
pnpm install
```

### 启动开发环境

```powershell
cd desktop
$env:VITE_BACKEND_URL="http://127.0.0.1:19200"
$env:VITE_BACKEND_TOKEN=$env:SCORE_TRANS_API_TOKEN
pnpm dev
```

Electron 会自动启动 FastAPI 后端（需要 `.venv` 已存在并配置正确）。

### Lint 与类型检查

```powershell
cd desktop
pnpm lint
npx vue-tsc --noEmit
```

---

## 常用 API 端点

开发或调试时可以直接请求后端接口：

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/files/upload` | 上传输入文件，返回 `file_id` |
| POST | `/files/{file_id}/rotate` | 将图片旋转 90°（`left` / `right`），返回新的 `file_id` |
| POST | `/recognize` | 图片/PDF → MusicXML |
| POST | `/convert/musicxml-to-jianpu` | MusicXML → 简谱文本 |
| POST | `/convert/jianpu-to-musicxml` | 简谱文本 → MusicXML |
| POST | `/render/jianpu-svg` | MusicXML → 简谱 SVG |
| POST | `/pipeline` | 一键完成识别 + 转换 + 渲染 |
| POST | `/ai/transcribe` | 图片/PDF → AI 简谱草稿 |

完整 OpenAPI 文档在启动后端后访问：`http://127.0.0.1:19200/docs`

---

## 构建桌面安装包

打包仅在 CI 中运行，入口为 `.github/workflows/package.yml`。详见
[打包指南](packaging.md) 和 [`pyinstaller.spec`](../pyinstaller.spec)。

---

## 提交规范

使用中文 conventional commits：

- `feat: 添加XXX功能`
- `fix: 修复XXX`
- `refactor: 重构XXX`
- `docs: 更新文档`
- `test: 添加测试`

---

## 更多文档

- [架构说明](architecture.md)
- [文件索引](file-by-file.md)
- [环境变量参考](environment.md)
- [简谱语法](jianpu-syntax.md)
- [已知问题与路线图](issues.md)
