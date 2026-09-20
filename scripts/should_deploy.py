#!/usr/bin/env python3
"""データに変化があったときだけGitHub Pagesへ公開する（変化がなくても2時間に1回は公開）。
GitHub Actions の出力形式（deploy=true/false）で標準出力に書く。"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

site = Path(os.environ["JEPX_WIDGET_DIR"])
cache = Path(os.environ["JEPX_CACHE_DIR"])
event = sys.argv[sys.argv.index("--event") + 1] if "--event" in sys.argv else ""

data = json.loads((site / "data.json").read_text(encoding="utf-8"))
data.pop("generated", None)  # 生成時刻だけの違いは変化とみなさない
digest = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

state_path = cache / "last_deploy.json"
state = json.loads(state_path.read_text()) if state_path.exists() else {}
changed = digest != state.get("hash")
due = time.time() - state.get("time", 0) > 2 * 3600
manual = event in ("push", "workflow_dispatch")

deploy = manual or changed or due
if deploy:
    state_path.write_text(json.dumps({"hash": digest, "time": time.time()}))
reason = "手動/プッシュ" if manual else "データ変化" if changed else "定期" if due else "変化なし"
print(f"判定: {reason}", file=sys.stderr)
print(f"deploy={'true' if deploy else 'false'}")
