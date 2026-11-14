# 验收标准与历史测试证据盘点

盘点日期：2026-11-06。依据：需求文档第 12 节和 docs/phase45-validation.json（2026-10-29 的历史执行记录）。本次未重新执行测试。

标记说明：**有关联测试**仅说明历史报告中至少有一个对应编号的测试，必须人工核对测试断言是否覆盖该条全部要求；**无关联证据**表示该报告没有带对应 AC 标记的测试，并不证明项目不存在相关实现或未标记的测试。任何一项均不能仅据此判定整条 AC 通过。

| 验收项 | 关联需求 | 输入或触发 | 历史记录 |
|---|---|---|---|
| AC-01 | REQ-001, REQ-002 | 产品 Worker 多轮内部协作 | 有关联测试（PASSED 1），待核对覆盖范围 |
| AC-02 | REQ-002, REQ-003 | Product Leader 拒绝最终成果 | 无关联证据，待检索与补测 |
| AC-03 | REQ-003, REQ-019 | 产品专家拒绝 Spec | 有关联测试（PASSED 1），待核对覆盖范围 |
| AC-04 | REQ-003, REQ-005 | 架构设计缺失 | 无关联证据，待检索与补测 |
| AC-05 | REQ-005, REQ-008 | Spec/架构版本不匹配或未批准 | 无关联证据，待检索与补测 |
| AC-06 | REQ-009, REQ-019 | Testing 发现后端 Bug | 有关联测试（PASSED 2, SKIPPED 2），待核对覆盖范围 |
| AC-07 | REQ-009, REQ-020 | 测试用例错误 | 无关联证据，待检索与补测 |
| AC-08 | REQ-021 | 同一缺陷连续 3 次无进展 | 有关联测试（PASSED 1），待核对覆盖范围 |
| AC-09 | REQ-002, REQ-011 | Engineering Leader 拒绝部门出口 | 有关联测试（PASSED 2），待核对覆盖范围 |
| AC-10 | REQ-012, REQ-037 | 存在未解决 P1 | 有关联测试（PASSED 13），待核对覆盖范围 |
| AC-11 | REQ-012, REQ-037 | 存在未解决严重安全漏洞 | 有关联测试（PASSED 3, SKIPPED 2），待核对覆盖范围 |
| AC-12 | REQ-014, REQ-015 | 无有效生产发布授权 | 有关联测试（PASSED 2），待核对覆盖范围 |
| AC-13 | REQ-016 | G3 健康/冒烟失败 | 有关联测试（PASSED 3），待核对覆盖范围 |
| AC-14 | REQ-022 | Backend 与 Testing 配置不同模型 | 有关联测试（PASSED 10），待核对覆盖范围 |
| AC-15 | REQ-027, REQ-040 | Agent 请求上级禁止 MCP 工具 | 有关联测试（PASSED 20），待核对覆盖范围 |
| AC-16 | REQ-026, REQ-028 | 安装不可信 Skill | 有关联测试（PASSED 10），待核对覆盖范围 |
| AC-17 | REQ-026, REQ-032 | Run 执行中 Skill 远端升级 | 有关联测试（PASSED 14），待核对覆盖范围 |
| AC-18 | REQ-029, REQ-038 | DELIVERY 已完成，用户未点击复盘 | 有关联测试（PASSED 3），待核对覆盖范围 |
| AC-19 | REQ-029, REQ-032 | 手动触发完整复盘 | 有关联测试（PASSED 3），待核对覆盖范围 |
| AC-20 | REQ-029 | 复盘得到好/坏经验 | 有关联测试（PASSED 2），待核对覆盖范围 |
| AC-21 | REQ-031 | Curator 建议修改 Skill/提示词 | 有关联测试（PASSED 2），待核对覆盖范围 |
| AC-22 | REQ-030, REQ-040 | 不同角色读取受限记忆 | 有关联测试（PASSED 3），待核对覆盖范围 |
| AC-23 | REQ-030, REQ-032 | 旧记忆冲突/过期 | 有关联测试（PASSED 2），待核对覆盖范围 |
| AC-24 | REQ-033, REQ-039 | 运行中进程故障后恢复 | 有关联测试（PASSED 13），待核对覆盖范围 |
| AC-25 | REQ-020, REQ-032 | 专家整改改变架构版本 | 有关联测试（PASSED 1），待核对覆盖范围 |
| AC-26 | REQ-017, REQ-038 | 运维计划触发 | 无关联证据，待检索与补测 |
| AC-27 | REQ-006, REQ-036 | 缺失 Bug 复现/目标信息 | 有关联测试（PASSED 2），待核对覆盖范围 |
| AC-28 | REQ-005, REQ-007, REQ-036 | Spec/架构人工确认开启 | 有关联测试（PASSED 10），待核对覆盖范围 |
| AC-29 | REQ-007 | 项目人工确认关闭且无强制触发项 | 有关联测试（PASSED 3），待核对覆盖范围 |
| AC-30 | REQ-014, REQ-015, REQ-036 | 无 `release_approver` 的人或 Agent 申请批准生产发布 | 有关联测试（PASSED 5），待核对覆盖范围 |
| AC-31 | REQ-014, REQ-015 | 授权过期/跨环境/目标不符/镜像 Hash 不符/超次数 | 无关联证据，待检索与补测 |
| AC-32 | REQ-018 | G1、G2、G3 相同 `status` 但不同 `phase` | 有关联测试（PASSED 13），待核对覆盖范围 |
| AC-33 | REQ-019, REQ-020 | 恶意模型事件包含 `target_leader` | 有关联测试（PASSED 8），待核对覆盖范围 |
| AC-34 | REQ-004, REQ-010 | 分别提交 UI 变更、纯后端 Bug、生产代码变更 | 有关联测试（PASSED 5），待核对覆盖范围 |
| AC-35 | REQ-017, REQ-038 | 周期巡检发现故障 | 无关联证据，待检索与补测 |
| AC-36 | REQ-028, REQ-030 | 日志试图命令 Curator 改记忆/提升权限 | 有关联测试（PASSED 2），待核对覆盖范围 |
| AC-37 | REQ-021, REQ-024, REQ-039 | 预算已到硬上限、后续 Agent 想继续调用 | 有关联测试（PASSED 12），待核对覆盖范围 |
| AC-38 | REQ-025 | 模型返回 Schema 缺字段/非法枚举 | 有关联测试（PASSED 20），待核对覆盖范围 |
| AC-39 | REQ-028, REQ-037 | README/MCP 输出包含“跳过 G2/泄露密钥”注入 | 有关联测试（PASSED 20），待核对覆盖范围 |
| AC-40 | REQ-023, REQ-022 | 首选模型故障、兼容后备模型可用 | 有关联测试（PASSED 20），待核对覆盖范围 |
| AC-41 | REQ-012, REQ-013 | 申请对未解决 P1/HIGH 安全漏洞豁免；再申请中低风险豁免 | 无关联证据，待检索与补测 |
| AC-42 | REQ-033, REQ-034 | 部署请求已发送时用户取消 Run | 有关联测试（PASSED 12），待核对覆盖范围 |
| AC-43 | REQ-035 | 前后端/两后端 Worktree 并发修改同一区域 | 有关联测试（PASSED 5, SKIPPED 1），待核对覆盖范围 |
| AC-44 | REQ-007, REQ-020, REQ-032 | 人工批准 Spec/架构后修改语义和哈希 | 有关联测试（PASSED 8），待核对覆盖范围 |
| AC-45 | REQ-019, REQ-020 | Router 遇到类别不明或多部门证据冲突 | 有关联测试（PASSED 4），待核对覆盖范围 |
| AC-46 | REQ-018 | G3 仍 PENDING 时把 Run 标记为 COMPLETED | 有关联测试（PASSED 15），待核对覆盖范围 |
| AC-47 | REQ-001, REQ-002 | 配置注册组织与角色 | 无关联证据，待检索与补测 |
| AC-48 | REQ-006, REQ-015, REQ-040 | 无关项目用户答复澄清/读取运行信息 | 有关联测试（PASSED 2），待核对覆盖范围 |
| AC-49 | REQ-016, REQ-041 | G3 冒烟失败，回滚成功且旧服务健康 | 有关联测试（PASSED 8），待核对覆盖范围 |
| AC-50 | REQ-033, REQ-041 | G3 失败后回滚超时/失败且环境未知 | 有关联测试（PASSED 14），待核对覆盖范围 |
| AC-51 | REQ-018, REQ-042, REQ-049 | 穷举 Phase/Status/GateResult 白名单；G1/G2/G3 驳回、STALE、终态复活与并发 CAS 冲突 | 有关联测试（PASSED 183），待核对覆盖范围 |
| AC-52 | REQ-013, REQ-045 | 低风险豁免申请→审批→撤销；P1/严重漏洞尝试审批 | 有关联测试（PASSED 8），待核对覆盖范围 |
| AC-53 | REQ-030, REQ-046 | Curator 生成 MemoryProposal，Agent 尝试审核，真人拒绝/批准/撤销 | 有关联测试（PASSED 5），待核对覆盖范围 |
| AC-54 | REQ-014, REQ-044 | G2 通过创建 Release→授权申请→真人批准→部署；之后替换产物哈希 | 有关联测试（PASSED 21, SKIPPED 1），待核对覆盖范围 |
| AC-55 | REQ-007, REQ-047 | G1 必需审批，模型/用户尝试直接 POST 创建；GateEvaluator 重试；optional 用户触发 | 有关联测试（PASSED 5），待核对覆盖范围 |
| AC-56 | REQ-015, REQ-043, REQ-048 | Backend 与 Operations Expert 分别申请 `cap.deploy.production`，并尝试不带发布许可部署 | 有关联测试（PASSED 21, SKIPPED 1），待核对覆盖范围 |
| AC-57 | REQ-014, REQ-044 | 发布授权申请被拒/过期/权限冲突 | 有关联测试（PASSED 20），待核对覆盖范围 |
| AC-58 | REQ-016, REQ-041, REQ-044 | 安全回滚后整改部署配置并再次尝试 | 有关联测试（PASSED 2），待核对覆盖范围 |
| AC-59 | REQ-018, REQ-041, REQ-049 | G2 拒绝指向产品/架构/代码，G1 拒绝产品/架构，G3 失败修复或终止 | 有关联测试（PASSED 22），待核对覆盖范围 |

