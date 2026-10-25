"""确定性 LoopRouter。

规范硬约束（§2.7 / REQ-019）：
- **LoopRouter 必须是确定性代码，不允许 LLM 拥有最终路由权**
- 不得读取 Agent 自报的 target_leader 作为目标
- 输出含 policy_version + routing_reason + evidence_ids
- 分类、归属表和 Gate 规则均存版本，可回放、可单测
- 证据不足、涉及多个部门或策略冲突时，生成 UNASSIGNED 升级，不允许猜测 Leader

本模块不导入任何模型 SDK。
"""

from __future__ import annotations

from ..contracts.enums import (
    ActorType,
    Department,
    EventType,
    IssueCategory,
    IssueStatus,
    LeaderRole,
)
from ..contracts.models import AgentIssueReport, Issue, RoutingDecision, utc_now
from ..orchestration.store import InMemoryStore, atomic

ROUTER_POLICY_VERSION = "router-policy-v1.2"


class OwnershipTable:
    """规范 §2.7 的规范 category → 责任部门 / Leader 映射。"""

    #: category → (department, leader)
    DEFAULTS: dict[IssueCategory, tuple[Department, LeaderRole]] = {
        IssueCategory.SPEC_DEFECT: (Department.PRODUCT, LeaderRole.PRODUCT_LEADER),
        IssueCategory.UX_DEFECT: (Department.PRODUCT, LeaderRole.PRODUCT_LEADER),
        IssueCategory.ARCH_DEFECT: (Department.EXPERT, LeaderRole.EXPERT_LEADER),
        IssueCategory.CODE_DEFECT: (Department.ENGINEERING, LeaderRole.ENGINEERING_LEADER),
        IssueCategory.TEST_DEFECT: (Department.ENGINEERING, LeaderRole.ENGINEERING_LEADER),
        IssueCategory.SECURITY_FINDING: (Department.ENGINEERING, LeaderRole.ENGINEERING_LEADER),
        IssueCategory.DEPLOY_FAILURE: (Department.EXPERT, LeaderRole.EXPERT_LEADER),
        IssueCategory.ENV_DEFECT: (Department.EXPERT, LeaderRole.EXPERT_LEADER),
        IssueCategory.MERGE_CONFLICT: (Department.ENGINEERING, LeaderRole.ENGINEERING_LEADER),
    }

    #: SECURITY_FINDING 按 root_cause 归属，不能固定给研发
    ROOT_CAUSE_TABLE: dict[IssueCategory, tuple[Department, LeaderRole]] = {
        IssueCategory.SPEC_DEFECT: (Department.PRODUCT, LeaderRole.PRODUCT_LEADER),
        IssueCategory.ARCH_DEFECT: (Department.EXPERT, LeaderRole.EXPERT_LEADER),
        IssueCategory.CODE_DEFECT: (Department.ENGINEERING, LeaderRole.ENGINEERING_LEADER),
        IssueCategory.TEST_DEFECT: (Department.ENGINEERING, LeaderRole.ENGINEERING_LEADER),
        IssueCategory.ENV_DEFECT: (Department.EXPERT, LeaderRole.EXPERT_LEADER),
    }

    #: 这些 category 的 root_cause 决定真实责任部门
    ROOT_CAUSE_DRIVEN: frozenset[IssueCategory] = frozenset(
        {
            IssueCategory.SECURITY_FINDING,
            IssueCategory.DEPLOY_FAILURE,
            IssueCategory.ENV_DEFECT,
        }
    )

    def __init__(self, policy_version: str = ROUTER_POLICY_VERSION) -> None:
        self.policy_version = policy_version
        self._overrides: dict[IssueCategory, tuple[Department, LeaderRole]] = {}

    def with_override(
        self, category: IssueCategory, department: Department, leader: LeaderRole
    ) -> "OwnershipTable":
        """模块/项目级归属覆盖。仍属确定性配置，不是运行时猜测。"""
        table = OwnershipTable(self.policy_version)
        table._overrides = {**self._overrides, category: (department, leader)}
        return table

    def lookup(self, issue: Issue) -> tuple[Department | None, LeaderRole | None, str]:
        """确定性查表。返回 (department, leader, reason_code)。"""
        category = issue.category

        if category in self._overrides:
            department, leader = self._overrides[category]
            return department, leader, f"{category.value}_MODULE_OVERRIDE"

        if category is IssueCategory.UNCLASSIFIED:
            return None, None, "UNCLASSIFIED_NO_AUTO_ASSIGN"

        if category not in self.ROOT_CAUSE_DRIVEN and issue.root_cause not in {None, category}:
            return None, None, "CATEGORY_ROOT_CAUSE_CONFLICT"

        # root_cause 驱动的 category
        if category in self.ROOT_CAUSE_DRIVEN:
            if issue.root_cause is None:
                # 证据不足：不猜测，升级人工
                return None, None, f"MISSING_ROOT_CAUSE_FOR_{category.value}"
            mapping = self.ROOT_CAUSE_TABLE.get(issue.root_cause)
            if mapping is None:
                return None, None, f"ROOT_CAUSE_{issue.root_cause.value}_UNMAPPED"
            department, leader = mapping
            return department, leader, f"{category.value}_FROM_{issue.root_cause.value}"

        mapping = self.DEFAULTS.get(category)
        if mapping is None:
            return None, None, f"CATEGORY_{category.value}_UNMAPPED"
        department, leader = mapping
        return department, leader, category.value


