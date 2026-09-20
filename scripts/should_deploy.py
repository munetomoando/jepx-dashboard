#!/usr/bin/env python3
"""GitHub Pagesへの公開が必要かを判定する。GitHub Actions の出力形式（deploy=true/false）で標準出力に書く。

比べる相手は「実際に公開されているdata.json」。前回の公開が失敗していても、次の実行で必ずやり直される。
  - 手動実行・プッシュ時 → 公開
  - 公開中のデータと中身（生成時刻を除く）が違う → 公開
  - 公開中のデータが2時間以上前に生成されたもの → 公開（「更新が止まっています」の誤表示を防ぐ）
  - 公開中のデータを読めない → 公開
"""
import datetime as dt
import hashlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

REFRESH = 2 * 3600


def digest(data):
    data = dict(data)
    data.pop("generated", None)
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def live_url():
    if os.environ.get("PAGES_URL"):
        base = os.environ["PAGES_URL"]
    else:
        owner, repo = os.environ["GITHUB_REPOSITORY"].split("/")
        base = f"https://{owner.lower()}.github.io/{repo}/"
    return base.rstrip("/") + f"/data.json?t={int(time.time())}"


def main():
    event = sys.argv[sys.argv.index("--event") + 1] if "--event" in sys.argv else ""
    site = Path(os.environ["JEPX_WIDGET_DIR"])
    new = json.loads((site / "data.json").read_text(encoding="utf-8"))

    if event in ("push", "workflow_dispatch"):
        deploy, reason = True, "手動実行・プッシュ"
    else:
        try:
            with urllib.request.urlopen(live_url(), timeout=20) as r:
                live = json.loads(r.read())
            age = time.time() - dt.datetime.fromisoformat(live["generated"]).timestamp()
            if digest(live) != digest(new):
                deploy, reason = True, "データに変化あり"
            elif age > REFRESH:
                deploy, reason = True, f"公開中のデータが{age / 3600:.1f}時間前のもの"
            else:
                deploy, reason = False, "変化なし"
        except Exception as e:
            deploy, reason = True, f"公開中のデータを読めない（{type(e).__name__}）"
    print(f"判定: {reason}", file=sys.stderr)
    print(f"deploy={'true' if deploy else 'false'}")


if __name__ == "__main__":
    main()
