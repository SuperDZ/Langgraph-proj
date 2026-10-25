# AgentLoop Phase 0

2026-10-21：已继续实现 Phase 1 首批流程，最新能力和运行方式见 [Phase 1 说明](PHASE1.md)。以下保留 Phase 0 的实现边界与历史验证方法。

需求依据：`notes/multi_agent_loop_platform_design_v1.2.md`，实现日期：2026-10-19。

本阶段实现可测试的编排内核和持久澄清流程。模型、三部门完整子图、源码修改和生产部署尚未接入。

## 安装与离线演示

在项目根目录 `E:\VibeCoding\Langgraph-proj` 执行，要求 Python 3.11+。本次实际验证使用 Windows / Python 3.13.14。

仓库根目录 `requirements-lock.txt` 保存本次 Windows 验证的完整依赖版本。复现同一依赖集合时，先执行 `python -m pip install -r requirements-lock.txt`，再执行下面的可编辑安装命令。其他 Python 版本和操作系统需要重新验证。

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m agentloop demo-start
.\.venv\Scripts\python.exe -m agentloop demo-status
.\.venv\Scripts\python.exe -m agentloop demo-answer --answer "空参数应返回 400，合法参数应返回 200。"
.\.venv\Scripts\python.exe -m agentloop demo-status
```

上述命令分别启动独立 Python 进程。`demo-start` 将 Run 停在 `INTAKE / PAUSED_FOR_HUMAN`；`demo-answer` 从原 `thread_id` 恢复，状态变为 `INTAKE / RUNNING`。这表示澄清完成，不表示整个研发任务已交付。重复启动、重复相同答复均不会增加重复的澄清事件。

默认状态位于 `.agentloop/demo/state.db`，LangGraph checkpoint 位于同目录 `checkpoints.db`。可使用 `--data-dir` 和 `--run-id` 指定独立演示目录及任务。演示命令使用明确标注的假身份 `demo-owner`，不读取 `.env`、不调用模型、不连接服务器、不产生真实发布。

## 已实现的模块

| 路径 | 行为与边界 |
|---|---|
| `core/contracts` | Pydantic 契约、三套状态枚举与白名单；拒绝 Agent 提交路由目标及门禁决定；门禁布尔值禁止字符串隐式转换 |
| `core/orchestration/store.py` | 内存测试仓储、复制读写、可回滚事务 |
| `core/orchestration/sqlite_store.py` | SQLite JSON 记录、幂等唯一约束、追加事件、嵌套事务；跨连接写入串行化 |
| `core/orchestration/state_transition.py` | Phase/Status 复合守卫、CAS、终态保护、最新门禁校验；拒绝时业务状态和事件不变 |
| `core/orchestration/gate_evaluator.py` | G1/G2/G3 确定性评估；人工确认策略与风险触发；G3 拒绝进入恢复阶段 |
| `core/orchestration/clarifications.py` | 澄清幂等创建、真人与项目角色检查、输入版本校验、答复落库 |
| `core/orchestration/intake_graph.py` | 真实 LangGraph `interrupt` / `Command(resume=...)` 与 SQLite Checkpointer；恢复前验证已落库答复 |
| `core/approvals` | 持久身份与角色绑定、Capability 交集、G1 审批/撤销、Release 及发布许可基础服务 |
| `core/routing` | 类别和归属表路由；未知及结构化责任冲突升级；自然语言不能指定目标 |

状态变更与业务事件在单个仓储事务中提交；SQLite checkpoint 与业务库是两个独立提交边界。答复提交后若 checkpoint 更新前进程故障，可重交相同答复完成原 checkpoint 恢复。这里不承诺分布式 exactly-once。

## 验收与回归

```powershell
# 只验证新内核
.\.venv\Scripts\python.exe -m pytest src/agentloop/tests -q

# 同时执行 week2 回归并保存需求追踪及逐用例结果
.\.venv\Scripts\python.exe -m pip install -r src/week2/requirements-dev.txt
.\.venv\Scripts\python.exe -m agentloop.verify --output docs/phase0-validation.json
```

追踪报告检查 REQ-001～049、AC-01～59 的编号与关联，记录每个测试的执行结果。`HAS_LINKED_TESTS_REVIEW_SCOPE` 只表示该 AC 有关联测试，不能作为该 AC 全部业务条件已经验收的证明。后续阶段的未实现内容明确保留为缺口。

已覆盖的关键场景：

- G1 的两个确认均待真人决定；重评估复用 PENDING 记录；过期、拒绝、撤销和基线变更阻断研发入口。
- 发布审批拒绝 Agent、系统服务、无角色人员和其他项目人员；拒绝记录单独审计。
- Phase 白名单与规格一致，Run Status 和 GateResult 白名单穷举；旧 PASSED 不得覆盖最新 REJECTED。
- 两个 SQLite 连接的 CAS 冲突；注入事件写入故障后，状态与事件同时回滚。
- 真实独立进程暂停、重启、恢复；重复答复不产生重复事件。
- Agent 上报中的越权字段、空证据、自报身份不匹配和幂等键碰撞被拒绝。
- 假部署记录下 G3 的通过、拒绝与缺失健康结论；这些测试不代表部署执行器已实现。

本次实测结果以仓库中的 `docs/phase0-validation.json` 为准；CI 配置仅代表已编写，远端 CI 是否通过需查看实际运行。

## 已知限制与后续工作

1. 当前为内部 Python 服务及离线 CLI，没有 HTTP API、真实登录认证、桌面界面或可暴露公网的入口。主体注册/角色绑定是可信服务的配置接口，不是用户可调用的自授权 API。
2. G1/G2 的验收输入由可信测试/编排代码构造；尚未实现完整的 Artifact 内容仓库、扫描器适配器及证据签发链。不能把模型回复直接映射成这些布尔值。
3. 实际进入 `DEPLOYMENT` 的通用入口保持拒绝，等待受控副作用执行器接入。发布授权的 60 分钟/单次参数仅用于当前原型；真实发布还缺签名、完整策略快照、操作租约、撤销/消耗、回滚、对账与环境集成。
4. 持久模型采用单机 SQLite JSON 表；父子 Run 的项目关系由服务校验。生产化仍需数据库迁移、关系约束、项目隔离评审及数据归档策略。
5. 完整部门子图、自动开发/审查/测试 Loop、预算、Skills/MCP 注册、长期记忆和复盘仍按 Phase 1～5 实施。审批更新版本及多人联合审批的对外流程也尚未提供。
6. 现有 severity 约定沿用骨架的保守阻断：CRITICAL/HIGH 均阻断 G2。P1 与漏洞严重等级的完整映射需要在接入真实缺陷来源时单独固化。

下一阶段优先实现产品—前置专家—后端—测试 MVP，以可复现 Spring Boot Bug 验证真实开发与测试闭环。

## 官方实现依据

中断恢复沿用相同 `thread_id`，且节点可能从开头重新执行，因此审批和澄清创建必须幂等。依据：[LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)、[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)。以上为官方工程文档，非学术文献。
