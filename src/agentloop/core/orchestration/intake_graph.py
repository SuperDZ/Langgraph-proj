"""Phase 0 的真实 LangGraph 澄清子图；不调用模型或外部工具。"""

import sqlite3
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import START, END, StateGraph
from langgraph.types import Command, interrupt

from ..contracts.enums import ClarificationKind, ClarificationStatus


class IntakeState(TypedDict, total=False):
    run_id: str
    question: str
    question_id: str
    answer: str


class IntakeGraph:
    """thread_id 固定等于 run_id。恢复只传已落库并通过身份校验的答复引用。"""

    def __init__(self, path, clarifications):
        self.clarifications = clarifications
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path), check_same_thread=False)
        self.saver = SqliteSaver(self.connection)
        builder = StateGraph(IntakeState)
        builder.add_node("clarify", self._clarify)
        builder.add_edge(START, "clarify")
        builder.add_edge("clarify", END)
        self.graph = builder.compile(checkpointer=self.saver)

    def _clarify(self, state):
        request = self.clarifications.ensure(
            run_id=state["run_id"], question=state["question"],
            kind=ClarificationKind.MISSING_REQUIREMENT,
        )
        # 节点恢复会重放 ensure，因此请求与审计创建均必须幂等。
        response = interrupt({"question_id": request.question_id, "question": request.question})
        answered = self.clarifications.store.get_clarification(request.question_id)
        if response != {"question_id": request.question_id} or answered.status is not ClarificationStatus.ANSWERED:
            raise ValueError("仅允许恢复经过服务端校验的澄清答复")
        return {"question_id": request.question_id, "answer": answered.answer}

    @staticmethod
    def config(run_id):
        return {"configurable": {"thread_id": run_id}}

    def start(self, run_id, question):
        config = self.config(run_id)
        snapshot = self.graph.get_state(config)
        if snapshot.values:
            return dict(snapshot.values)
        return self.graph.invoke({"run_id": run_id, "question": question}, config)

    def resume(self, *, run_id, question_id, principal_id, answer, expected_version):
        request = self.clarifications.store.get_clarification(question_id)
        if request.run_id != run_id:
            raise ValueError("question_id 不属于该 Run")
        config = self.config(run_id)
        snapshot = self.graph.get_state(config)
        if not snapshot.values:
            raise ValueError("缺少原 thread_id 的 checkpoint")
        self.clarifications.answer(question_id=question_id, principal_id=principal_id,
                                   answer=answer, expected_version=expected_version)
        if not snapshot.next:
            return dict(snapshot.values)
        return self.graph.invoke(Command(resume={"question_id": question_id}), config)

    def close(self):
        self.connection.close()