class LoopRouter:
    """服务端责任路由器。构造后不接受任何模型输入作为路由依据。"""

    def __init__(
        self, store: InMemoryStore, ownership: OwnershipTable | None = None
    ) -> None:
        self.store = store
        self.ownership = ownership or OwnershipTable()

    # ------------------------------------------------------------------

    @atomic
    def route(self, issue: Issue, source_event_id: str) -> RoutingDecision:
        """按经过验证的 category、归属表和既定策略作最终决定。"""
        department, leader, reason = self.ownership.lookup(issue)

        requires_human = leader is None
        secondary: list[LeaderRole] = []

        if requires_human and reason == "CATEGORY_ROOT_CAUSE_CONFLICT":
            # 多责任工单：不猜测主目标，附带全部候选
            secondary = sorted(
                {self.ownership.DEFAULTS[c][1] for c in (issue.category, issue.root_cause)
                 if c in self.ownership.DEFAULTS},
                key=lambda r: r.value,
            )
            reason = "MULTI_DEPARTMENT_EVIDENCE_CONFLICT"

        decision = RoutingDecision(
            source_event_id=source_event_id,
            issue_id=issue.issue_id,
            target_department=department,
            target_leader=leader,
            reason_code=reason,
            router_policy_version=self.ownership.policy_version,
            evidence_artifact_ids=list(issue.evidence_artifact_ids),
            requires_human=requires_human,
            secondary_targets=secondary,
        )

        routed = issue.model_copy(deep=True)
        routed.routed_department = department
        routed.routed_leader = leader
        routed.router_policy_version = self.ownership.policy_version
        routed.status = IssueStatus.ROUTED if not requires_human else IssueStatus.OPEN
        self.store.put_issue(routed)

        self.store.append_event(
            run_id=issue.run_id,
            event_type=EventType.ISSUE_ROUTED,
            actor_id="loop-router",
            actor_type=ActorType.SYSTEM,
            payload_ref=(
                f"target_leader={leader.value if leader else 'UNASSIGNED'};"
                f"reason={reason};policy={self.ownership.policy_version}"
            ),
            idempotency_key=(f"{issue.run_id}:ISSUE_ROUTED:{issue.issue_id}:{self.ownership.policy_version}:"
                             f"{issue.category.value}:{issue.root_cause.value if issue.root_cause else 'UNKNOWN'}"),
        )
        return decision

    @atomic
    def route_agent_report(self, report: AgentIssueReport, *, authenticated_agent_id: str) -> RoutingDecision:
        """把 Agent 上报转换为 Issue 并路由。

        ``AgentIssueReport`` 用extra="forbid"，因此 Agent 若提交
        ``target_leader``/``routed_leader``/``final_gate_result``
        会在解析阶段直接失败，根本到不了这里（AC-33）。
        """
        if authenticated_agent_id != report.source_agent:
            raise PermissionError("source_agent 必须绑定认证会话")
        run = self.store.get_run(report.run_id)
        for artifact_id in report.issue.evidence_artifact_ids:
            artifact = self.store.get_artifact(artifact_id)
            if artifact.run_id != run.run_id:
                raise PermissionError("不得引用其他 Run 的证据")
        body = report.issue
        issue = Issue(
            issue_id=f"issue-{report.idempotency_key}",
            run_id=report.run_id,
            severity=body.severity,
            category=body.category,
            description=body.description,
            root_cause=body.root_cause,
            evidence_artifact_ids=list(body.evidence_artifact_ids),
        )
        existing_events = [e for e in self.store.events_for(report.run_id)
                           if e.idempotency_key == report.idempotency_key]
        if existing_events:
            if existing_events[0].payload_ref != report.model_dump_json():
                raise ValueError("同一幂等键不可绑定不同的缺陷报告")
            return self.route(self.store.get_issue(issue.issue_id), existing_events[0].event_id)
        self.store.put_issue(issue)

        event = self.store.append_event(
            run_id=report.run_id,
            event_type=EventType.ISSUE_RAISED,
            actor_id=report.source_agent,
            actor_type=ActorType.AGENT,
            payload_ref=report.model_dump_json(),
            idempotency_key=report.idempotency_key,
        )
        return self.route(issue, event.event_id)

    # ------------------------------------------------------------------

    def routing_summary(self, issue_id: str) -> dict:
        issue = self.store.get_issue(issue_id)
        return {
            "issue_id": issue.issue_id,
            "category": issue.category.value,
            "root_cause": issue.root_cause.value if issue.root_cause else None,
            "target_department": (
                issue.routed_department.value if issue.routed_department else None
            ),
            "target_leader": issue.routed_leader.value if issue.routed_leader else None,
            "router_policy_version": issue.router_policy_version,
            "evidence_artifact_ids": issue.evidence_artifact_ids,
            "routed_at": utc_now().isoformat(),
        }
