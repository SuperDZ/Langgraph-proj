# Langgraph-proj

基于 LangGraph 的 Java 故障排查学习项目：**输入报错信息，按需查询示例日志和本地源码，生成结构化故障分析及任务分配建议。**

**当前阶段：week2 的 LangGraph 双 Agent 流程已实现，具备离线验证代码；真实模型端到端效果尚未在本次核查中验证。** 程序通过命令行输出结果，尚未接入真实日志平台、人员系统或工单系统，也不会自动修改源码。

进度核查日期：2026-10-18。下述状态以当前工作区代码与本次验证为依据，不代表线上部署状态。

同一套业务流程用两种技术实现了两遍，作为对照学习：

| 阶段 | 技术路线 | 说明 |
| --- | --- | --- |
| week1 | OpenAI SDK 手写 Agent Loop | 手写 `while` 循环 + 工具分发器 + 手写 JSON Schema |
| week2 | **LangGraph 重构** | 用图的边表达循环，工具交给 `ToolNode`，输出用 Pydantic 校验 |

---

## 当前进度

### week1：手写 Agent Loop（历史实现，保留作对照）

在 `main.py` 中先调用日志分析 Agent，再把结果传给团队 Leader Agent；外层未使用 LangGraph。

- Agent 内部手写 `while` 循环驱动工具调用，上限 8 轮
- 工具参数 JSON 非法或工具执行失败时抛出异常，中断流程
- `search_code` 递归搜索 Java 文件，返回命中文件路径和文件全文
- 结构化输出靠手写 JSON Schema + 解析前清理 markdown 代码块
- 模型调用使用 OpenAI SDK 的 `responses.create`，客户端指向 DeepSeek；week2 测试不覆盖该历史版本，其在线兼容性未在本次验证

### week2：LangGraph 重构（当前主实现）

- **外层图**：`workflow.py` 固定业务顺序 `START → log_reviewer → team_leader → END`
- **内层图**：`agent_runner.py` 用条件边实现 Agent Loop
  ```
  model ──有工具调用──> tools ──> model
     └──无工具调用──> finalize(生成并校验 JSON) ──> END
  ```
- 三个工具改用 `@tool` 装饰器，参数说明自动生成，交给 `bind_tools` 和 `ToolNode`
- `add_messages` 累积历史，工具结果以带调用 ID 的 `ToolMessage` 返回，一轮可执行多个工具
- 结构化输出用 `with_structured_output(method="json_mode")` + Pydantic 校验字段、列表长度、confidence 范围
- **固定检索根目录**：Agent 中的 `search_code` 只向模型暴露 `keyword`，`src_base` 由程序绑定；这不等同于操作系统级文件访问隔离
- **成员白名单**：Leader 分配前必须成功查询成员，程序拒绝分配给工具从未返回过的人
- **按需创建模型**：模型只在运行时构造，导入模块和离线测试不需要 API Key
- **异常处理**：未知工具、缺少必填参数及工具执行异常通过 `ToolMessage` 回传；非法工具调用 JSON、轮数耗尽、结构化结果校验失败会抛出异常
- **轮数限制**：每个 Agent 默认最多 8 次工具决策模型调用，包含最终不调用工具的一轮；生成结构化结果会额外调用模型一次
- **离线测试**：脚本模型驱动真实 LangGraph 和本地工具，并使用 HTTP 模拟传输检查 ChatDeepSeek 适配器；详见下方验证记录

详细说明见 [`src/week2/README.md`](src/week2/README.md)。

### 能力与边界

| 能力 | 当前状态 | 代码依据与实际边界 |
| --- | --- | --- |
| 日志分析 → 团队分配 | 已实现 | `src/week2/group/workflow.py` 固定串联两个 Agent |
| 日志补全 | 示例实现 | `tool_getFullLog.py` 只查询内置的两个服务日志；未接入外部日志源 |
| 源码检索 | 已实现基础版本 | `tool_searchCode.py` 按文件名或内容进行不区分大小写的关键词匹配，仅搜索 `*.java`；返回全文，无行号、片段裁剪和结果数量上限 |
| 故障分析输出 | 已实现格式校验 | `schemas.py` 校验字段、额外字段、列表长度及置信度范围；不验证根因结论是否正确，置信度也不是实测准确率 |
| 成员查询与校验 | 示例实现及程序约束 | `tool_getTeamMembers.py` 内置三个团队；`team_leader.py` 检查查询成功及姓名是否属于查询结果，不校验技能匹配质量 |
| 任务交付 | 仅输出建议 | `main.py` 打印分配结果；未发送消息、创建工单或跟踪处理状态 |
| 会话与持久化 | 未实现 | `add_messages` 仅累积本次 Agent 执行消息，未配置 checkpointer、数据库或跨会话记忆 |
| 自动修复 | 未实现 | 无源码写入、patch 生成、编译或修复后回归流程 |
| 服务化与运行观测 | 未实现 | 当前入口为同步 CLI，未提供 HTTP API、流式界面、持久化执行记录或 CI 配置 |
| 真实模型端到端验证 | 本次未执行 | 离线测试不能证明密钥、所选模型、外部网络或诊断效果可用 |

### 建议的下一步（尚未实施）

1. **验证真实模型链路**：用已知故障样例执行 week2，确认工具调用、JSON 输出和任务分配，并记录结果、耗时及失败原因。
2. **控制检索上下文规模**：增加命中行号、上下文片段和返回数量/长度上限，避免大型 Java 仓库的文件全文占满模型上下文。
3. **替换示例数据源**：为日志与成员查询接入真实只读接口，明确未命中、超时与权限不足的返回约定。
4. **建立诊断评估集**：用有明确根因和责任团队的样例评价诊断及分配效果，再按需求增加持久化、人工复核和工单集成。

