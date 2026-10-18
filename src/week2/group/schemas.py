"""延续 week1 的输出字段，增加本地类型与范围校验。"""

from pydantic import BaseModel, ConfigDict, Field


class LogAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_type: str
    root_cause: str
    possible_causes: list[str] = Field(max_length=3)
    confidence: float = Field(ge=0, le=1)
    suggestions: list[str] = Field(max_length=3)


class TaskAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_member: str
    task_description: str


class AssignmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_assignments: list[TaskAssignment]
