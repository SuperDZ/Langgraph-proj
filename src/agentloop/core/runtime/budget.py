"""持久预算预占/结算。未知响应保留预占，根 Run 与逐角色同时记账。"""

from uuid import uuid4
from .configuration import digest


class BudgetBlocked(ValueError):
    pass


class BudgetLedger:
    def __init__(self, repository):
        self.repo, self.store = repository, repository.store

    def root(self, run_id):
        visited = set()
        run = self.store.get_run(run_id)
        while run.parent_run_id:
            if run.run_id in visited:
                raise ValueError("Run 父链存在循环")
            visited.add(run.run_id)
            run = self.store.get_run(run.parent_run_id)
        return run.run_id

    def initialize(self, run_id, tokens, cost):
        root = self.root(run_id)
        if min(tokens, cost) <= 0:
            raise ValueError("预算必须为正数")
        with self.store.transaction():
            existing = self.store.runtime_get("budget", root)
            if existing:
                if existing["initial_tokens"] != tokens or existing["initial_cost"] != cost:
                    raise ValueError("预算初始化不可覆盖原预算")
                return
            if run_id != root:
                raise BudgetBlocked("子 Run 不能创建独立预算")
            self.store.runtime_put("budget", root, {"root": root, "tokens": tokens, "cost": cost,
                "initial_tokens": tokens, "initial_cost": cost, "overrun": False})

    def reserve(self, run_id, role, tokens, cost, config):
        from ..contracts.enums import RunStatus
        if self.store.get_run(run_id).status in {RunStatus.CANCEL_REQUESTED, RunStatus.CANCELLING, RunStatus.CANCELLED, RunStatus.FAILED, RunStatus.NEEDS_RECONCILIATION}:
            raise BudgetBlocked("Run 已停止接收新模型调用")
        if type(tokens) is not int or type(cost) is not int or tokens <= 0 or cost < 0:
            raise ValueError("预占用量必须是正整数 Token 和非负整数金额")
        root = self.root(run_id)
        blocked = None
        with self.store.transaction():
            budget = self.store.runtime_get("budget", root)
            if not budget:
                raise BudgetBlocked("根 Run 预算尚未初始化")
            receipts = [r for r in self.store.runtime_list("usage") if r["root"] == root]
            used_tokens = sum(r["tokens"] for r in receipts)
            used_cost = sum(r["cost"] for r in receipts)
            own = [r for r in receipts if r["role"] == role]
            role_limit = self.store.runtime_get("role_budget", f"{root}/{role}") or {"tokens": config.token_budget, "cost": config.cost_budget}
            if (budget["overrun"] or used_tokens + tokens > budget["tokens"] or used_cost + cost > budget["cost"]
                    or sum(r["tokens"] for r in own) + tokens > role_limit["tokens"]
                    or sum(r["cost"] for r in own) + cost > role_limit["cost"]
                    or len(own) >= config.max_steps
                    or sum(r["status"] == "RESERVED" for r in own) >= config.concurrency):
                request_id = digest({"root": root, "role": role, "tokens": used_tokens, "cost": used_cost,
                                     "limit": budget, "requested": [tokens, cost]})
                self.store.runtime_put("budget_request", request_id, {"id": request_id, "root": root,
                    "role": role, "status": "PENDING", "used_tokens": used_tokens, "used_cost": used_cost})
                self.repo.audit(run_id, "BUDGET_BLOCKED", {"request_id": request_id, "role": role})
                blocked = request_id
            else:
                receipt = {"id": uuid4().hex, "root": root, "run_id": run_id, "role": role,
                    "tokens": tokens, "cost": cost, "reserved_tokens": tokens, "reserved_cost": cost,
                    "status": "RESERVED"}
                self.store.runtime_put("usage", receipt["id"], receipt)
        if blocked:
            raise BudgetBlocked("硬预算/步骤/并发上限阻断，审批请求=" + blocked)
        return receipt["id"]

    def settle(self, receipt_id, *, tokens=None, cost=None, status="SETTLED"):
        with self.store.transaction():
            receipt = self.store.runtime_get("usage", receipt_id)
            if receipt["status"] != "RESERVED":
                return receipt
            if tokens is not None:
                if type(tokens) is not int or type(cost) is not int or min(tokens, cost) < 0:
                    raise ValueError("实际用量不能为负")
                if tokens > receipt["reserved_tokens"] or cost > receipt["reserved_cost"]:
                    budget = self.store.runtime_get("budget", receipt["root"])
                    budget["overrun"] = True
                    self.store.runtime_put("budget", receipt["root"], budget)
                    status = "PROVIDER_USAGE_OVERRUN"
                receipt.update(tokens=tokens, cost=cost)
            receipt["status"] = status
            self.store.runtime_put("usage", receipt_id, receipt)
            self.repo.audit(receipt["run_id"], "MODEL_USAGE", receipt)
            return receipt

    def approve_increase(self, request_id, *, principal_id, rbac, tokens, cost, role_tokens=None, role_cost=None):
        with self.store.transaction():
            request = self.store.runtime_get("budget_request", request_id)
            if not request or request["status"] != "PENDING":
                raise ValueError("预算申请不存在或已处理")
            project = self.store.get_run(request["root"]).project_id
            rbac.require_human(principal_id)
            rbac.require_role(principal_id, "project_owner", project)
            budget = self.store.runtime_get("budget", request["root"])
            if tokens < budget["tokens"] or cost < budget["cost"]:
                raise ValueError("增额不能降低已有预算")
            budget.update(tokens=tokens, cost=cost)
            if role_tokens is not None or role_cost is not None:
                original = self.repo.load_snapshot(request["root"], request["role"])
                existing = self.store.runtime_get("role_budget", f"{request['root']}/{request['role']}") or {"tokens": original.token_budget, "cost": original.cost_budget}
                if role_tokens is None or role_cost is None or role_tokens < existing["tokens"] or role_cost < existing["cost"] or role_tokens > tokens or role_cost > cost:
                    raise ValueError("角色增额必须成对提交，且在已批准根预算内")
                self.store.runtime_put("role_budget", f"{request['root']}/{request['role']}", {"tokens": role_tokens, "cost": role_cost})
            request.update(status="APPROVED", principal_id=principal_id)
            self.store.runtime_put("budget", request["root"], budget)
            self.store.runtime_put("budget_request", request_id, request)
            self.repo.audit(request["root"], "BUDGET_INCREASE_APPROVED", request)

    def summary(self, run_id):
        root = self.root(run_id)
        records = [r for r in self.store.runtime_list("usage") if r["root"] == root]
        return {"limits": self.store.runtime_get("budget", root), "tokens": sum(r["tokens"] for r in records),
                "cost_micro_usd_estimate": sum(r["cost"] for r in records), "calls": records,
                "requests": [r for r in self.store.runtime_list("budget_request") if r["root"] == root]}
