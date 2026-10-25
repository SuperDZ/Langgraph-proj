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
