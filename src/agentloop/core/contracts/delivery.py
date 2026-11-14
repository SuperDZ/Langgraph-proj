"""Phase 1 部门交换契约。模型只产出候选内容，不能提供命令或门禁结论。"""

from typing import Literal

from pydantic import Field, StrictBool

from .models import StrictModel


class Criterion(StrictModel):
    criterion_id: str
    description: str


class ProductSpec(StrictModel):
    title: str
    goal: str
    criteria: list[Criterion] = Field(min_length=1)
    out_of_scope: list[str] = Field(default_factory=list)


class Verdict(StrictModel):
    accepted: StrictBool
    input_digest: str
    reasons: list[str] = Field(default_factory=list)


class ArchitectureIssueResolution(StrictModel):
    issue_id: str
    decision: Literal["FIXED", "WITHDRAWN"]
    explanation: str = Field(min_length=1)


class ArchitectureReReview(Verdict):
    resolutions: list[ArchitectureIssueResolution] = Field(default_factory=list)


class ArchitectureDesign(StrictModel):
    spec_digest: str
    summary: str
    editable_paths: list[str] = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)


class FileChange(StrictModel):
    path: str
    expected_sha256: str
    content: str = Field(max_length=200000)


class PatchProposal(StrictModel):
    summary: str
    changes: list[FileChange] = Field(min_length=1, max_length=20)


class EngineeringPlan(StrictModel):
    summary: str
    backend_task: str
    test_criteria_ids: list[str] = Field(min_length=1)


class TestDiagnosis(StrictModel):
    category: Literal["CODE_DEFECT", "TEST_DEFECT", "UNCLASSIFIED"]
    explanation: str


class SecurityFinding(StrictModel):
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
    description: str


class SecurityReport(StrictModel):
    input_digest: str
    findings: list[SecurityFinding] = Field(default_factory=list)
    limitations: list[str] = Field(min_length=1)


class WorkflowConfig(StrictModel):
    """受信应用配置，不来自模型输出；创建 Run 时固定内容摘要。"""
    project_id: str = "phase1-demo"
    changes_ui: StrictBool = False
    production_code_changed: StrictBool = True
    require_confirmation: StrictBool = False
    max_rework_rounds: int = Field(default=3, ge=1, le=10)
    max_department_attempts: int = Field(default=3, ge=1, le=10)
    max_steps: int = Field(default=100, ge=10, le=500)
    role_profiles: dict[str, str]