---

## 快速开始

以下命令在项目根目录执行，使用 Python 3.11 虚拟环境。依赖版本范围见 `src/week2/requirements.txt`，当前未提供锁文件。

```powershell
# 1. 创建虚拟环境（已有 .venv 时跳过创建），安装依赖
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r src/week2/requirements.txt

# 2. 配置密钥
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 3. 运行
.\.venv\Scripts\python.exe src/week2/group/main.py
```

也支持模块入口与自定义参数：

```powershell
.\.venv\Scripts\python.exe -m src.week2.group.main
.\.venv\Scripts\python.exe src/week2/group/main.py --log "UserService 启动失败" --src-base "D:/your-project" --max-rounds 8
```

Linux/macOS 使用 `.venv/bin/python`，复制配置使用 `cp .env.example .env`，已有 `.env` 时直接编辑。

配置从项目根目录 `.env` 加载；已有进程环境变量优先。`DEEPSEEK_API_KEY` 必填，`DEEPSEEK_MODEL` 可选，代码回退值是 `deepseek-chat`；当前 `.env.example` 填写的是 `deepseek-v4-flash`，复制后会使用该配置值。本次未验证这些模型名称的在线可用性；运行时所选模型需支持工具调用与 JSON 输出。

默认源码目录是 `src/week2/test/test_codebase`，通过入口文件位置定位，不依赖启动目录。`--src-base` 可指定自己的 Java 仓库，相对路径以启动目录为基准。

程序分别打印 `log_analysis` 和 `task_assignment`。前者包含 `error_type`、`root_cause`、`possible_causes`、`confidence`、`suggestions`；后者包含 `task_assignments`，每项为 `team_member` 和 `task_description`。`run_workflow` 的返回值还包含输入日志及解析后的源码根目录。

### 运行离线测试

```powershell
.\.venv\Scripts\python.exe -m pip install -r src/week2/requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest src/week2/test -q
```

现有测试包含 **15 个测试函数、参数化后 21 个场景**（按测试源码静态统计）。测试设计覆盖真实工具执行、双 Agent 数据衔接、多工具调用与调用 ID、固定源码目录、工具异常、无工具调用结束、轮数上限、非法结构化输出、成员白名单、延迟创建模型及 DeepSeek 请求格式。测试使用脚本模型和 HTTP 模拟传输，不调用真实模型 API。

### 本次核查记录（2026-10-18）

| 检查 | 结果 |
| --- | --- |
| 核查运行环境 | 项目 `.venv` 使用 Python 3.11.15，初始仅安装 pip 与 setuptools |
| Python 语法检查 | 使用 Python 3.11.15 解析全部 25 个 Python 文件，均通过；不代表导入、运行或业务逻辑验证通过 |
| 离线测试执行 | 启动 pytest 时提示 `No module named pytest`，未获得测试通过或失败结果 |
| 测试依赖安装 | 已尝试安装 `requirements-dev.txt`；下载持续缓慢后中止，依赖安装未完成，需完成安装后重跑上述命令 |
| 真实模型 API | 本次未调用，未验证在线可用性及诊断质量 |

---

## 目录结构

```
src/
├── week1/                      # 手写 Agent Loop 版本
│   ├── group/
│   │   ├── main.py             # 顺序调用两个 Agent
│   │   ├── client_manager.py   # OpenAI SDK 客户端
│   │   ├── agents/             # agent_runner / log_reviewer / team_leader / tool_execute
│   │   └── tools/              # 三个工具函数 + 手写工具注册表
│   └── test/test_codebase/     # 供检索的 Java 示例代码库
│
└── week2/                      # LangGraph 版本（当前主实现）
    ├── README.md               # 详细设计与运行说明
    ├── requirements.txt        # 运行依赖
    ├── requirements-dev.txt    # 测试依赖
    ├── group/
    │   ├── main.py             # 命令行入口
    │   ├── workflow.py         # 外层图：两 Agent 衔接
    │   ├── client_manager.py   # 延迟创建 ChatDeepSeek
    │   ├── schemas.py          # Pydantic 输出模型
    │   ├── agents/             # 内层图（通用 Agent Loop）+ 两个业务 Agent
    │   └── tools/              # 三个 @tool 装饰的工具
    └── test/
        ├── test_workflow.py    # 离线测试，包含参数化场景
        └── test_codebase/      # 同 week1 的 Java 示例代码库
```

---

## 从 week1 到 week2 学到了什么

| 维度 | week1（手写） | week2（LangGraph） |
| --- | --- | --- |
| 工具定义 | 手写 JSON Schema + if/else 分发器 | `@tool` 装饰器自动生成 |
| Agent 循环 | 手写 `while` + 计数器 | 条件边 `tools_condition` |
| 循环上限 | 自己判断轮数 | 图的 `recursion_limit` + 状态计数 |
| 消息历史 | 手动 append 到 list | `add_messages` 自动合并 |
| 输出格式 | 手写 schema + 清理 markdown | JSON 模式生成，Pydantic 本地校验；不是服务端严格 schema 保证 |
| 源码目录约束 | 通过 prompt 指定目录 | `src_base` 由程序绑定，不作为 Agent 工具参数 |
| 工具异常 | 抛出异常，中断流程 | 执行异常回传模型；非法调用 JSON 等情况仍会中断 |
| 可测试性 | 客户端在导入时创建，当前无对应自动化测试 | 支持模型依赖注入及离线测试 |
