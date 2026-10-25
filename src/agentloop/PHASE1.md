# Phase 1 首批实现

日期：2026-10-21。需求依据：`notes/multi_agent_loop_platform_design_v1.2.md`。

本批实现完整的部门编排主路径，并以真实 Spring Boot 接口测试验证局部开发返工。默认角色适配器是明确标注的脚本演示，不能据此宣称真实模型已经具备自主研发能力。

## 本批行为

父 StateGraph 串联独立的 Product、Front Expert、Engineering、Security Expert 子图。产品 Worker 形成带编号的验收条件；Product Leader 出口验收后进入产品专家审计与架构设计；G1 通过后研发才可启动。研发 Leader 分配一次初始任务，Backend、Code Review、Testing 在部门内部直接流转，最终再调用研发 Leader 验收。

UX 由受信的界面变更标志触发。Code Review 同时读取配置和实际生产代码 Diff；即使配置标为无生产代码变更，实际修改 `src/main/` 仍会触发。专家拒绝产品时生成结构化 Issue，由 LoopRouter 交给 Product Leader。研发返工和部门返工均有次数上限。

G1 可选人工确认使用原审批服务。流程在 G1 或发布授权点保存 checkpoint；恢复使用相同 Run/thread，且读取已固定的配置。Release 创建后默认等待显式演示授权，才能进入仅写本地记录的部署模拟器。生产部署没有开放。

## 真实 Spring Boot 验收样例

`examples/spring-bug` 使用 Spring Boot 3.5.16、Java 21 和 Maven。接口 `/hello` 的原始代码直接调用 `name.trim()`，缺失参数导致 500，空串及空白参数错误返回 200。固定测试要求：缺失、空串、空白均返回 400；合法参数仍返回 `Hello, Alice`。

脚本 Backend 第一轮故意仅修复 null，实际 Maven/HTTP 测试仍有 2 个失败；第二轮增加空白校验后，4 个测试全部通过。每轮提交独立 Git Commit，JUnit 结果、退出码、代码版本及 Spec/架构哈希共同决定测试是否通过。测试、pom.xml 和其他未授权路径禁止由 Backend 修改。

`StructuredModelAdapter` 支持由应用注入已有 LangChain 模型实例；本批没有读取模型密钥或调用在线模型。当前命令行尚未提供真实模型 Profile 配置入口，不能将演示脚本当成线上模型验证。

## 运行

在项目根目录执行。下面的 Java/Maven 路径是本机验证路径；其他机器替换为自己的 JDK 21 和 Maven 路径。

```powershell
$python = 'E:\VibeCoding\Langgraph-proj\.venv\Scripts\python.exe'
$java21 = 'E:\VibeCoding\Langgraph-proj\.agentloop\toolchains\jdk-21.0.12.1+1'
$maven = 'E:\CodeEnv\Java\Maven\binary\apache-maven-3.9.16\bin\mvn.cmd'

& $python -m pip install -e ".[test]"
& $python -m agentloop phase1-run --data-dir .agentloop --run-id sample-01 --java-home $java21 --maven $maven
# 此时应停在 RELEASE_AUTHORIZATION / WAITING_APPROVAL。
& $python -m agentloop phase1-authorize --data-dir .agentloop --run-id sample-01 --java-home $java21 --maven $maven
& $python -m agentloop phase1-status --data-dir .agentloop --run-id sample-01 --java-home $java21 --maven $maven
```

验证 G1 人工确认时，在首次 `phase1-run` 增加 `--require-confirmation`，随后运行 `phase1-confirm`。确认完成后才执行 Backend 与测试；后续恢复命令读取原始配置快照。

所有 `phase1-*` 命令均属于演示，使用假身份 `demo-owner`。该身份不是真实认证，也不能授权任何生产操作。Maven 使用演示目录内的独立 settings 和仓库，只访问 Maven Central，不继承用户的私有仓库凭据或修改系统 Java 配置。工作区按 Run 隔离，保留在 `.agentloop/<run_id>/workspace`。

