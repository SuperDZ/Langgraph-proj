# Phase 2：模型、Skills/MCP 与异常弹性

日期：2026-10-22。需求基线：`notes/multi_agent_loop_platform_design_v1.2.md` §3–5、§12、Phase 2 出口条件。

2026-10-25 复核：发现阶段先过滤 Capability 与独立执行器能力，禁止为了获取工具元数据启动无权使用的服务；写入审批增加脱敏参数预览，并在 `phase2-status` 中展示项目内待审批请求。参数哈希仍绑定原请求，审批预览不保存凭据原文。

本阶段实现可运行的本地执行层，并接入原有交付图。它支持真实模型 HTTP 客户端、真实 MCP stdio/Streamable HTTP 客户端和故障注入测试。生产部署、外部身份认证、OS 级进程沙箱和长期记忆发布属于后续阶段。

## 实现与验收对应

| 能力 | 实现 | 主要证据 |
| --- | --- | --- |
| 四级配置与逐角色模型 | 平台→部门→Agent→任务；普通参数覆盖，预算/步骤/并发受上层上限约束；模型、工具、网络、秘密与 Capability 求交；目录只能缩小；deny 优先 | AC-14/15，`test_phase2_runtime.py` |
| 不可变配置 | 每个角色按 Run 保存完整有效配置及摘要；工作流 Profile 包含有效配置摘要，恢复不能替换；秘密只保留 `env:NAME` | AC-14/17/32 |
| 后备模型 | 按显式顺序；模型白名单、驻留、结构化输出、工具能力与审计兼容性在启动前校验；只对超时、限流、服务不可用重试 | AC-40 |
| 预算 | 根 Run、子 Run、角色共用持久预占/结算；未知调用保留预占；后备调用、修复调用都计费；调用前检查硬额度、步骤和并发 | AC-37 |
| 预算审批 | 阻断生成持久申请；仅人工项目负责人可增额；角色增额在根额度内单独批准；保留原始配置和全部历史用量 | AC-37 |
| Schema 弹性 | 严格 Pydantic；初始生成后最多两次修复；记录摘要和错误路径；失败不产生业务候选并阻断工作流 | AC-38 |
| Skills | 目录、ZIP/TAR、受信 HTTPS 下载+SHA256、Git 指定 revision→commit；隔离、静态风险、依赖与许可证声明检查；人工批准并绑定、版本哈希锁定、搜索/比较/导出/停用/卸载 | AC-16/17 |
| MCP | 人工登记并审批后才启动；初始化、能力协商、分页工具发现、Schema 校验、stdio/HTTP JSON/SSE、会话头、关闭连接 | AC-14/15 |
| 工具控制 | 模型只能提出 JSON 工具候选；代理逐次校验不可变配置、工具及 Capability、路径、网络和秘密引用；生产部署、秘密管理、记忆审批必须走独立执行器 | AC-15/39 |
| 运行恢复 | 持久预算和 MCP 凭据；成功调用复用结果；STARTED/UNKNOWN/FAILED 请求不自动重放；工具版本在 Run 内固定 | AC-17/24/37 |
| 注入边界 | Skills、README/日志、MCP 内容全部放在 user 数据区域；无权修改状态机/RBAC/审批；命中风险规则生成专门审计事件；安全性不依赖关键词检测 | AC-39 |

源码入口：`core/contracts/phase2.py`、`core/runtime/{configuration,budget,models,skills,mcp}.py`、`runtime_cli.py`。数据库继续使用现有 SQLite 事务和追加事件，不引入独立的无事务旁路。

## 本地运行

```powershell
$python = '.\.venv\Scripts\python.exe'
$java21 = '.agentloop/toolchains/jdk-21.0.12.1+1'
$maven = 'E:/CodeEnv/Java/Maven/binary/apache-maven-3.9.16/bin/mvn.cmd'

& $python -m pip install -r requirements-lock.txt
& $python -m pip install -e '.[test]' --no-deps
& $python -m agentloop phase2-config --output .agentloop/phase2-config.json
# 通过进程环境或已有秘密管理器设置 DEEPSEEK_API_KEY，不要写入配置 JSON。
& $python -m agentloop phase2-preflight --config .agentloop/phase2-config.json --java-home $java21 --maven $maven
& $python -m agentloop phase2-run --config .agentloop/phase2-config.json --java-home $java21 --maven $maven
& $python -m agentloop phase2-status
& $python -m agentloop phase2-export --output docs/phase2-delivery-evidence.json
```

