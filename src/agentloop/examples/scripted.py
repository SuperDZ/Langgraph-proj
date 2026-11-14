"""可复现演示适配器，不是模型推理。第一轮故意遗漏空串边界。"""


class ScriptedDemoAdapter:
    def invoke(self, role, context, schema):
        if role == "product-analyst":
            return {"title": "修复 hello 参数校验", "goal": context["task"], "criteria": [
                {"criterion_id": name, "description": text} for name, text in (
                    ("missing", "缺失参数返回400"), ("empty", "空串返回400"),
                    ("blank", "空白返回400"), ("valid", "合法参数保留问候语"))]}
        if role == "architecture-expert":
            return {"spec_digest": context["spec_digest"], "summary": "在 Controller 校验参数，固定 HTTP 回归验证",
                    "editable_paths": context["editable_paths"], "risks": ["不得改变合法参数行为或削弱测试"]}
        if role == "engineering-leader" and context.get("mode") == "ENTRY":
            return {"summary": "后端实现并执行固定验收测试", "backend_task": "按安全整改工单移除进程执行入口并重测" if context.get("remediation") else "补齐参数校验",
                    "test_criteria_ids": [c["criterion_id"] for c in context["spec"]["criteria"]]}
        if role == "backend":
            changes = []
            for path, source in context["sources"].items():
                stripped = "\n".join(line for line in source.splitlines() if "ResponseEntity.badRequest()" not in line) + "\n"
                condition = "name == null" if context["attempt"] == 1 else "name == null || name.isBlank()"
                guard = f'        if ({condition}) return ResponseEntity.badRequest().body("name required");\n'
                content = stripped.replace('        return ResponseEntity.ok("Hello, " + name.trim());', guard + '        return ResponseEntity.ok("Hello, " + name.trim());')
                changes.append({"path": path, "expected_sha256": context["hashes"][path], "content": content})
            return {"summary": "演示候选补丁", "changes": changes}
        if role == "testing":
            return {"category": "CODE_DEFECT", "explanation": "固定 HTTP 测试仍有失败，退回 Backend 修复边界"}
        if role == "security-expert":
            return {"input_digest": context["input_digest"], "findings": [],
                    "limitations": ["脚本专家；仅结合演示范围的进程执行模式扫描，非完整安全审计"]}
        return {"accepted": True, "input_digest": context["input_digest"], "reasons": []}


class ScriptedSecurityRepairAdapter(ScriptedDemoAdapter):
    """演示扫描阻断与代码整改。未调用该方法，也不执行任何外部命令。"""

    unsafe_method = ('\n    private Process unsafeCommand(String command) throws java.io.IOException {\n'
                     '        return Runtime.getRuntime().exec(command);\n    }\n')

    def invoke(self, role, context, schema):
        output = super().invoke(role, context, schema)
        if role == "backend":
            for change in output["changes"]:
                content = change["content"]
                if context.get("remediation"):
                    content = content.replace(self.unsafe_method, "")
                elif self.unsafe_method not in content:
                    prefix, suffix = content.rsplit("}", 1)
                    content = prefix + self.unsafe_method + "}" + suffix
                change["content"] = content
        return output


class ScriptedCurator:
    """明确标注的脚本复盘分析器：不是模型推理。

    只对冻结证据做确定性统计，报告与候选提案全部回溯到证据快照中的真实
    Artifact；不产生任何自动生效的记忆或配置变更。
    """

    def analyze(self, evidence):
        artifacts = {a["type"]: a["artifact_id"] for a in reversed(evidence["artifacts"])}
        fallback = evidence["artifacts"][0]["artifact_id"]
        spec = artifacts.get("SPEC", fallback)
        architecture = artifacts.get("ARCHITECTURE", fallback)
        test = artifacts.get("TEST_EXECUTION", fallback)
        histogram = evidence["events"]["type_histogram"]
        local_reworks = histogram.get("LOCAL_REWORK", 0)
        external_reworks = histogram.get("EXTERNAL_REWORK", 0)
        test_rounds = sum(1 for a in evidence["artifacts"] if a["type"] == "TEST_EXECUTION")
        severity_counts: dict[str, int] = {}
        for issue in evidence["issues"]:
            severity_counts[issue["severity"]] = severity_counts.get(issue["severity"], 0) + 1
        return {
            "run_id": evidence["run"]["run_id"],
            "delivered_version": evidence["run"]["baseline_versions"].get("commit") or "uncommitted",
            "final_phase": evidence["run"]["phase"],
            "final_status": evidence["run"]["status"],
            "summary": ("脚本复盘：基于冻结证据的确定性统计；"
                        f"{evidence['artifact_count']} 个产物、{evidence['events']['count']} 个事件、"
                        f"{local_reworks} 次局部返工、{external_reworks} 次外部整改"),
            "timeline": [
                {"stage": "PRODUCT", "note": "Spec 形成并绑定基线", "source_artifact_ids": [spec]},
                {"stage": "ARCHITECTURE", "note": "架构设计经专家验收", "source_artifact_ids": [architecture]},
                {"stage": "ENGINEERING", "note": f"研发-测试 Loop 共 {test_rounds} 轮测试证据",
                 "source_artifact_ids": [test]},
            ],
            "stage_evidence": [
                {"stage": "PRODUCT", "artifact_ids": [spec]},
                {"stage": "ARCHITECTURE", "artifact_ids": [architecture]},
                {"stage": "ENGINEERING", "artifact_ids": [test]},
            ],
            "defect_stats": [
                {"severity": severity, "count": count, "responsibility": "engineering",
                 "source_artifact_ids": [test]}
                for severity, count in sorted(severity_counts.items())
            ],
            "improvements": ([
                {"issue": "首轮实现遗漏空串/空白边界", "root_cause": "需求边界条件进入实现前未逐条核对",
                 "action": "Backend 在编码前逐条复述验收条件", "verification": "下一任务的固定回归测试",
                 "estimated_benefit": "预计减少一轮返工（估计值，待验证）", "source_artifact_ids": [test]},
            ] if local_reworks else []),
            "keep_practices": [
                {"practice": "Spec 与架构摘要先行绑定基线，G1 复核输入版本",
                 "applicability": "所有交付 Run", "evidence_artifact_ids": [spec, architecture]},
            ],
            "runtime_suggestions": [
                {"kind": "SKILL", "target": "spring-validation-checklist",
                 "summary": "把空串/空白边界检查加入 Spring 参数校验 Skill 的检查单",
                 "verification_plan": "在下一个演示 Run 上对比返工轮次", "source_artifact_ids": [test]},
            ],
            "memory_candidates": [
                {"scope_type": "AGENT", "scope_id": "backend",
                 "title": "参数校验需覆盖缺失/空串/空白三类输入",
                 "content": "实现 HTTP 参数校验时，缺失、空串与空白参数应一并返回 400，并在编码前逐条核对验收条件。",
                 "confidence": 0.7, "maturity": "OBSERVED", "source_artifact_ids": [test]},
                {"scope_type": "SHARED", "scope_id": "",
                 "title": "上游产物变更后受影响门禁必须重新评估",
                 "content": "Spec 或架构摘要变更会使依赖测试与评审失效；重跑受影响门禁后再进入下游阶段。",
                 "confidence": 0.8, "maturity": "OBSERVED", "source_artifact_ids": [spec, architecture]},
            ],
            "regression_checklist": [
                "缺失/空串/空白参数均返回 400",
                "合法参数行为保持不变",
                "受影响门禁在新基线下重新评估",
            ],
            "open_risks": ["脚本复盘不含成本与 Token 统计（预算接入后补齐）"],
        }
