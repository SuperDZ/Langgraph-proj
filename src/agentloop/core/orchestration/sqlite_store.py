"""以 SQLite 表替换内存容器，沿用仓储接口；事务保护状态与追加日志。"""

from __future__ import annotations

import sqlite3
from collections.abc import MutableMapping
from contextlib import contextmanager
from pathlib import Path

from ..contracts import models
from .store import InMemoryStore


class RecordMap(MutableMapping):
    """容器读取返回独立模型，序列化使用 JSON，不执行 pickle。"""

    def __init__(self, connection, kind, model):
        self.connection, self.kind, self.model = connection, kind, model

    def __getitem__(self, key):
        row = self.connection.execute(
            "SELECT data FROM records WHERE kind=? AND id=?", (self.kind, key)
        ).fetchone()
        if row is None:
            raise KeyError(key)
        return self.model.model_validate_json(row[0])

    def __setitem__(self, key, value):
        self.connection.execute(
            "INSERT INTO records(kind,id,data) VALUES(?,?,?) "
            "ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data",
            (self.kind, key, value.model_dump_json()),
        )

    def __delitem__(self, key):
        raise TypeError("持久记录不支持直接删除")

    def __iter__(self):
        return iter([row[0] for row in self.connection.execute(
            "SELECT id FROM records WHERE kind=? ORDER BY position", (self.kind,)
        )])

    def __len__(self):
        return self.connection.execute(
            "SELECT count(*) FROM records WHERE kind=?", (self.kind,)
        ).fetchone()[0]


class SQLiteStore(InMemoryStore):
    """跨连接 BEGIN IMMEDIATE 串行写；嵌套事务使用 SAVEPOINT。"""

    def __init__(self, path):
        super().__init__()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA busy_timeout=10000")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS records (
                position INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL,
                UNIQUE(kind,id)
            );
            CREATE INDEX IF NOT EXISTS records_by_run
                ON records(kind,json_extract(data,'$.run_id'));
            CREATE UNIQUE INDEX IF NOT EXISTS approval_identity ON records(
                json_extract(data,'$.run_id'),json_extract(data,'$.subject_type'),
                json_extract(data,'$.input_digest'),json_extract(data,'$.request_version'))
                WHERE kind='approval_requests';
            CREATE UNIQUE INDEX IF NOT EXISTS tool_identity
                ON records(json_extract(data,'$.idempotency_key')) WHERE kind='tool_executions';
            CREATE UNIQUE INDEX IF NOT EXISTS deployment_attempt
                ON records(json_extract(data,'$.release_id'),json_extract(data,'$.attempt_no'))
                WHERE kind='deployments';
            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                idempotency_key TEXT NOT NULL UNIQUE, data TEXT NOT NULL
            );
            CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
                BEGIN SELECT RAISE(ABORT,'events are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
                BEGIN SELECT RAISE(ABORT,'events are append-only'); END;
        """)
        entities = {
            "runs": models.Run, "gate_results": models.GateResult, "issues": models.Issue,
            "artifacts": models.Artifact, "clarifications": models.ClarificationRequest,
            "approval_requests": models.ApprovalRequest, "risk_waivers": models.RiskWaiver,
            "tool_executions": models.ToolExecution, "releases": models.Release,
            "authorization_requests": models.ReleaseAuthorizationRequest,
            "authorizations": models.ReleaseAuthorization, "deployments": models.Deployment,
            "principals": models.Principal, "bindings": models.RoleBinding,
        }
        for kind, model in entities.items():
            setattr(self, "_" + kind, RecordMap(self.connection, kind, model))
        from ..contracts.phase2 import RuntimeRecord
        self._runtime_records = RecordMap(self.connection, "runtime_records", RuntimeRecord)
        self._depth = 0

    @contextmanager
    def transaction(self):
        with self._lock:
            depth = int(self._depth)  # 内部整数计数器；savepoint 名不含任何外部输入
            begin_sql = "BEGIN IMMEDIATE" if depth == 0 else f"SAVEPOINT tx_{depth}"
            commit_sql = "COMMIT" if depth == 0 else f"RELEASE tx_{depth}"
            rollback_sql = None if depth == 0 else f"ROLLBACK TO tx_{depth}"
            release_sql = None if depth == 0 else f"RELEASE tx_{depth}"
            self.connection.execute(begin_sql)
            self._depth += 1
            try:
                yield
                self.connection.execute(commit_sql)
            except BaseException:
                if depth == 0:
                    self.connection.execute("ROLLBACK")
                else:
                    self.connection.execute(rollback_sql)
                    self.connection.execute(release_sql)
                raise
            finally:
                self._depth -= 1

    def append_event(self, **kwargs):
        with self.transaction():
            row = self.connection.execute(
                "SELECT data FROM events WHERE idempotency_key=?", (kwargs["idempotency_key"],)
            ).fetchone()
            if row:
                event = models.ExecutionEvent.model_validate_json(row[0])
                if (event.run_id, event.type, event.actor_id, event.payload_ref) != (
                    kwargs["run_id"], kwargs["event_type"], kwargs["actor_id"], kwargs["payload_ref"]
                ):
                    raise ValueError("幂等键已绑定另一事件")
                return event
            self._events, self._event_keys = [], set()
            self._sequence = self.connection.execute("SELECT coalesce(max(sequence),0) FROM events").fetchone()[0]
            event = super().append_event(**kwargs)
            self.connection.execute("INSERT INTO events(sequence,idempotency_key,data) VALUES(?,?,?)",
                                    (event.sequence, event.idempotency_key, event.model_dump_json()))
            return event

    def all_events(self):
        with self._lock:
            return [models.ExecutionEvent.model_validate_json(row[0]) for row in
                    self.connection.execute("SELECT data FROM events ORDER BY sequence")]

    def events_for(self, run_id):
        return [e for e in self.all_events() if e.run_id == run_id]

    def count_events_of_type(self, event_type, run_id=None):
        return sum(e.type == event_type and (run_id is None or e.run_id == run_id)
                   for e in self.all_events())

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