默认角色模型示例采用 `deepseek-flash`，Testing 使用 `deepseek-v4-pro`。默认不设置后备链；在目标角色的 `agent.fallbacks` 中明确配置所需 Profile。启动前通过 `/models` 验证账户实际可见模型；思考模式拒绝无效的 temperature 组合。模型输出中的实际模型标识和每次请求的用量凭据独立保存，不把别名视为永久固定权重版本。

`input_rate`/`output_rate` 单位为 micro-USD/token，是受信配置提供的记账费率，默认值仅供演示。`run_cost_budget` 和 `cost_budget` 单位为 micro-USD。需要按照目标合同和提供方价格配置保守费率；账本按提供方返回的实际 Token 用量结算估算金额，不能当作提供方账单或账户余额。预占使用 UTF-8 字节上界和封装余量，可能较保守；提供方用量若超预占会停止后续调用并要求核对。

普通流程最终停在 `RELEASE_AUTHORIZATION / WAITING_APPROVAL`。本地显式授权命令如下；它使用演示身份，执行目标仍是本地模拟器。

```powershell
& $python -m agentloop phase2-authorize --config .agentloop/phase2-config.json --java-home $java21 --maven $maven
```

预算阻断后先查看 `phase2-status` 中的申请，再使用已注册的人类项目负责人批准：

```powershell
& $python -m agentloop phase2-budget-approve --request-id '<request-id>' --tokens 2000000 --cost 4000000
# 若还需要提高某角色额度，增加 --role-tokens / --role-cost；这两项必须同时给出。
& $python -m agentloop phase2-resume --config .agentloop/phase2-config.json --java-home $java21 --maven $maven
```

增额不会解除 max_steps、concurrency 或提供方超额异常；它们需要核对，而非无限重试。

## Skills 与 MCP 管理

先创建或运行一个本地 Run，管理命令才能将来源和审批事件归档到该项目。导入不执行代码，也不会自动批准风险。

```powershell
& $python -m agentloop phase2-skill-import --path C:/trusted-input/review-helper
& $python -m agentloop phase2-skill-list
& $python -m agentloop phase2-skill-approve --version '<content-hash>' --accepted-risk '<listed-risk>'
& $python -m agentloop phase2-skill-bind --version '<content-hash>' --role backend
# 将 skills: {"review-helper":"<content-hash>"} 放入对应角色 agent 配置，创建新 Run 后生效。
& $python -m agentloop phase2-skill-diff --previous-version '<old-hash>' --version '<new-hash>'
& $python -m agentloop phase2-skill-export --version '<content-hash>' --output .agentloop/review-helper.zip
& $python -m agentloop phase2-skill-disable --version '<content-hash>'
```

风险为空时省略 `--accepted-risk`；存在多项时重复该参数，必须明确确认全部项。下载用 `phase2-skill-download --url ... --sha256 ... --trusted-host ...`；Git 用 `phase2-skill-git --url ... --revision ... --trusted-host ...`。Git 来源记录解析后的 commit。依赖使用可选的 `dependencies.json`，内容为已批准 Skill 哈希列表。

升级需导入并人工批准新版本，再为新 Run 更新配置。回滚选择仍已批准的旧哈希重新绑定，并为新 Run 使用该哈希。运行中的 Skill 内容不会被远端更新替换。停用/卸载属于明确撤权，后续读取会拒绝；已归档的历史内容保留用于审计。SKILL.md 的 `allowed-tools` 仅是包元数据，不能赋权。脚本只静态检查并归档，Phase 2 不执行 Skill 脚本。引用资料仅在 `references/`、`assets/` 下按需读取。

MCP 服务定义例子：

```json
{
  "server_id": "source-reader",
  "transport": "stdio",
  "command": ["C:/approved-runtime/python.exe", "C:/approved-tools/source_reader.py"],
  "cwd": "C:/approved-tools",
  "env_refs": {},
  "tools": {
    "read_file": {"capability": "cap.repo.read", "mutating": false, "path_parameters": ["path"]}
  }
}
```

远端服务使用 `transport: "http"`、`url` 和可选 `auth_ref: "env:MCP_TOKEN"`，不把 token 放在 URL 或 JSON。平台及下级策略需同时授权 `source-reader/read_file`、`cap.repo.read` 和对应目录；凭据、网络域名也必须在交集中。

```powershell
& $python -m agentloop phase2-mcp-register --path .agentloop/source-reader.json
& $python -m agentloop phase2-mcp-approve --version '<server-config-hash>'
& $python -m agentloop phase2-mcp-test --version '<server-config-hash>'
& $python -m agentloop phase2-mcp-list
```

