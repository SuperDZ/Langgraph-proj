"""独立部署代理的 HTTP 入口；认证凭据来自环境，服务仅运行内建静态资源后端。"""
import hmac
import json
import re
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from .core.runtime.configuration import resolve_secret
from .core.runtime.deployment_providers import LocalStaticProvider
from .knowledge.archive import canonical


def create_agent_server(target,root,*,host="127.0.0.1",port=0,token_ref):
    secret=resolve_secret(token_ref)
    provider=LocalStaticProvider(root,target)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def _send(self,status,body):
            raw=canonical(body).encode();self.send_response(status)
            self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(raw)))
            self.end_headers();self.wfile.write(raw)
        def _handle(self):
            if not hmac.compare_digest(self.headers.get("Authorization",""),"Bearer "+secret):
                return self._send(403,{"error":"FORBIDDEN"})
            try:
                length=int(self.headers.get("Content-Length","0"))
                if not 0<=length<=3_000_000: raise ValueError()
                body=json.loads(self.rfile.read(length)) if length else {}
                if self.path=="/operations" and self.command=="POST":
                    if body.get("target_id")!=target.target_id or body.get("project_id")!=target.project_id:
                        return self._send(403,{"error":"TARGET_SCOPE_MISMATCH"})
                    operation=body["operation_id"]
                    if not re.fullmatch(r"[A-Za-z0-9_-]{1,150}",operation): raise ValueError()
                    result=provider.execute(operation,body["action"],bundle=body.get("bundle"),artifact_digest=body["artifact_digest"],previous_digest=body.get("previous_digest"))
                    return self._send(200,result.model_dump(mode="json"))
                if self.path=="/health" and self.command=="POST":
                    return self._send(200,provider.health(body["expected_digest"]))
                match=re.fullmatch(r"/operations/([A-Za-z0-9_-]{1,150})(/cancel)?",self.path)
                if match and ((self.command=="GET" and not match[2]) or (self.command=="POST" and match[2])):
                    result=provider.cancel(match[1]) if match[2] else provider.query(match[1])
                    return self._send(200,result.model_dump(mode="json"))
                return self._send(404,{"error":"NOT_FOUND"})
            except (KeyError,TypeError,ValueError,OSError):
                return self._send(422,{"error":"INVALID_OPERATION_OR_TARGET_STATE"})
        def do_POST(self):self._handle()
        def do_GET(self):self._handle()
    server=ThreadingHTTPServer((host,port),Handler)
    return server,provider