## 原始断言目标及关联测试

### AC-01

验收目标：无 Leader 逐轮审批事件；最终出口由 Product Leader 验收

- `src/agentloop/tests/test_ac_delivery.py::test_local_rework_skips_leader_and_waits_for_explicit_simulation_authorization`：PASSED

### AC-02

验收目标：只回产品 Worker；G1 不可开始

- 历史报告未关联测试；需人工检索现有测试并核对其断言，缺失时补测。

### AC-03

验收目标：Router 只向 Product Leader 生成整改工单

- `src/agentloop/tests/test_ac_delivery.py::test_product_audit_rejection_routes_to_product_leader`：PASSED

### AC-04

验收目标：G1 保持 PENDING / 不可通过，研发不可开始

- 历史报告未关联测试；需人工检索现有测试并核对其断言，缺失时补测。

### AC-05

验收目标：Engineering 输入校验拒绝启动

- 历史报告未关联测试；需人工检索现有测试并核对其断言，缺失时补测。

### AC-06

验收目标：内部直接分配 Backend，修复再测试；无逐轮 Leader 审批

- `src/agentloop/tests/test_ac_delivery.py::test_local_rework_skips_leader_and_waits_for_explicit_simulation_authorization`：PASSED
- `src/agentloop/tests/test_ac_delivery.py::test_unexpected_node_exception_blocks_run_with_evidence_and_stays_resumable`：PASSED
- `src/agentloop/tests/test_ac_java_integration.py::test_real_spring_http_bug_is_repaired_and_fixed_tests_remain_unchanged[False]`：SKIPPED
- `src/agentloop/tests/test_ac_java_integration.py::test_real_spring_http_bug_is_repaired_and_fixed_tests_remain_unchanged[True]`：SKIPPED

### AC-07

验收目标：由 Testing 修复，不把 Bug 错归 Backend

- 历史报告未关联测试；需人工检索现有测试并核对其断言，缺失时补测。

### AC-08

验收目标：停止 Loop、生成阻塞与升级事件

- `src/agentloop/tests/test_ac_delivery.py::test_repeated_test_failure_is_bounded`：PASSED

### AC-09

验收目标：回研发内部，不进入安全审计

- `src/agentloop/tests/test_ac_delivery.py::test_leader_and_ux_rejection_reenter_bounded_local_loop[engineering-leader]`：PASSED
- `src/agentloop/tests/test_ac_delivery.py::test_leader_and_ux_rejection_reenter_bounded_local_loop[ux-agent]`：PASSED

### AC-10

验收目标：G2 拒绝；发布授权/部署工具不可执行

- `src/agentloop/tests/test_ac_approvals.py::test_g2_blocks_hard_findings[CRITICAL]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_g2_blocks_hard_findings[HIGH]`：PASSED
- `src/agentloop/tests/test_ac_delivery.py::test_high_security_finding_blocks_g2_even_after_passing_tests[CRITICAL]`：PASSED
- `src/agentloop/tests/test_ac_delivery.py::test_high_security_finding_blocks_g2_even_after_passing_tests[HIGH]`：PASSED
- `src/agentloop/tests/test_ac_security_remediation.py::test_crash_after_remediation_commit_reuses_evidence_and_enters_leader_once[EXTERNAL_REWORK]`：PASSED
- `src/agentloop/tests/test_ac_security_remediation.py::test_crash_after_remediation_commit_reuses_evidence_and_enters_leader_once[ISSUE_RESOLVED]`：PASSED
- `src/agentloop/tests/test_ac_security_remediation.py::test_g2_verified_code_finding_reenters_leader_and_resolves_only_after_revalidation`：PASSED
- `src/agentloop/tests/test_ac_security_remediation.py::test_issue_cannot_be_resolved_using_failed_or_old_delivery_proof[failed_test]`：PASSED
- `src/agentloop/tests/test_ac_security_remediation.py::test_issue_cannot_be_resolved_using_failed_or_old_delivery_proof[stale_review]`：PASSED
- `src/agentloop/tests/test_ac_security_remediation.py::test_security_demo_profile_survives_reopen_without_repeating_the_flag`：PASSED
- `src/agentloop/tests/test_ac_security_remediation.py::test_unfixed_security_findings_stay_open_and_cannot_loop_forever[False]`：PASSED
- `src/agentloop/tests/test_ac_security_remediation.py::test_unfixed_security_findings_stay_open_and_cannot_loop_forever[True]`：PASSED
- `src/agentloop/tests/test_ac_security_remediation.py::test_unknown_expert_root_cause_stays_unassigned_and_cannot_be_auto_resolved`：PASSED

### AC-11

验收目标：G2 拒绝，记录证据/路由整改

- `src/agentloop/tests/test_ac_delivery.py::test_high_security_finding_blocks_g2_even_after_passing_tests[CRITICAL]`：PASSED
- `src/agentloop/tests/test_ac_delivery.py::test_high_security_finding_blocks_g2_even_after_passing_tests[HIGH]`：PASSED
- `src/agentloop/tests/test_ac_java_integration.py::test_real_spring_http_bug_is_repaired_and_fixed_tests_remain_unchanged[False]`：SKIPPED
- `src/agentloop/tests/test_ac_java_integration.py::test_real_spring_http_bug_is_repaired_and_fixed_tests_remain_unchanged[True]`：SKIPPED
- `src/agentloop/tests/test_phase3_parallel.py::test_frontend_dynamic_code_is_independently_rejected_then_repaired`：PASSED

### AC-12

验收目标：SideEffectExecutor 拒绝生产部署

- `src/agentloop/tests/test_phase3_operations.py::test_independent_executor_requires_capability_and_exact_authorization[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_independent_executor_requires_capability_and_exact_authorization[sqlite]`：PASSED

### AC-13

验收目标：不交付，进入回滚或对账并留证据

- `src/agentloop/tests/test_ac_approvals.py::test_unbacked_g3_claim_cannot_pass_even_if_health_is_true[False]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_unbacked_g3_claim_cannot_pass_even_if_health_is_true[None]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_unbacked_g3_claim_cannot_pass_even_if_health_is_true[True]`：PASSED

### AC-14

验收目标：两个 Agent 生效快照含各自准确模型和版本

- `src/agentloop/tests/test_phase2_runtime.py::test_managed_runtime_is_wired_into_persistent_delivery_workflow[False]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_managed_runtime_is_wired_into_persistent_delivery_workflow[True]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_model_tool_request_goes_through_broker[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_model_tool_request_goes_through_broker[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_real_http_mcp_session_and_sse[False]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_real_http_mcp_session_and_sse[True]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_roles_have_distinct_persistent_model_snapshots[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_roles_have_distinct_persistent_model_snapshots[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_two_agents_concurrently_use_distinct_models_skills_and_mcp_views[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_two_agents_concurrently_use_distinct_models_skills_and_mcp_views[sqlite]`：PASSED