`phase2-mcp-disable` / `phase2-mcp-uninstall` 立即撤销后续执行；停止进程由客户端关闭与命令结束处理。升级登记新配置摘要并批准；回滚重新人工批准旧配置摘要。已有 Run 首次加载工具时固定服务版本及工具 Schema，之后升级不能替换它。服务自行修改 Schema 会触发拒绝，必须重新登记。调用执行审计包含 Run、角色、服务版本、工具名、参数哈希、状态、耗时，不保存原始参数；审批单单独保留脱敏预览。可供模型读取的工具返回在持久化前替换该服务凭据内容。

当有效策略 `requires_human_approval: true` 时，写入工具还需要逐次人工审批。首次请求生成绑定 Run、角色、参数哈希、配置摘要、服务版本及 30 分钟有效期的申请，启动工具前即阻断。使用 `phase2-mcp-call-approve --request-id ...` 批准后再恢复；许可只在持久 STARTED 凭据写入时消费，同一成功请求只复用结果，另一个请求不能使用该许可。只读工具必须由受信注册配置显式声明 `mutating: false`，服务端 annotations 无权代替该声明。

先通过 `phase2-status` 查看 `tool_approvals`：其中 `review_arguments` 保留目标路径、操作内容等结构，并替换已引用的凭据内容及敏感字段值。审批人应核对这些内容、服务版本及原参数摘要；状态读取校验项目访问权限，审批仍仅允许人类项目负责人。

本地服务登记时额外锁定可执行文件、命令中可识别的文件参数，以及 `pinned_files` 列出的支持文件 SHA256；启动前重新校验，文件变化会拒绝执行。`pinned_files` 使用绝对路径，部署包的其他模块和依赖锁文件应显式纳入。系统运行时及所有隐式依赖的完全复现需要后续隔离镜像，不能仅凭入口文件摘要作出该保证。

人工批准的本地 MCP 进程具有操作系统用户本身的权限。这里实现的是调用代理的授权控制、最小环境变量与禁止隐式启动，不能声称是 OS 沙箱。容器/沙箱、受控生产 SideEffectExecutor 和在途取消对账属于 Phase 3。

## 验证边界

2026-10-25 最终验证：全量 **383 passed，0 failed，0 skipped**，其中 Phase 2 专项 **80 项**，真实 Java/Maven/Spring 集成 **2 项**；专项包含真实本机 MCP stdio、HTTP 和 SSE 交互。安装包版本 **0.3.0**，独立安装与配置命令通过，包内 42 个 Python 模块与源码逐字节一致，`pip check` 和 `git diff --check` 通过。

汇总和源码摘要见 `docs/phase2-completion.json`；安装包检查见 `docs/phase2-packaging-validation.json`；独立专项执行记录见 `docs/phase2-runtime-tests.xml`。80 项专项已包含在 383 项全量中，不重复相加。

全量报告为 `docs/phase2-validation.json`，包括既有 Phase 0/1、week2 回归、真实 Java 21/Maven/Spring HTTP 断言，以及 Phase 2 故障注入和真实本机 MCP 传输测试。REQ/AC 关联仅表示有相应用例，不能解释为所有 49 项需求已交付。

本次 DeepSeek `/models` 在线预检返回 **HTTP 401**。现有凭据未通过认证，未进行成功的在线生成，不能据此宣称真实模型修复质量已经验收。没有输出或归档密钥。在线效果验收需要先提供可用的进程环境凭据，再运行 preflight 和模型工作流；这不影响本地故障恢复和权限出口测试的真实性。

补齐了两个已有流程缺口：UX 拒绝进入产品有界返工，并在审查上下文纳入轮次防止复用旧拒绝；研发 Leader 拒绝出口进入研发有界返工。测试自身缺陷、未验证的安全根因和真实部署仍保持明确阻断，由后续工作处理。

## 工程协议依据

- [DeepSeek Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)、[JSON 输出](https://api-docs.deepseek.com/guides/json_mode/)、[思考模式](https://api-docs.deepseek.com/guides/thinking_mode/)：请求参数与输出约束。
- [MCP 生命周期](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)、[传输](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)、[工具](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)：初始化、会话、传输和 Schema。
- [Agent Skills 格式](https://agentskills.io/specification)：SKILL.md 元数据和目录结构。

以上是协议官方文档，没有引入未经验证的论文结论或额外学术引用。
