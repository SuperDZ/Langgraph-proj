# AgentLoop Platform

基于 LangGraph 的多 Agent 研发交付平台：把「需求 → 研发 → 质量门禁 → 发布」串成一条受控、可追溯、可回滚的流水线，并附带本机管理控制台与事件回放工作台。

> 仓库目录名 `Langgraph-proj`；Python 包名 `agentloop-platform`（v0.5.0）。

## 能力概览

- 多角色协作子图：产品、前置专家、研发、测试、代码审查、安全审查。
- 确定性状态机 + SQLite 仓储与审计：状态可跨进程恢复，每次决策有迹可循。
- 人工门禁：需求确认、发布授权、安全整改返工等由真人显式确认。
- 隔离 Worktree、发布执行器、人工范围许可、回滚与对账。
- 长期记忆治理：复盘、记忆审批 / 撤销 / 回滚，可信证据约束的 Skill 演进。
- 逐角色模型配置与后备链、预算、Skills 隔离导入与 MCP 工具授权。

## 目录结构

```
src/agentloop/              # 平台主实现
├── core/                   # 契约、编排（SQLite）、审批 RBAC、运行时
├── knowledge/              # 长期记忆治理、原始证据复盘
├── examples/               # 可复现脚本角色（离线验证）
├── *_cli.py                # phase2 / phase3 / phase4 命令行入口
└── tests/                  # 单元与集成回归
frontend/                   # 两个本机界面 + 本地服务
├── server.py               # 本机 HTTP 服务（仅回环监听，Host/Origin/CSRF 校验）
├── platform_api.py         # 运行、门禁、复盘、模型设置接口
├── agent_settings.py       # 逐角色模型参数与配置快照
├── credentials.py          # 加密凭据库
├── index.html              # 交付工作台 / 事件回放工作台（原生页面）
├── workbench.js / *.css    # 工作台脚本与样式
└── console/                # React 管理控制台 + Tauri 桌面客户端
docs/                       # 阶段说明与验证记录
notes/                      # 需求规格说明书
src/week1/  src/week2/      # 学习对照版本（见文末）
```

## 环境要求

- Python 3.11+
- Node.js（仅在构建控制台前端时需要）
- JDK 与 Maven（可选）：仅在需要跑内置 Spring 演示的真实测试时提供

## 快速开始

### 1. 安装

在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
```

### 2. 配置

复制模板并按需填入模型服务商的 API Key：

```powershell
Copy-Item .env.example .env
```

`.env` 中只保存模型凭据引用（`env:..._API_KEY`），密钥本身不进仓库。

### 3. 构建控制台前端（首次检出）

```powershell
cd frontend/console
npm ci
npm run build
cd ../..
```

### 4. 启动服务

```powershell
.\.venv\Scripts\python.exe frontend/server.py
```

可选参数：

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--port` | `8438` | 监听端口（仅回环地址） |
| `--data-dir` | `.agentloop/workbench` | 运行状态、交付产物与证据目录 |
| `--java-home` | 空 | JDK 目录；提供后演示可用真实 Maven 测试 |
| `--maven` | 空 | Maven 可执行文件路径（如 `mvn.cmd`） |

### 5. 访问

- 研发控制台：<http://127.0.0.1:8438/console/>
- 交付工作台：<http://127.0.0.1:8438/workbench>

## 两个界面

| 维度 | 研发控制台 `/console/` | 交付工作台 `/workbench` |
| --- | --- | --- |
| 技术栈 | React + Vite（可打包为 Tauri 桌面客户端） | 原生 HTML / CSS / JS |
| 定位 | 操作与控制：新建交付、门禁审批、模型 / 凭据 / 技能配置、成本审计 | 可视化与回放：按时间轴回看角色协作、门禁与产物 |
| 数据来源 | 实时轮询 `/api/platform` | 实时状态 + 载入导出的证据 JSON 离线回放 |

两页互相链接：控制台侧边栏可跳转工作台，工作台顶部面包屑可返回控制台。

## 命令行

```powershell
# 交付流程（离线演示，可指定数据目录与 JDK/Maven）
.\.venv\Scripts\python.exe -m agentloop phase1-run --run-id <id> [--java-home <jdk>] [--maven <mvn>]

# 复盘与长期记忆治理
.\.venv\Scripts\python.exe -m agentloop phase4-retrospect --run-id <id>
```

各阶段子命令与验收边界见 `docs/phase*-runtime.md`。

## 本地状态与敏感文件

以下路径已在 `.gitignore` 排除，**请勿提交**：

| 路径 | 内容 |
| --- | --- |
| `.env` | 模型 API Key 等本地配置 |
| `.agentloop/` | SQLite 状态库、加密凭据、交付产物、本机工具链 |
| 凭据文件（`*.dpapi` / `credentials.fernet` / 密钥文件） | 加密凭据及其解密密钥 |
| `frontend/console/node_modules/`、`dist/`、`**/target/` | 前端依赖、构建产物、Rust / Maven 编译缓存 |
| `output/`、`.slidep/` | 截图、演示工具本机状态 |

模型凭据仅以 `env:..._API_KEY` 引用；控制台保存的密钥经服务端加密后落盘，SQLite、审计记录与 HTTP 响应均不含明文。

## 安全边界

- 服务仅监听 `127.0.0.1` 回环地址，不对外暴露。
- 身份为本地演示身份，不是真实认证。
- 测试真实执行；发布默认关闭或仅本地模拟，生产发布禁用。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

`testpaths` 覆盖平台主实现与 week2 学习版本；带 `java_integration` 标记的真实 Maven / Spring 集成测试默认不运行，需显式启用。

## 学习对照版本（week1 / week2）

`src/week1`（手写 Agent Loop）与 `src/week2`（LangGraph 重构）是两个历史学习实现，用于对照理解「手写循环 + 工具分发器」与「LangGraph 图 + ToolNode」的差异，属于教学材料，不在主平台演进范围内。