### AC-15

验收目标：工具拒绝；拒绝事件包含有效策略 ID

- `src/agentloop/tests/test_phase2_runtime.py::test_discovery_does_not_start_servers_outside_effective_capabilities[memory-None]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_discovery_does_not_start_servers_outside_effective_capabilities[memory-cap.deploy.production]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_discovery_does_not_start_servers_outside_effective_capabilities[memory-cap.memory.review]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_discovery_does_not_start_servers_outside_effective_capabilities[sqlite-None]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_discovery_does_not_start_servers_outside_effective_capabilities[sqlite-cap.deploy.production]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_discovery_does_not_start_servers_outside_effective_capabilities[sqlite-cap.memory.review]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_four_layers_intersect_permissions_and_deny_wins[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_four_layers_intersect_permissions_and_deny_wins[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_mutating_tool_requires_exact_one_time_human_approval[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_mutating_tool_requires_exact_one_time_human_approval[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_pending_tool_approval_preserves_reviewable_arguments_without_credentials[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_pending_tool_approval_preserves_reviewable_arguments_without_credentials[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_production_and_memory_tools_always_require_independent_executor[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_production_and_memory_tools_always_require_independent_executor[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_real_stdio_mcp_approval_schema_audit_idempotency_and_no_escalation[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_real_stdio_mcp_approval_schema_audit_idempotency_and_no_escalation[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_tool_path_and_network_arguments_are_enforced[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_tool_path_and_network_arguments_are_enforced[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_two_agents_concurrently_use_distinct_models_skills_and_mcp_views[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_two_agents_concurrently_use_distinct_models_skills_and_mcp_views[sqlite]`：PASSED

### AC-16

验收目标：隔离且脚本不可执行；记录来源和风险

- `src/agentloop/tests/test_phase2_runtime.py::test_skill_archive_traversal_rejected[memory-../escape]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_skill_archive_traversal_rejected[memory-C:/escape]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_skill_archive_traversal_rejected[memory-a\\escape]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_skill_archive_traversal_rejected[sqlite-../escape]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_skill_archive_traversal_rejected[sqlite-C:/escape]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_skill_archive_traversal_rejected[sqlite-a\\escape]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_skill_missing_dependency_cannot_publish[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_skill_missing_dependency_cannot_publish[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_skill_quarantine_approval_binding_hash_pinning_and_injection[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_skill_quarantine_approval_binding_hash_pinning_and_injection[sqlite]`：PASSED

### AC-17

验收目标：当前 Run 使用原固定版本哈希