## 验证及证据

```powershell
# 快速测试：Java 集成用例明确标记跳过。
& $python -m pytest -q

# 完整本机验证：显式执行真实 Maven / Spring Boot HTTP 测试。
$env:AGENTLOOP_MAVEN_REPOSITORY = 'E:\VibeCoding\Langgraph-proj\.agentloop\m2'
& $python -m agentloop.verify --java --java-home $java21 --maven $maven --output docs/phase1-validation.json

# 导出单个运行的全部原文产物、哈希、门禁和事件。
& $python -m agentloop phase1-export --data-dir .agentloop --run-id sample-01 --java-home $java21 --maven $maven --output docs/sample-01-evidence.json
```

本批检查覆盖：内部返工不逐轮调用 Leader；G1 前不调用 Backend；实际生产 Diff 触发审查；无进展停止；高严重性安全发现阻断 G2；越界补丁、测试篡改、旧补丁和损坏产物被拒绝；没有 XML、跳过测试、退出码不一致均不能算 PASS。

2026-10-21 代码审查进一步补齐审批使用时校验、G2 后新增严重问题阻断、累计 Diff 审查、HEAD/未跟踪输入漂移检查、发布门禁绑定与研发计划/架构范围传递。详见项目根目录 `docs/code-review-2026-10-21.md`；本次验证单独保存为 `docs/code-review-validation-2026-10-21.json`，保留首批实现的历史报告。

后续批次已增加确定性代码安全策略的 G2 整改闭环：拒绝 G2 → Router 交研发 Leader → 工单分配 → 修改、审查、测试、出口验收 → 安全复查与原问题结算 → 新 G2。运行 `phase1-run` 时增加 `--security-example` 可复现；后续恢复与授权从原配置快照读取 Profile，无需重复该参数。完整行为和限制见 `docs/phase1-security-remediation.md`。

验收追踪报告将“有关联测试”与“整条 AC 完成”分开。真实 Java 验证必须显式启用；报告中的 `java_integration_requested` 和逐用例结果说明本次是否实际执行，不能把跳过算成通过。

## 剩余边界

- 默认模型角色和人类身份是脚本/假身份。未验证在线模型质量、Token 预算、完整四级模型配置、权限隔离进程或生产认证。
- 本地受限补丁检查不是操作系统沙箱。当前执行器仅用于受信的固定测试样例；任意第三方仓库的构建代码仍需容器/进程隔离后接入。
- 安全扫描仅检测样例源码中的进程执行模式，并结合专家候选报告。没有依赖漏洞扫描、完整 SAST 或正式安全放行能力。
- 测试自身问题进入 BLOCKED，禁止自动修改验收条件。确定性扫描验证为代码根因的严重策略项可自动交研发 Leader 整改，原始拒绝记录和关闭证据保留。专家候选缺少已验证根因时保持 UNASSIGNED/BLOCKED；产品、架构与环境整改的全自动执行、完整影响传播尚未完成。
- 模拟部署不连接服务器，健康与回滚准备是模拟条件。真实部署、失败恢复/对账、维护子 Run 和生产授权签名仍属后续阶段。
- 源码补丁有持久候选凭据并支持相同内容的幂等重放；测试复用绑定 Commit 和文档版本。任意节点、任意时刻崩溃的全量恢复矩阵仍需补齐。
- 前端完整 UX 产物、并行 Worktree、Skills/MCP 注册、预算、长期记忆、复盘与界面尚未实现；本批不能视为全部 Phase 1～5 已交付。

## 官方依据

子图与父图的通信和持久状态边界依据 [LangGraph Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)。HTTP 测试采用 [Spring Boot Testing](https://docs.spring.io/spring-boot/reference/testing/spring-boot-applications.html) 的随机端口方式。以上为官方工程文档，不作为学术文献引用。
