# AgentLoop 代码审查与修复

日期：2026-10-21。范围：当前工作区 `src/agentloop` 的 Phase 0/1 实现、测试、需求文档及运行说明。审查依据为 `notes/multi_agent_loop_platform_design_v1.2.md`。现有代码多为未跟踪文件，因此审查的是文件当前内容，不能仅凭 `git diff` 评估本批代码。

发现并修复以下 7 类缺陷。严重性表示修复前对当前工作流的影响；发布路径仍限于本地模拟，不代表已存在生产部署风险。

## 1. P1：门禁放行标签不能证明使用时仍有效

`StateTransitionService.require_fresh_passing_gate()` 原先主要检查 PASSED 与 G2 Commit，没有重新检查 G1 审批是否过期、审批人是否停用或角色是否失效。G2 放行后新增 HIGH/CRITICAL Issue 也不能阻止旧门禁被继续使用。

修复：使用门禁时重新验证 G1 基线摘要、关联审批、有效期、真人身份和项目角色；重新检查 G2 未解决严重问题。G1 再评估也不再复用权限已失效的批准。发布申请和发布决定均执行这些守卫。验证覆盖过期、角色过期、身份停用，以及 G2 后新增 HIGH/CRITICAL 问题。

位置：`core/orchestration/state_transition.py`、`core/approvals/approval_requests.py`、`core/orchestration/gate_evaluator.py`、`core/approvals/releases.py`。

## 2. P1：补丁提交可夹带预先暂存的其他文件

`GitWorkspace.apply()` 校验的是候选补丁与写入前后的测试摘要。若测试已被外部修改并暂存，后续普通 `git commit` 会一并提交这些文件，写入前后摘要相同无法发现。

修复：首次写入前检查 Git 索引和工作树，拒绝候选范围外的已暂存或未暂存修改；拒绝未经审查的未跟踪文件。候选文件已写入及其临时文件仍可按原恢复协议重放。验证同时覆盖预先暂存与未暂存的测试修改，确认拒绝时不写源码、不产生提交、不撤销原修改。

位置：`core/runtime/workspace.py`。

## 3. P1：恢复和授权未核对实际工作区版本

测试复用原先比较报告里的 Commit 与 checkpoint 中的 Commit，并只检查受跟踪文件是否有未提交改动。外部切换到另一个干净 HEAD 后仍可复用旧测试；新增未跟踪 Java 源码也会被忽略。

修复：代码审查、测试及其复用、安全扫描、G2、授权等待、授权入口和模拟执行均核对实际 HEAD 与完整工作树。真实执行器也将未跟踪输入视为完整性失败。恢复时的守卫拒绝转为 BLOCKED。验证覆盖测试产物落库后崩溃、外部增加空提交再恢复，以及授权前增加未跟踪源码；拒绝时不签发或消耗许可。

位置：`core/runtime/workspace.py`、`core/runtime/testing.py`、`core/department_graphs/delivery.py`。

## 4. P1：Release 与许可未完整绑定通过的 G2

`ReleaseService.create()` 原先接受与 G2 不同的调用者 Commit。模拟器只要求存在一个当前通过的 G2，因此同一 Run 返工并产生新 G2 后，旧 Release 的许可仍可能被接受。

修复：有 Commit 基线的运行必须将 Release 绑定当前基线和 G2 Commit；发布申请核对 G2 身份；模拟执行核对 Release 的 Spec、架构、Commit 与当前门禁 ID。验证覆盖错误 Commit 与旧 G2 许可，拒绝时许可使用次数和部署记录不变。Phase 0 无 Commit 的离线契约测试保留兼容性。

位置：`core/approvals/releases.py`、`core/runtime/simulation.py`。

## 5. P2：多轮 Code Review 只收到最后一次提交

触发条件读取累计 Diff，但给 Reviewer 的材料来自 `git show HEAD`。前轮保留、后轮未触碰的修改会从后轮审查材料中消失。

修复：统一传入工作区初始提交至候选 Commit 的累计 Diff。验证在首轮添加一项保留修改，确认第二轮审查同时看到该修改和新增修复。

位置：`core/department_graphs/delivery.py` 的 `review()`。

## 6. P2：缺失或损坏的 G2 证据使评估异常退出

G2 解析产物引用时可能抛出 KeyError；产物丢失或损坏也可能抛出读取异常。原路径不能形成明确的 REJECTED 门禁和 BLOCKED 运行记录。

修复：证据解析失败形成 `DELIVERY_EVIDENCE_UNREADABLE_OR_INVALID` 阻断项，按门禁事务写入拒绝结果。验证覆盖不存在的测试引用和损坏的原文产物。

位置：`core/orchestration/gate_evaluator.py`。

## 7. P2：研发分工与架构批准范围未传递到 Backend

研发 Leader 的 `EngineeringPlan` 原先生成后被丢弃，Backend 未获得分配内容。架构可以批准工作区权限的子集，但实际候选仍按更大的工作区权限校验。

修复：checkpoint 保存计划产物引用，Backend 上下文包含计划和架构，只提供获批文件；候选及恢复凭据中的补丁再次检查获批范围。验证在工作区允许两个文件、架构只批准其中一个时，越范围候选在任何写入和测试前被阻断。

位置：`core/department_graphs/delivery.py` 的 `plan()`、`backend()`。

## 验证

最终完整回归：**291 passed，0 failed，0 skipped**，耗时 248.82 秒；相对首批 274 项增加 17 项测试。真实 Maven/Spring Boot HTTP 集成用例实际执行并通过。`pip check`、Python 编译检查与 `git diff --check` 均通过；Git 仅提示既有需求文档的 CRLF/LF 换行转换。

完整执行结果记录于 `code-review-validation-2026-10-21.json`。该报告保留逐用例结果、REQ/AC 映射、运行环境及是否显式启用真实 Java 集成。

运行命令：

```powershell
$env:AGENTLOOP_MAVEN_REPOSITORY = Join-Path (Get-Location) '.agentloop\m2'
.\.venv\Scripts\python.exe -m agentloop.verify --java `
  --java-home .agentloop/toolchains/jdk-21.0.12.1+1 `
  --maven E:/CodeEnv/Java/Maven/binary/apache-maven-3.9.16/bin/mvn.cmd `
  --output docs/code-review-validation-2026-10-21.json
```

## 证据边界

本次没有调用在线模型、真实认证服务或生产部署。默认脚本角色、假身份、本地模拟部署、有限安全扫描及缺少操作系统沙箱等既有边界仍适用。新增失败路径测试采用假执行器验证编排约束；真实 Java 集成单独执行 Maven、随机端口 Spring Boot HTTP 断言及 FAIL→PASS 返工。没有将全部需求或未来阶段视为已经验收。