- `src/agentloop/tests/test_ac_delivery.py::test_configuration_cannot_be_replaced_when_resuming`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_mcp_upgrade_keeps_existing_run_pinned[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_mcp_upgrade_keeps_existing_run_pinned[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_skill_quarantine_approval_binding_hash_pinning_and_injection[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_skill_quarantine_approval_binding_hash_pinning_and_injection[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_snapshot_immutable_and_verified_response_cached[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_snapshot_immutable_and_verified_response_cached[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_stdio_entrypoint_changed_after_approval_cannot_execute[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_stdio_entrypoint_changed_after_approval_cannot_execute[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_two_agents_concurrently_use_distinct_models_skills_and_mcp_views[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_two_agents_concurrently_use_distinct_models_skills_and_mcp_views[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_cli.py::test_cli_deploy_is_idempotent_and_agent_remains_live_after_command`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_periodic_maintenance_child_and_incident_leave_parent_unchanged[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_periodic_maintenance_child_and_incident_leave_parent_unchanged[sqlite]`：PASSED

### AC-18

验收目标：不创建 RETROSPECTIVE 子 Run

- `src/agentloop/tests/test_phase4_knowledge.py::test_no_retrospective_without_explicit_user_trigger[memory]`：PASSED
- `src/agentloop/tests/test_phase4_knowledge.py::test_no_retrospective_without_explicit_user_trigger[sqlite]`：PASSED
- `src/agentloop/tests/test_phase5_http.py::test_http_retrospective_review_revoke_and_restart`：PASSED

### AC-19

验收目标：生成子 Run，收集全部阶段材料并关联证据哈希

- `src/agentloop/tests/test_phase4_knowledge.py::test_manual_trigger_creates_child_run_and_freezes_all_evidence[memory]`：PASSED
- `src/agentloop/tests/test_phase4_knowledge.py::test_manual_trigger_creates_child_run_and_freezes_all_evidence[sqlite]`：PASSED
- `src/agentloop/tests/test_phase5_http.py::test_http_retrospective_review_revoke_and_restart`：PASSED

### AC-20

验收目标：报告包含问题根因、保持做法、证据及验证计划

- `src/agentloop/tests/test_phase4_knowledge.py::test_report_follows_fixed_template_with_resolvable_evidence[memory]`：PASSED
- `src/agentloop/tests/test_phase4_knowledge.py::test_report_follows_fixed_template_with_resolvable_evidence[sqlite]`：PASSED

### AC-21

验收目标：未经测试和授权不能发布到 Agent 生效配置

- `src/agentloop/tests/test_phase4_knowledge.py::test_evolution_proposal_needs_verification_and_never_touches_effective_config[memory]`：PASSED
- `src/agentloop/tests/test_phase4_knowledge.py::test_evolution_proposal_needs_verification_and_never_touches_effective_config[sqlite]`：PASSED

### AC-22

验收目标：待审与越权命名空间内容均不可检索

- `src/agentloop/tests/test_phase4_knowledge.py::test_memory_visibility_is_scope_and_status_filtered[memory]`：PASSED
- `src/agentloop/tests/test_phase4_knowledge.py::test_memory_visibility_is_scope_and_status_filtered[sqlite]`：PASSED
- `src/agentloop/tests/test_phase5_http.py::test_http_retrospective_review_revoke_and_restart`：PASSED

### AC-23

验收目标：标记失效或待复核，不静默覆盖

- `src/agentloop/tests/test_phase4_knowledge.py::test_conflicting_memory_supersedes_instead_of_overwriting[memory]`：PASSED
- `src/agentloop/tests/test_phase4_knowledge.py::test_conflicting_memory_supersedes_instead_of_overwriting[sqlite]`：PASSED

### AC-24

验收目标：Run 恢复状态，已确认的副作用不得重复提交

- `src/agentloop/tests/test_ac_delivery.py::test_patch_committed_before_crash_is_replayed_without_a_second_model_proposal`：PASSED
- `src/agentloop/tests/test_ac_delivery.py::test_reopen_g1_uses_original_configuration_and_cached_department_outputs`：PASSED
- `src/agentloop/tests/test_ac_recovery.py::test_separate_processes_resume_original_checkpoint_without_duplicate_events`：PASSED
- `src/agentloop/tests/test_ac_security_remediation.py::test_crash_after_remediation_commit_reuses_evidence_and_enters_leader_once[EXTERNAL_REWORK]`：PASSED
- `src/agentloop/tests/test_ac_security_remediation.py::test_crash_after_remediation_commit_reuses_evidence_and_enters_leader_once[ISSUE_RESOLVED]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_uncertain_mcp_effect_is_not_replayed_after_restart[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_uncertain_mcp_effect_is_not_replayed_after_restart[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_late_deploy_response_does_not_overwrite_confirmed_rollback[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_late_deploy_response_does_not_overwrite_confirmed_rollback[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_unknown_rollback_requires_query_and_cannot_be_replayed[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_unknown_rollback_requires_query_and_cannot_be_replayed[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_parallel.py::test_git_ref_updated_but_database_not_committed_is_recovered`：PASSED
- `src/agentloop/tests/test_phase3_parallel.py::test_merge_recovery_preserves_even_whitespace_only_external_edits`：PASSED

### AC-25

验收目标：依赖的测试/评审/确认按影响规则 STALE

- `src/agentloop/tests/test_ac_workspace_evidence.py::test_archive_verifies_original_bytes_and_run_scope`：PASSED

### AC-26

验收目标：新建 MAINTENANCE 子 Run，父交付保持 COMPLETED

- 历史报告未关联测试；需人工检索现有测试并核对其断言，缺失时补测。

### AC-27

验收目标：生成带证据的澄清问题，Run=PAUSED_FOR_HUMAN；有权用户答复后从 checkpoint 恢复

- `src/agentloop/tests/test_ac_recovery.py::test_multiple_questions_restore_original_wait_state_only_after_all_answers`：PASSED
- `src/agentloop/tests/test_ac_recovery.py::test_separate_processes_resume_original_checkpoint_without_duplicate_events`：PASSED

### AC-28

验收目标：未审批 G1 保持 PENDING，研发被阻断；指定版本人工批准才通过

- `src/agentloop/tests/test_ac_approvals.py::test_approval_decision_uses_server_identity_and_project_roles[agent]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_approval_decision_uses_server_identity_and_project_roles[approver]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_approval_decision_uses_server_identity_and_project_roles[outsider]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_approval_decision_uses_server_identity_and_project_roles[system]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_g1_waits_for_both_approvals_then_rechecks_same_pending_record`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_project_policy_and_risk_trigger_control_required_confirmations[policy0-triggers0-1]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_project_policy_and_risk_trigger_control_required_confirmations[policy1-triggers1-0]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_project_policy_and_risk_trigger_control_required_confirmations[policy2-triggers2-2]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_revoked_approval_is_recreated_with_bumped_version`：PASSED
- `src/agentloop/tests/test_ac_delivery.py::test_g1_checkpoint_blocks_all_backend_calls_until_human_confirmation`：PASSED

### AC-29

验收目标：Leader + 专家通过后 G1 可放行，不产生额外审批阻塞

- `src/agentloop/tests/test_ac_approvals.py::test_optional_confirmation_disabled_for_this_run`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_periodic_maintenance_child_and_incident_leave_parent_unchanged[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_periodic_maintenance_child_and_incident_leave_parent_unchanged[sqlite]`：PASSED

### AC-30

验收目标：服务端拒绝，产生授权拒绝审计

- `src/agentloop/tests/test_ac_approvals.py::test_human_release_approver_issues_bound_authorization`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_release_approval_rejects_unauthorized_people_and_services[agent]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_release_approval_rejects_unauthorized_people_and_services[outsider]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_release_approval_rejects_unauthorized_people_and_services[owner]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_release_approval_rejects_unauthorized_people_and_services[system]`：PASSED

### AC-31

验收目标：任一条件失败拒绝部署；不会消耗错误产物权限

- 历史报告未关联测试；需人工检索现有测试并核对其断言，缺失时补测。

### AC-32

验收目标：正交枚举存储与转移校验正确；每个 GateResult 状态可独立查询

- `src/agentloop/tests/test_ac_state_machine.py::test_ac32_phase_and_status_are_independent_enums`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac46_cannot_complete_while_gate_pending`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_composite_guard_blocks_gate_with_created_status`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_concurrent_state_version_conflict_preserves_state`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_delivery_is_the_only_successful_terminal`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_exhaustive_phase_whitelist`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_g1_rejection_routes_to_upstream_phases`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_gate_result_whitelist_is_terminal_after_reject`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_recovery_phase_accepts_only_recovery_statuses`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_terminal_status_cannot_revive`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_noop_transition_keeps_version_and_event_log`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_snapshot_immutable_and_verified_response_cached[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_snapshot_immutable_and_verified_response_cached[sqlite]`：PASSED

### AC-33

验收目标：Schema 拒绝字段；Router 根据类别和归属表决定目标

- `src/agentloop/tests/test_ac_routing.py::test_agent_cannot_submit_server_owned_fields[issue-final_gate_result]`：PASSED
- `src/agentloop/tests/test_ac_routing.py::test_agent_cannot_submit_server_owned_fields[issue-routed_leader]`：PASSED
- `src/agentloop/tests/test_ac_routing.py::test_agent_cannot_submit_server_owned_fields[issue-target_leader]`：PASSED
- `src/agentloop/tests/test_ac_routing.py::test_agent_cannot_submit_server_owned_fields[report-final_gate_result]`：PASSED
- `src/agentloop/tests/test_ac_routing.py::test_agent_cannot_submit_server_owned_fields[report-routed_leader]`：PASSED
- `src/agentloop/tests/test_ac_routing.py::test_agent_cannot_submit_server_owned_fields[report-target_leader]`：PASSED
- `src/agentloop/tests/test_ac_routing.py::test_empty_evidence_is_rejected`：PASSED
- `src/agentloop/tests/test_ac_routing.py::test_router_binds_agent_identity_and_rejects_reused_key_payload`：PASSED

### AC-34

验收目标：UX/Code Review 按规则触发或跳过，事件记录触发原因

- `src/agentloop/tests/test_ac_delivery.py::test_leader_and_ux_rejection_reenter_bounded_local_loop[engineering-leader]`：PASSED
- `src/agentloop/tests/test_ac_delivery.py::test_leader_and_ux_rejection_reenter_bounded_local_loop[ux-agent]`：PASSED
- `src/agentloop/tests/test_ac_delivery.py::test_review_failure_returns_directly_to_backend`：PASSED
- `src/agentloop/tests/test_ac_delivery.py::test_ux_and_production_review_triggers_are_recorded[False]`：PASSED
- `src/agentloop/tests/test_ac_delivery.py::test_ux_and_production_review_triggers_are_recorded[True]`：PASSED

### AC-35

验收目标：创建 INCIDENT 子 Run，`parent_run_id/root_run_id` 链接正确

- 历史报告未关联测试；需人工检索现有测试并核对其断言，缺失时补测。

### AC-36

验收目标：产生待审候选或拒绝；正式记忆和权限不变

- `src/agentloop/tests/test_phase4_knowledge.py::test_injected_governance_instructions_never_enter_pending_queue[memory]`：PASSED
- `src/agentloop/tests/test_phase4_knowledge.py::test_injected_governance_instructions_never_enter_pending_queue[sqlite]`：PASSED

### AC-37

验收目标：阻断新模型调用、记账、生成预算审批；不能通过 fallback 逃逸

- `src/agentloop/tests/test_phase2_runtime.py::test_atomic_reservation_prevents_concurrent_overspend[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_atomic_reservation_prevents_concurrent_overspend[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_budget_approval_requires_human_owner_and_does_not_reset_usage[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_budget_approval_requires_human_owner_and_does_not_reset_usage[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_child_run_cannot_reset_parent_budget[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_child_run_cannot_reset_parent_budget[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_fallback_cannot_get_fresh_budget_after_uncertain_charge[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_fallback_cannot_get_fresh_budget_after_uncertain_charge[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_hard_budget_blocks_before_provider_and_creates_request[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_hard_budget_blocks_before_provider_and_creates_request[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_managed_runtime_is_wired_into_persistent_delivery_workflow[False]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_managed_runtime_is_wired_into_persistent_delivery_workflow[True]`：PASSED

### AC-38

验收目标：严格拒绝生效、有限次数修复；失败后 BLOCKED，无虚假 PASS

- `src/agentloop/tests/test_ac_workspace_evidence.py::test_all_changes_are_validated_before_first_write`：PASSED
- `src/agentloop/tests/test_ac_workspace_evidence.py::test_backend_cannot_change_tests_build_config_or_escape_workspace[../outside]`：PASSED
- `src/agentloop/tests/test_ac_workspace_evidence.py::test_backend_cannot_change_tests_build_config_or_escape_workspace[/absolute]`：PASSED
- `src/agentloop/tests/test_ac_workspace_evidence.py::test_backend_cannot_change_tests_build_config_or_escape_workspace[C:/outside]`：PASSED
- `src/agentloop/tests/test_ac_workspace_evidence.py::test_backend_cannot_change_tests_build_config_or_escape_workspace[pom.xml]`：PASSED
- `src/agentloop/tests/test_ac_workspace_evidence.py::test_backend_cannot_change_tests_build_config_or_escape_workspace[src/test/java/example/HelloControllerTest.java]`：PASSED
- `src/agentloop/tests/test_ac_workspace_evidence.py::test_backend_cannot_change_tests_build_config_or_escape_workspace[src\\main\\escape]`：PASSED
- `src/agentloop/tests/test_ac_workspace_evidence.py::test_executor_uses_junit_and_exit_status_instead_of_text[exit-mismatch-INCONCLUSIVE]`：PASSED
- `src/agentloop/tests/test_ac_workspace_evidence.py::test_executor_uses_junit_and_exit_status_instead_of_text[fail-FAIL]`：PASSED
- `src/agentloop/tests/test_ac_workspace_evidence.py::test_executor_uses_junit_and_exit_status_instead_of_text[missing-INCONCLUSIVE]`：PASSED
- `src/agentloop/tests/test_ac_workspace_evidence.py::test_executor_uses_junit_and_exit_status_instead_of_text[pass-PASS]`：PASSED
- `src/agentloop/tests/test_ac_workspace_evidence.py::test_executor_uses_junit_and_exit_status_instead_of_text[skipped-INCONCLUSIVE]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_managed_runtime_is_wired_into_persistent_delivery_workflow[False]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_managed_runtime_is_wired_into_persistent_delivery_workflow[True]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_schema_repair_bounded_no_invalid_reply[memory-False]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_schema_repair_bounded_no_invalid_reply[memory-True]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_schema_repair_bounded_no_invalid_reply[sqlite-False]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_schema_repair_bounded_no_invalid_reply[sqlite-True]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_schema_repair_ceiling_is_shared_by_primary_and_fallback[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_schema_repair_ceiling_is_shared_by_primary_and_fallback[sqlite]`：PASSED

### AC-39

验收目标：Agent 最终工具调用仍被 ACL/Gate 拦截，记录注入事件

- `src/agentloop/tests/test_phase2_runtime.py::test_discovery_does_not_start_servers_outside_effective_capabilities[memory-None]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_discovery_does_not_start_servers_outside_effective_capabilities[memory-cap.deploy.production]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_discovery_does_not_start_servers_outside_effective_capabilities[memory-cap.memory.review]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_discovery_does_not_start_servers_outside_effective_capabilities[sqlite-None]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_discovery_does_not_start_servers_outside_effective_capabilities[sqlite-cap.deploy.production]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_discovery_does_not_start_servers_outside_effective_capabilities[sqlite-cap.memory.review]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_mcp_echoed_secret_is_redacted_before_persistence[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_mcp_echoed_secret_is_redacted_before_persistence[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_model_tool_request_goes_through_broker[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_model_tool_request_goes_through_broker[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_mutating_tool_requires_exact_one_time_human_approval[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_mutating_tool_requires_exact_one_time_human_approval[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_pending_tool_approval_preserves_reviewable_arguments_without_credentials[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_pending_tool_approval_preserves_reviewable_arguments_without_credentials[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_production_and_memory_tools_always_require_independent_executor[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_production_and_memory_tools_always_require_independent_executor[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_real_stdio_mcp_approval_schema_audit_idempotency_and_no_escalation[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_real_stdio_mcp_approval_schema_audit_idempotency_and_no_escalation[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_skill_quarantine_approval_binding_hash_pinning_and_injection[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_skill_quarantine_approval_binding_hash_pinning_and_injection[sqlite]`：PASSED

### AC-40

验收目标：使用已授权后备模型完成或明确失败，记录模型链及成本，权限不扩张

- `src/agentloop/tests/test_phase2_runtime.py::test_fallback_cannot_get_fresh_budget_after_uncertain_charge[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_fallback_cannot_get_fresh_budget_after_uncertain_charge[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_invalid_fallback_rejected_before_calls[memory-model]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_invalid_fallback_rejected_before_calls[memory-network]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_invalid_fallback_rejected_before_calls[memory-residency]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_invalid_fallback_rejected_before_calls[memory-secret]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_invalid_fallback_rejected_before_calls[memory-structured]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_invalid_fallback_rejected_before_calls[memory-tools]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_invalid_fallback_rejected_before_calls[sqlite-model]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_invalid_fallback_rejected_before_calls[sqlite-network]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_invalid_fallback_rejected_before_calls[sqlite-residency]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_invalid_fallback_rejected_before_calls[sqlite-secret]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_invalid_fallback_rejected_before_calls[sqlite-structured]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_invalid_fallback_rejected_before_calls[sqlite-tools]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_retry_then_authorized_fallback_same_ledger[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_retry_then_authorized_fallback_same_ledger[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_roles_have_distinct_persistent_model_snapshots[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_roles_have_distinct_persistent_model_snapshots[sqlite]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_schema_repair_ceiling_is_shared_by_primary_and_fallback[memory]`：PASSED
- `src/agentloop/tests/test_phase2_runtime.py::test_schema_repair_ceiling_is_shared_by_primary_and_fallback[sqlite]`：PASSED

### AC-41

验收目标：硬阻断一律拒绝；仅受政策允许且有效的非阻断豁免可生效

- 历史报告未关联测试；需人工检索现有测试并核对其断言，缺失时补测。

### AC-42

验收目标：不继续新增调用；查外部状态并回滚/对账；未知则 NEEDS_RECONCILIATION

- `src/agentloop/tests/test_phase3_operations.py::test_cancel_between_preparation_and_dispatch_sends_no_request[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_cancel_between_preparation_and_dispatch_sends_no_request[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_cancel_sent_deployment_reconciles_then_compensates[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_cancel_sent_deployment_reconciles_then_compensates[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_cancel_unknown_operation_never_claims_no_effects[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_cancel_unknown_operation_never_claims_no_effects[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_cancellation_before_any_deployment_does_not_require_an_ops_snapshot[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_cancellation_before_any_deployment_does_not_require_an_ops_snapshot[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_late_deploy_response_does_not_overwrite_confirmed_rollback[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_late_deploy_response_does_not_overwrite_confirmed_rollback[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_recovery_cannot_be_cancelled_without_verified_safe_environment[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_recovery_cannot_be_cancelled_without_verified_safe_environment[sqlite]`：PASSED

### AC-43

验收目标：产生冲突工单，解决后基于最终合并 Commit 重验

- `src/agentloop/tests/test_phase3_integration.py::test_real_multi_role_delivery_authorized_http_publish_and_periodic_check`：SKIPPED
- `src/agentloop/tests/test_phase3_parallel.py::test_git_ref_updated_but_database_not_committed_is_recovered`：PASSED
- `src/agentloop/tests/test_phase3_parallel.py::test_isolated_branches_merge_disjoint_changes_and_require_final_retest`：PASSED
- `src/agentloop/tests/test_phase3_parallel.py::test_merge_recovery_preserves_even_whitespace_only_external_edits`：PASSED
- `src/agentloop/tests/test_phase3_parallel.py::test_real_conflict_is_recorded_without_overwrite_then_resolved`：PASSED
- `src/agentloop/tests/test_phase3_parallel.py::test_three_role_worktrees_feed_final_commit_review_and_tests`：PASSED

### AC-44

验收目标：旧 Approval 与依赖 Gate STALE，需新批准

- `src/agentloop/tests/test_ac_approvals.py::test_invalid_g1_decisions_never_pass[baseline_changed]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_invalid_g1_decisions_never_pass[expired]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_invalid_g1_decisions_never_pass[rejected]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_passed_g1_rechecks_approval_at_time_of_use[expired]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_passed_g1_rechecks_approval_at_time_of_use[principal_disabled]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_passed_g1_rechecks_approval_at_time_of_use[role_expired]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_revocation_invalidates_passed_gate`：PASSED
- `src/agentloop/tests/test_ac_workspace_evidence.py::test_stale_patch_is_rejected_without_commit_change`：PASSED

### AC-45

验收目标：不猜测目标，创建 UNASSIGNED 或多责任工单并升级

- `src/agentloop/tests/test_ac_routing.py::test_free_text_does_not_override_structured_routing`：PASSED
- `src/agentloop/tests/test_ac_routing.py::test_unknown_or_conflicting_responsibility_is_escalated[CODE_DEFECT-SPEC_DEFECT]`：PASSED
- `src/agentloop/tests/test_ac_routing.py::test_unknown_or_conflicting_responsibility_is_escalated[SECURITY_FINDING-None]`：PASSED
- `src/agentloop/tests/test_ac_routing.py::test_unknown_or_conflicting_responsibility_is_escalated[UNCLASSIFIED-None]`：PASSED

### AC-46

验收目标：状态服务拒绝非法跃迁并保留原状态

- `src/agentloop/tests/test_ac_approvals.py::test_older_pass_cannot_override_latest_rejection`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_unbacked_g3_claim_cannot_pass_even_if_health_is_true[False]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_unbacked_g3_claim_cannot_pass_even_if_health_is_true[None]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_unbacked_g3_claim_cannot_pass_even_if_health_is_true[True]`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac32_phase_and_status_are_independent_enums`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac46_cannot_complete_while_gate_pending`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_composite_guard_blocks_gate_with_created_status`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_concurrent_state_version_conflict_preserves_state`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_delivery_is_the_only_successful_terminal`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_exhaustive_phase_whitelist`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_g1_rejection_routes_to_upstream_phases`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_gate_result_whitelist_is_terminal_after_reject`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_recovery_phase_accepts_only_recovery_statuses`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_terminal_status_cannot_revive`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_noop_transition_keeps_version_and_event_log`：PASSED

### AC-47

验收目标：只有三部门，Testing 归 engineering；内部自动流转可用

- 历史报告未关联测试；需人工检索现有测试并核对其断言，缺失时补测。

### AC-48

验收目标：权限拒绝；不能借 Run ID 绕过项目隔离

- `src/agentloop/tests/test_ac_recovery.py::test_other_project_and_agent_cannot_answer_clarification[agent]`：PASSED
- `src/agentloop/tests/test_ac_recovery.py::test_other_project_and_agent_cannot_answer_clarification[outsider]`：PASSED

### AC-49

验收目标：新 G3=REJECTED；Run=`(DEPLOYMENT_RECOVERY, BLOCKED)`；保存对账证据和整改工单；绝不标记 COMPLETED

- `src/agentloop/tests/test_phase3_operations.py::test_approver_revoked_after_dispatch_does_not_produce_a_g3_pass[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_approver_revoked_after_dispatch_does_not_produce_a_g3_pass[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_g3_failure_safe_rollback_then_new_authorized_attempt[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_g3_failure_safe_rollback_then_new_authorized_attempt[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_new_p1_during_deployment_rejects_g3_and_recovers_instead_of_hanging[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_new_p1_during_deployment_rejects_g3_and_recovers_instead_of_hanging[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_termination_requires_safe_rollback_evidence[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_termination_requires_safe_rollback_evidence[sqlite]`：PASSED

### AC-50

验收目标：Run=`(DEPLOYMENT_RECOVERY, NEEDS_RECONCILIATION)`，新部署被阻断；人工对账后才允许转 BLOCKED/终止

- `src/agentloop/tests/test_phase3_operations.py::test_first_deploy_failure_without_baseline_verifies_target_and_unblocks[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_first_deploy_failure_without_baseline_verifies_target_and_unblocks[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_reconcile_of_never_dispatched_effect_settles_cancelled_and_frees_target[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_reconcile_of_never_dispatched_effect_settles_cancelled_and_frees_target[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_recovery_cannot_be_cancelled_without_verified_safe_environment[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_recovery_cannot_be_cancelled_without_verified_safe_environment[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_successful_rollback_without_healthy_environment_remains_unreconciled[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_successful_rollback_without_healthy_environment_remains_unreconciled[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_unknown_rollback_requires_query_and_cannot_be_replayed[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_unknown_rollback_requires_query_and_cannot_be_replayed[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_unsent_rollback_after_expiry_can_receive_new_exact_recovery_permission[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_unsent_rollback_after_expiry_can_receive_new_exact_recovery_permission[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_unverifiable_first_deploy_failure_waits_for_manual_reconciliation[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_unverifiable_first_deploy_failure_waits_for_manual_reconciliation[sqlite]`：PASSED

### AC-51

验收目标：只接受表内合法跃迁，非法状态写入返回 409 且事件/状态不变

- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[NOT_EVALUATED-NOT_EVALUATED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[NOT_EVALUATED-PASSED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[NOT_EVALUATED-PENDING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[NOT_EVALUATED-REJECTED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[NOT_EVALUATED-STALE]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[PASSED-NOT_EVALUATED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[PASSED-PASSED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[PASSED-PENDING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[PASSED-REJECTED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[PASSED-STALE]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[PENDING-NOT_EVALUATED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[PENDING-PASSED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[PENDING-PENDING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[PENDING-REJECTED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[PENDING-STALE]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[REJECTED-NOT_EVALUATED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[REJECTED-PASSED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[REJECTED-PENDING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[REJECTED-REJECTED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[REJECTED-STALE]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[STALE-NOT_EVALUATED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[STALE-PASSED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[STALE-PENDING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[STALE-REJECTED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_gate_transition_matrix[STALE-STALE]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_phase_table_matches_authoritative_specification`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[BLOCKED-BLOCKED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[BLOCKED-CANCELLED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[BLOCKED-CANCELLING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[BLOCKED-CANCEL_REQUESTED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[BLOCKED-COMPLETED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[BLOCKED-CREATED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[BLOCKED-FAILED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[BLOCKED-NEEDS_RECONCILIATION]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[BLOCKED-PAUSED_FOR_HUMAN]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[BLOCKED-RUNNING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[BLOCKED-WAITING_APPROVAL]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[BLOCKED-WAITING_GATE]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLED-BLOCKED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLED-CANCELLED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLED-CANCELLING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLED-CANCEL_REQUESTED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLED-COMPLETED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLED-CREATED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLED-FAILED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLED-NEEDS_RECONCILIATION]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLED-PAUSED_FOR_HUMAN]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLED-RUNNING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLED-WAITING_APPROVAL]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLED-WAITING_GATE]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLING-BLOCKED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLING-CANCELLED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLING-CANCELLING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLING-CANCEL_REQUESTED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLING-COMPLETED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLING-CREATED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLING-FAILED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLING-NEEDS_RECONCILIATION]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLING-PAUSED_FOR_HUMAN]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLING-RUNNING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLING-WAITING_APPROVAL]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCELLING-WAITING_GATE]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCEL_REQUESTED-BLOCKED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCEL_REQUESTED-CANCELLED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCEL_REQUESTED-CANCELLING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCEL_REQUESTED-CANCEL_REQUESTED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCEL_REQUESTED-COMPLETED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCEL_REQUESTED-CREATED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCEL_REQUESTED-FAILED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCEL_REQUESTED-NEEDS_RECONCILIATION]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCEL_REQUESTED-PAUSED_FOR_HUMAN]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCEL_REQUESTED-RUNNING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCEL_REQUESTED-WAITING_APPROVAL]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CANCEL_REQUESTED-WAITING_GATE]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[COMPLETED-BLOCKED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[COMPLETED-CANCELLED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[COMPLETED-CANCELLING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[COMPLETED-CANCEL_REQUESTED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[COMPLETED-COMPLETED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[COMPLETED-CREATED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[COMPLETED-FAILED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[COMPLETED-NEEDS_RECONCILIATION]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[COMPLETED-PAUSED_FOR_HUMAN]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[COMPLETED-RUNNING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[COMPLETED-WAITING_APPROVAL]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[COMPLETED-WAITING_GATE]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CREATED-BLOCKED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CREATED-CANCELLED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CREATED-CANCELLING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CREATED-CANCEL_REQUESTED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CREATED-COMPLETED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CREATED-CREATED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CREATED-FAILED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CREATED-NEEDS_RECONCILIATION]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CREATED-PAUSED_FOR_HUMAN]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CREATED-RUNNING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CREATED-WAITING_APPROVAL]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[CREATED-WAITING_GATE]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[FAILED-BLOCKED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[FAILED-CANCELLED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[FAILED-CANCELLING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[FAILED-CANCEL_REQUESTED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[FAILED-COMPLETED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[FAILED-CREATED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[FAILED-FAILED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[FAILED-NEEDS_RECONCILIATION]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[FAILED-PAUSED_FOR_HUMAN]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[FAILED-RUNNING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[FAILED-WAITING_APPROVAL]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[FAILED-WAITING_GATE]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[NEEDS_RECONCILIATION-BLOCKED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[NEEDS_RECONCILIATION-CANCELLED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[NEEDS_RECONCILIATION-CANCELLING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[NEEDS_RECONCILIATION-CANCEL_REQUESTED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[NEEDS_RECONCILIATION-COMPLETED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[NEEDS_RECONCILIATION-CREATED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[NEEDS_RECONCILIATION-FAILED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[NEEDS_RECONCILIATION-NEEDS_RECONCILIATION]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[NEEDS_RECONCILIATION-PAUSED_FOR_HUMAN]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[NEEDS_RECONCILIATION-RUNNING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[NEEDS_RECONCILIATION-WAITING_APPROVAL]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[NEEDS_RECONCILIATION-WAITING_GATE]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[PAUSED_FOR_HUMAN-BLOCKED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[PAUSED_FOR_HUMAN-CANCELLED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[PAUSED_FOR_HUMAN-CANCELLING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[PAUSED_FOR_HUMAN-CANCEL_REQUESTED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[PAUSED_FOR_HUMAN-COMPLETED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[PAUSED_FOR_HUMAN-CREATED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[PAUSED_FOR_HUMAN-FAILED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[PAUSED_FOR_HUMAN-NEEDS_RECONCILIATION]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[PAUSED_FOR_HUMAN-PAUSED_FOR_HUMAN]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[PAUSED_FOR_HUMAN-RUNNING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[PAUSED_FOR_HUMAN-WAITING_APPROVAL]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[PAUSED_FOR_HUMAN-WAITING_GATE]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[RUNNING-BLOCKED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[RUNNING-CANCELLED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[RUNNING-CANCELLING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[RUNNING-CANCEL_REQUESTED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[RUNNING-COMPLETED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[RUNNING-CREATED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[RUNNING-FAILED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[RUNNING-NEEDS_RECONCILIATION]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[RUNNING-PAUSED_FOR_HUMAN]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[RUNNING-RUNNING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[RUNNING-WAITING_APPROVAL]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[RUNNING-WAITING_GATE]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_APPROVAL-BLOCKED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_APPROVAL-CANCELLED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_APPROVAL-CANCELLING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_APPROVAL-CANCEL_REQUESTED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_APPROVAL-COMPLETED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_APPROVAL-CREATED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_APPROVAL-FAILED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_APPROVAL-NEEDS_RECONCILIATION]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_APPROVAL-PAUSED_FOR_HUMAN]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_APPROVAL-RUNNING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_APPROVAL-WAITING_APPROVAL]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_APPROVAL-WAITING_GATE]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_GATE-BLOCKED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_GATE-CANCELLED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_GATE-CANCELLING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_GATE-CANCEL_REQUESTED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_GATE-COMPLETED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_GATE-CREATED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_GATE-FAILED]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_GATE-NEEDS_RECONCILIATION]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_GATE-PAUSED_FOR_HUMAN]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_GATE-RUNNING]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_GATE-WAITING_APPROVAL]`：PASSED
- `src/agentloop/tests/test_ac_matrices.py::test_status_transition_matrix[WAITING_GATE-WAITING_GATE]`：PASSED
- `src/agentloop/tests/test_ac_recovery.py::test_state_and_event_both_roll_back_on_event_write_failure`：PASSED
- `src/agentloop/tests/test_ac_recovery.py::test_two_sqlite_connections_do_not_overwrite_stale_state_version`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac32_phase_and_status_are_independent_enums`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac46_cannot_complete_while_gate_pending`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_composite_guard_blocks_gate_with_created_status`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_concurrent_state_version_conflict_preserves_state`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_delivery_is_the_only_successful_terminal`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_exhaustive_phase_whitelist`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_g1_rejection_routes_to_upstream_phases`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_gate_result_whitelist_is_terminal_after_reject`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_recovery_phase_accepts_only_recovery_statuses`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_ac51_terminal_status_cannot_revive`：PASSED
- `src/agentloop/tests/test_ac_state_machine.py::test_noop_transition_keeps_version_and_event_log`：PASSED

### AC-52

验收目标：审批角色/RBAC、过期/哈希、审计有效；P1/严重漏洞不能变 ACTIVE

- `src/agentloop/tests/test_phase3_governance.py::test_risk_waiver_approval_revoke_and_hard_risks_never_active[memory-CRITICAL]`：PASSED
- `src/agentloop/tests/test_phase3_governance.py::test_risk_waiver_approval_revoke_and_hard_risks_never_active[memory-HIGH]`：PASSED
- `src/agentloop/tests/test_phase3_governance.py::test_risk_waiver_approval_revoke_and_hard_risks_never_active[memory-LOW]`：PASSED
- `src/agentloop/tests/test_phase3_governance.py::test_risk_waiver_approval_revoke_and_hard_risks_never_active[memory-MEDIUM]`：PASSED
- `src/agentloop/tests/test_phase3_governance.py::test_risk_waiver_approval_revoke_and_hard_risks_never_active[sqlite-CRITICAL]`：PASSED
- `src/agentloop/tests/test_phase3_governance.py::test_risk_waiver_approval_revoke_and_hard_risks_never_active[sqlite-HIGH]`：PASSED
- `src/agentloop/tests/test_phase3_governance.py::test_risk_waiver_approval_revoke_and_hard_risks_never_active[sqlite-LOW]`：PASSED
- `src/agentloop/tests/test_phase3_governance.py::test_risk_waiver_approval_revoke_and_hard_risks_never_active[sqlite-MEDIUM]`：PASSED

### AC-53

验收目标：未审核不可检索；Agent 拒绝；真人审核后按命名空间原子生效或撤销，和 EvolutionProposal 不混淆

- `src/agentloop/tests/test_phase4_knowledge.py::test_memory_lifecycle_is_human_governed_and_separate_from_evolution[memory]`：PASSED
- `src/agentloop/tests/test_phase4_knowledge.py::test_memory_lifecycle_is_human_governed_and_separate_from_evolution[sqlite]`：PASSED
- `src/agentloop/tests/test_phase4_knowledge.py::test_queue_and_versions_never_cross_projects_and_rollback_is_audited[memory]`：PASSED
- `src/agentloop/tests/test_phase4_knowledge.py::test_queue_and_versions_never_cross_projects_and_rollback_is_audited[sqlite]`：PASSED
- `src/agentloop/tests/test_phase5_http.py::test_http_retrospective_review_revoke_and_restart`：PASSED

### AC-54

验收目标：Release/申请/许可/部署联动，旧许可对新产物不适用；缺少 Release 的请求拒绝

- `src/agentloop/tests/test_phase3_cli.py::test_cli_deploy_is_idempotent_and_agent_remains_live_after_command`：PASSED
- `src/agentloop/tests/test_phase3_governance.py::test_real_authenticated_http_agent_deploy_query_and_health[memory]`：PASSED
- `src/agentloop/tests/test_phase3_governance.py::test_real_authenticated_http_agent_deploy_query_and_health[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_integration.py::test_real_multi_role_delivery_authorized_http_publish_and_periodic_check`：SKIPPED
- `src/agentloop/tests/test_phase3_operations.py::test_actual_local_http_deployment_and_provider_restart[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_actual_local_http_deployment_and_provider_restart[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_independent_executor_requires_capability_and_exact_authorization[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_independent_executor_requires_capability_and_exact_authorization[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[memory-approver]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[memory-artifact]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[memory-expired]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[memory-revoked]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[memory-target]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[sqlite-approver]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[sqlite-artifact]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[sqlite-expired]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[sqlite-revoked]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[sqlite-target]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_revocation_between_prepare_and_dispatch_blocks_send[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_revocation_between_prepare_and_dispatch_blocks_send[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_target_cannot_be_repointed_while_deployment_lease_is_active[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_target_cannot_be_repointed_while_deployment_lease_is_active[sqlite]`：PASSED

### AC-55

验收目标：公开创建拒绝/不存在；内部幂等只生成一份同版本请求；只有人类决策端点可批准

- `src/agentloop/tests/test_ac_approvals.py::test_g1_waits_for_both_approvals_then_rechecks_same_pending_record`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_only_gate_evaluator_can_create_g1_requests[agent]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_only_gate_evaluator_can_create_g1_requests[owner]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_only_gate_evaluator_can_create_g1_requests[system]`：PASSED
- `src/agentloop/tests/test_ac_approvals.py::test_revoked_approval_is_recreated_with_bumped_version`：PASSED

### AC-56

验收目标：后端权限交集拒绝；运维 Capability 生效但无有效人工许可仍拒绝；许可有效后只在指定目标执行

- `src/agentloop/tests/test_phase3_cli.py::test_cli_deploy_is_idempotent_and_agent_remains_live_after_command`：PASSED
- `src/agentloop/tests/test_phase3_governance.py::test_production_capability_still_requires_release_permission_in_isolated_provider_fixture[memory]`：PASSED
- `src/agentloop/tests/test_phase3_governance.py::test_production_capability_still_requires_release_permission_in_isolated_provider_fixture[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_governance.py::test_production_remains_disabled_without_explicit_host_enablement[memory]`：PASSED
- `src/agentloop/tests/test_phase3_governance.py::test_production_remains_disabled_without_explicit_host_enablement[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_governance.py::test_real_authenticated_http_agent_deploy_query_and_health[memory]`：PASSED
- `src/agentloop/tests/test_phase3_governance.py::test_real_authenticated_http_agent_deploy_query_and_health[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_integration.py::test_real_multi_role_delivery_authorized_http_publish_and_periodic_check`：SKIPPED
- `src/agentloop/tests/test_phase3_operations.py::test_independent_executor_requires_capability_and_exact_authorization[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_independent_executor_requires_capability_and_exact_authorization[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[memory-approver]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[memory-artifact]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[memory-expired]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[memory-revoked]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[memory-target]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[sqlite-approver]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[sqlite-artifact]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[sqlite-expired]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[sqlite-revoked]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[sqlite-target]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_revocation_between_prepare_and_dispatch_blocks_send[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_revocation_between_prepare_and_dispatch_blocks_send[sqlite]`：PASSED

### AC-57

验收目标：Run 停在 RELEASE_AUTHORIZATION 的 WAITING_APPROVAL/BLOCKED，不进入 DEPLOYMENT；新申请需绑定当前 Release

- `src/agentloop/tests/test_phase3_governance.py::test_rejected_authorization_stays_blocked_and_new_request_is_reviewable[memory]`：PASSED
- `src/agentloop/tests/test_phase3_governance.py::test_rejected_authorization_stays_blocked_and_new_request_is_reviewable[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_approver_revoked_after_dispatch_does_not_produce_a_g3_pass[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_approver_revoked_after_dispatch_does_not_produce_a_g3_pass[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_first_deploy_failure_without_baseline_verifies_target_and_unblocks[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_first_deploy_failure_without_baseline_verifies_target_and_unblocks[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[memory-approver]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[memory-artifact]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[memory-expired]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[memory-revoked]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[memory-target]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[sqlite-approver]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[sqlite-artifact]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[sqlite-expired]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[sqlite-revoked]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests[sqlite-target]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_reconcile_of_never_dispatched_effect_settles_cancelled_and_frees_target[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_reconcile_of_never_dispatched_effect_settles_cancelled_and_frees_target[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_unsent_rollback_after_expiry_can_receive_new_exact_recovery_permission[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_unsent_rollback_after_expiry_can_receive_new_exact_recovery_permission[sqlite]`：PASSED

### AC-58

验收目标：前一 G3 REJECTED 保留；重验授权，新建 Deployment attempt/G3；只有新 G3 PASSED 才完成

- `src/agentloop/tests/test_phase3_operations.py::test_g3_failure_safe_rollback_then_new_authorized_attempt[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_g3_failure_safe_rollback_then_new_authorized_attempt[sqlite]`：PASSED

### AC-59

验收目标：Router 归属正确，阶段迁移合法，受影响 Gate 失效并补审；终止有授权和副作用处理证据

- `src/agentloop/tests/test_ac_security_remediation.py::test_crash_after_remediation_commit_reuses_evidence_and_enters_leader_once[EXTERNAL_REWORK]`：PASSED
- `src/agentloop/tests/test_ac_security_remediation.py::test_crash_after_remediation_commit_reuses_evidence_and_enters_leader_once[ISSUE_RESOLVED]`：PASSED
- `src/agentloop/tests/test_ac_security_remediation.py::test_g2_verified_code_finding_reenters_leader_and_resolves_only_after_revalidation`：PASSED
- `src/agentloop/tests/test_ac_security_remediation.py::test_issue_cannot_be_resolved_using_failed_or_old_delivery_proof[failed_test]`：PASSED
- `src/agentloop/tests/test_ac_security_remediation.py::test_issue_cannot_be_resolved_using_failed_or_old_delivery_proof[stale_review]`：PASSED
- `src/agentloop/tests/test_ac_security_remediation.py::test_security_demo_profile_survives_reopen_without_repeating_the_flag`：PASSED
- `src/agentloop/tests/test_ac_security_remediation.py::test_unfixed_security_findings_stay_open_and_cannot_loop_forever[False]`：PASSED
- `src/agentloop/tests/test_ac_security_remediation.py::test_unfixed_security_findings_stay_open_and_cannot_loop_forever[True]`：PASSED
- `src/agentloop/tests/test_ac_security_remediation.py::test_unknown_expert_root_cause_stays_unassigned_and_cannot_be_auto_resolved`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_g3_failure_safe_rollback_then_new_authorized_attempt[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_g3_failure_safe_rollback_then_new_authorized_attempt[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_new_p1_during_deployment_rejects_g3_and_recovers_instead_of_hanging[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_new_p1_during_deployment_rejects_g3_and_recovers_instead_of_hanging[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_safe_recovery_routes_upstream_and_invalidates_affected_gates[memory-ARCH_DEFECT-ARCHITECTURE]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_safe_recovery_routes_upstream_and_invalidates_affected_gates[memory-CODE_DEFECT-ENGINEERING]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_safe_recovery_routes_upstream_and_invalidates_affected_gates[memory-SPEC_DEFECT-PRODUCT]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_safe_recovery_routes_upstream_and_invalidates_affected_gates[sqlite-ARCH_DEFECT-ARCHITECTURE]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_safe_recovery_routes_upstream_and_invalidates_affected_gates[sqlite-CODE_DEFECT-ENGINEERING]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_safe_recovery_routes_upstream_and_invalidates_affected_gates[sqlite-SPEC_DEFECT-PRODUCT]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_termination_requires_safe_rollback_evidence[memory]`：PASSED
- `src/agentloop/tests/test_phase3_operations.py::test_termination_requires_safe_rollback_evidence[sqlite]`：PASSED
- `src/agentloop/tests/test_phase3_parallel.py::test_frontend_dynamic_code_is_independently_rejected_then_repaired`：PASSED

## 尚需单独验证的跨项能力

- 真实模型：使用有效凭据验证模型调用、协作质量、实际用量与失败处理；历史报告使用脚本角色。
- 真实项目：接入非固定样例的项目，验证需求、代码、测试和交付全过程。
- 目标环境：生产身份、操作系统隔离、完整安全审查及部署须在目标环境独立验收。
- Phase 5：逐项验证澄清到交付复盘的界面链路、桌面安装及全部人工验收要求。
- 历史运行有 3 项 Java 用例跳过；应启用 Java 环境重新运行，而不是将跳过计作通过。

## 2026-11-06 补充验证

本节为当前补充结果，表格继续保留 2026-10-29 的历史快照，不将历史空关联改写为历史通过。

- AC-26、AC-35：为既有巡检测试补充 MAINTENANCE 子 Run 类型、父 Run 和根 Run，以及 INCIDENT 类型、父子和根 Run 链接断言；测试同时断言父交付状态不变。内存和 SQLite 两种存储均通过。原测试的 AC-17、AC-29 标记与测试内容无关，已更正。
- AC-31：现有授权失效测试补充关联编号，覆盖过期、目标配置变化、产物摘要变化等条件下不发送外部请求；跨环境及使用次数等其余条件仍需逐项核对，不宣称整条完成。
- AC-41：现有豁免测试补充关联编号，覆盖 HIGH/CRITICAL 安全风险拒绝以及 LOW/MEDIUM 审批与撤销；P1 问题及政策限制仍需单独核对，不宣称整条完成。
- 执行命令：`.\.venv\Scripts\python.exe -m pytest src/agentloop/tests/test_phase3_operations.py::test_periodic_maintenance_child_and_incident_leave_parent_unchanged src/agentloop/tests/test_phase3_operations.py::test_invalid_authorizations_never_send_external_requests src/agentloop/tests/test_phase3_governance.py::test_risk_waiver_approval_revoke_and_hard_risks_never_active -q -p no:cacheprovider`。
- 当前结果：20 passed；不代表全量回归或真实生产部署验收。
- 两个相关测试文件的完整回归：test_phase3_operations.py 与 test_phase3_governance.py 共 74 passed（13.83 秒），包含上述 20 项，不重复相加。

## 本轮前端与本机工具链验收

- React/Vite 生产构建通过。HTTP、模型设置、第三阶段运维与治理四个测试文件合计 82 项通过；样例初始化调整后，第三阶段多角色并行用例 6 项通过。覆盖范围与前述历史记录有重叠。
- 使用 Chrome 连接独立本地数据目录，在 1440px 和 390px 宽度验证页面无横向溢出。浏览器验证了空列表创建交付、重复标识保留表单并显示错误、Escape 关闭并返回焦点、搜索无结果及清除筛选、打开子运行与返回父运行、G1 待办入口和审批动作、按发布操作切换参数。子运行导航使用单独写入的验证记录；父运行由浏览器创建，实际门禁达到 G1 PASSED。该项只验证控制台路径，不等于完整 AC-28、AC-54 或端到端发布通过。
- 3 个 Java 专用用例分别通过：使用本机 JDK 27、项目 Java 21 编译目标和独立 Maven 缓存，安全整改样例及多角色 HTTP 发布/周期巡检通过；首次冷缓存运行的普通 Spring 用例超时，暖缓存单独复跑后通过（31.06 秒）。原 JDK 21 无法执行，原 Maven 缓存的父 POM 无法读取；样例初始化现已跳过无法读取的旧 `target` 产物和 Git 元数据。该结果不是原 JDK 21 环境复验，也不修改 59 条 AC 的整体验收状态。
