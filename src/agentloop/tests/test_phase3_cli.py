"""跨命令常驻代理：CLI 返回后服务仍运行，巡检不会重启已断开的代理。"""
import json
import threading
import pytest
from agentloop.examples.demo import build_demo
from agentloop.tests.test_ac_delivery import FakeTestRunner
from agentloop.phase3_cli import main,local_identities
from agentloop.core.contracts.phase3 import DeploymentTarget
from agentloop.deployment_agent import create_agent_server

pytestmark=[pytest.mark.ac("AC-17","AC-54","AC-56"),pytest.mark.requirements("REQ-014","REQ-016","REQ-017","REQ-038","REQ-044")]


def test_cli_deploy_is_idempotent_and_agent_remains_live_after_command(tmp_path,monkeypatch,capsys):
    workflow=build_demo(data_dir=tmp_path,run_id="cli",phase3=True,runner=FakeTestRunner())
    try:
        assert workflow.start("cli","multi role CLI fixture")["phase"]=="RELEASE_AUTHORIZATION"
        local_identities(workflow.rbac,workflow.config.project_id)
        project=workflow.config.project_id
    finally:workflow.close();workflow.store.close()
    monkeypatch.setenv("AGENTLOOP_TEST_AGENT_KEY","local-cli-fixture-token")
    static=DeploymentTarget(target_id="t",project_id=project,environment="staging",provider="local-static")
    server,backend=create_agent_server(static,tmp_path/"agent",token_ref="env:AGENTLOOP_TEST_AGENT_KEY")
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    target=DeploymentTarget(target_id="t",project_id=project,environment="staging",provider="http-agent",endpoint=f"http://127.0.0.1:{server.server_port}",secret_ref="env:AGENTLOOP_TEST_AGENT_KEY")
    config=tmp_path/"target.json";config.write_text(target.model_dump_json(),encoding="utf-8")
    def command(name,*extra):
        capsys.readouterr()
        main([name,"--data-dir",str(tmp_path),"--run-id","cli","--target-id","t",*extra])
        return json.loads(capsys.readouterr().out)
    try:
        command("phase3-target","--target-file",str(config))
        request=command("phase3-request")
        auth=command("phase3-approve","--request-id",request["authorization_request_id"])
        result=command("phase3-deploy","--authorization-id",auth["authorization_id"])
        assert result["status"]=="COMPLETED"
        assert backend.health(auth["artifact_digest"])["healthy"]
        assert command("phase3-deploy","--authorization-id",auth["authorization_id"])["status"]=="COMPLETED"
        assert backend.db.execute("SELECT count(*) FROM operations").fetchone()[0]==1
        command("phase3-schedule","--interval","10")
        server.shutdown();server.server_close();thread.join(timeout=2)
        assert command("phase3-tick")[0]["status"]=="BLOCKED"
        assert command("phase3-status")["run"]["status"]=="COMPLETED"
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2);backend.close()
