"""frontend/server.py 工作台门面的契约测试。

锁定启动参数（G1 人工确认 / 安全整改示例）真实传递到工作流装配，
以及查询接口不得为不存在的 Run 触发装配副作用。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "frontend"))

import server  # noqa: E402


def wait_idle(bench, timeout=10.0):
    deadline = time.time() + timeout
    while bench.job["busy"]:
        if time.time() > deadline:
            raise AssertionError("工作台作业超时未完成：" + str(bench.job))
        time.sleep(0.02)
    if bench.job["error"]:
        raise AssertionError("工作台作业失败：" + bench.job["error"])


@pytest.fixture
def bench(tmp_path, monkeypatch):
    workbench = server.Workbench(tmp_path)
    yield workbench, monkeypatch
    if workbench._store is not None:
        workbench._store.close()


def fake_workflow(**attrs):
    config = SimpleNamespace(require_confirmation=False,
                             role_profiles={"backend": "scripted-demo"})
    wf = SimpleNamespace(config=config, started=[], authorized=[], **attrs)
    wf.start = lambda run_id, task: wf.started.append((run_id, task))
    return wf


def test_state_for_unknown_run_does_not_assemble_workflow(bench):
    workbench, monkeypatch = bench

    def boom(*args, **kwargs):
        raise AssertionError("查询接口不得为不存在的 Run 装配工作流")

    monkeypatch.setattr(server, "build_demo", boom)
    assert workbench.state("never-started")["exists"] is False
    assert workbench.workflows == {}


def test_start_passes_launch_flags_to_workflow_assembly(bench):
    workbench, monkeypatch = bench
    captured = {}
    wf = fake_workflow()

    def fake_build_demo(**kwargs):
        captured.update(kwargs)
        return wf

    monkeypatch.setattr(server, "build_demo", fake_build_demo)
    workbench.start("wb-1", "任务", require_confirmation=True, security_example=True)
    wait_idle(workbench)
    assert captured["require_confirmation"] is True
    assert captured["security_example"] is True
    assert wf.started == [("wb-1", "任务")]


def test_start_rejects_conflicting_flags_on_same_unstarted_run(bench):
    workbench, monkeypatch = bench
    wf = fake_workflow()

    def fake_build_demo(**kwargs):
        # 与真实 build_demo 一致：启动参数写入 config，供后续一致性守卫比较
        wf.config.require_confirmation = bool(kwargs.get("require_confirmation"))
        if kwargs.get("security_example"):
            wf.config.role_profiles["backend"] = "scripted-security-demo"
        return wf

    monkeypatch.setattr(server, "build_demo", fake_build_demo)
    workbench.start("wb-2", "任务", require_confirmation=True)
    wait_idle(workbench)
    workbench.start("wb-2", "任务", require_confirmation=False)
    with pytest.raises(Exception):
        wait_idle(workbench)


def test_authorize_forwards_reject_decision(bench):
    workbench, monkeypatch = bench
    wf = fake_workflow()
    wf.authorize_simulation = lambda run_id, principal, decision=None: wf.authorized.append(decision)
    monkeypatch.setattr(server, "build_demo", lambda **kwargs: wf)
    workbench.authorize("wb-3", "REJECT")
    wait_idle(workbench)
    assert wf.authorized == ["REJECT"]
