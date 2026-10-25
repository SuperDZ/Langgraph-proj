"""内容寻址的本地产物。原文与元数据共同验证，禁止静默覆盖。"""

import hashlib
import json
import os
from pathlib import Path

from ..core.contracts.enums import TrustLevel
from ..core.contracts.models import Artifact


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class ArtifactArchive:
    def __init__(self, root, store):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.store = store

    def put(self, *, run_id, kind, producer, value, trust=TrustLevel.MODEL_GENERATED):
        raw = canonical(value).encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        artifact_id = hashlib.sha256(f"{run_id}:{kind}:{producer}:{digest}".encode()).hexdigest()
        try:
            artifact = self.store.get_artifact(artifact_id)
        except KeyError:
            artifact = None
        path = self.root / digest[:2] / f"{digest}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            # 排他创建；写入中断留下的损坏文件会在校验时被拒绝。
            try:
                with path.open("xb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError:
                pass
        if path.read_bytes() != raw:
            raise ValueError("Artifact blob 内容已损坏")
        if artifact is None:
            artifact = Artifact(artifact_id=artifact_id, run_id=run_id, type=kind, version=digest,
                sha256=digest, uri=str(path), producer_task_id=producer, trust_level=trust)
            self.store.put_artifact(artifact)
        return artifact

    def read(self, artifact_id, *, run_id):
        artifact = self.store.get_artifact(artifact_id)
        path = Path(artifact.uri).resolve()
        if artifact.run_id != run_id or not path.is_relative_to(self.root):
            raise PermissionError("Artifact 超出当前 Run/归档范围")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != artifact.sha256:
            raise ValueError("Artifact 哈希校验失败")
        return json.loads(raw)
