# Phase 1：G2 代码安全整改

日期：2026-10-21。需求：REQ-002、REQ-012、REQ-019、REQ-020、REQ-049；重点关联 AC-10、AC-24、AC-59。本批实现其中的代码根因路径，不表示完整需求已经验收。

## 已实现行为

G2 拒绝后，若全部严重阻断项均来自确定性源码策略扫描，且可验证为同一 Spec/架构下的代码根因，编排器创建不可变 `REMEDIATION_ORDER`。工单包含被拒绝的 Gate、基线、问题证据、目标研发 Leader 和代码范围的影响说明。

Router 基于 `SECURITY_FINDING + CODE_DEFECT` 决定归属。研发 Leader 重新接收外部整改并分配任务；Backend 与 Code Review/Testing 在部门内部运行，完成后由 Leader 验收，再独立安全复查。代码范围整改保留有效 G1，重新评估 G2；旧 REJECTED 记录永久保留，不能覆盖为 PASSED。

仅当新 Commit 的固定测试、累计代码审查和研发出口验收均有效，且同一 Spec/架构下的同一策略项已消失，验证服务才将原问题标记 RESOLVED。`ISSUE_RESOLUTION` 绑定新扫描、测试、审查和验收产物。模型自报修复不能关闭工单；失败或旧版本测试/审查不能用于结算。

专家候选发现没有经过独立根因验证，归类为 SECURITY_FINDING 并保持未分派；系统不会固定把所有安全问题交研发。出现此类严重问题、其他门禁证据阻断、基线变化或权限失效时，运行保持 BLOCKED。

部门安全整改轮数受固定配置 `max_department_attempts` 限制；每次进入研发部门的局部重试受 `max_rework_rounds` 限制；全局步骤仍受 `max_steps` 限制。提交、测试目录和候选凭据使用递增的全局 attempt，避免重入时覆盖历史。没有新 Commit 的无效整改在再次 G2 拒绝后停止。

整改工单、阶段切换与审计事件使用同一业务事务。业务事务已提交而 LangGraph checkpoint 未落盘时，恢复会复用工单。问题结算同样幂等；两个崩溃间隙均有独立回归用例。

## 可运行示例

```powershell
$python = 'E:\VibeCoding\Langgraph-proj\.venv\Scripts\python.exe'
$java21 = 'E:\VibeCoding\Langgraph-proj\.agentloop\toolchains\jdk-21.0.12.1+1'
$maven = 'E:\CodeEnv\Java\Maven\binary\apache-maven-3.9.16\bin\mvn.cmd'

& $python -m agentloop phase1-run --data-dir .agentloop --run-id security-sample-01 `
  --java-home $java21 --maven $maven --security-example
# 完成安全整改后停在 RELEASE_AUTHORIZATION / WAITING_APPROVAL。
& $python -m agentloop phase1-authorize --data-dir .agentloop --run-id security-sample-01 `
  --java-home $java21 --maven $maven
& $python -m agentloop phase1-export --data-dir .agentloop --run-id security-sample-01 `
  --java-home $java21 --maven $maven --output docs/security-sample-01-evidence.json
```

该示例使用脚本 Backend：先修复参数边界并保留一个未调用的进程执行方法；固定 HTTP 测试通过后，确定性策略扫描仍会拒绝 G2；第三次候选移除该方法，通过全部复核后生成新的 G2。示例不会调用该进程执行方法，也不会执行外部命令。授权仍使用假身份且仅进入本地部署模拟器。

Backend 的演示 Profile 写入初始配置快照，后续命令无需重复 `--security-example`。原始普通演示及既有配置摘要保持兼容；未新增配置默认字段改变历史摘要。

## 验证

最终完整回归：**301 passed，0 failed，0 skipped**，耗时 450.16 秒。相对审查后的 291 项增加 9 项整改专项用例和 1 个真实 Java 安全整改场景。`pip check`、Python 编译检查及 `git diff --check` 均通过；既有需求文档仍有 CRLF/LF 换行提示。

完整回归记录保存于 `phase1-security-validation.json`。真实 Java 集成同时验证普通参数 Bug 和安全整改两个场景：安全场景的 JUnit 序列应为 FAIL（2 项失败）→ PASS（4 项通过）→ PASS（4 项通过），G2 序列应为 REJECTED → PASSED，受保护的测试及构建配置保持不变。

```powershell
$env:AGENTLOOP_MAVEN_REPOSITORY = Join-Path (Get-Location) '.agentloop\m2'
& $python -m agentloop.verify --java --java-home $java21 --maven $maven `
  --output docs/phase1-security-validation.json
```

其他用例覆盖：未解决问题不关闭、无 Commit 进展停止、部门返工次数限制、未知根因不自动分派、旧或失败证据不能结算、工单与关闭事务后的崩溃恢复、Profile 跨进程恢复。

## 边界

扫描器仅按源码中的进程执行模式实施有限策略检查，可能命中注释或字符串；它不等同于漏洞可达性验证、完整 SAST 或依赖扫描。当前自动整改能力仅面向受信固定样例的确定性代码策略项，不能扩展为任意模型发现的自动根因判定。

产品、架构、环境根因的自动整改和完整影响分析矩阵仍未完成。角色仍为脚本，未调用在线模型；工作区限制不是操作系统沙箱；生产认证、真实部署及 Phase 2～5 均不在本批交付范围内。
