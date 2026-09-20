#!/usr/bin/env python3
"""JEPXスポット市場の約定価格（システム＋9エリア、30分×48コマ）を取得し、
ダッシュボード用の data.js と SwiftBar 用の data.json を書き出す。

標準ライブラリのみ。launchd から10分おきに呼ばれる想定だが、
JEPXへのアクセスは「キャッシュが古い」「翌日分が未取得」のときだけに絞っている。

  python3 jepx_fetch.py          # 必要なときだけ取得
  python3 jepx_fetch.py --force  # 強制的に取得
"""
import csv
import datetime as dt
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(os.environ.get("JEPX_WIDGET_DIR",
                           Path.home() / "Library/Application Support/jepx-widget"))
CACHE = Path(os.environ.get("JEPX_CACHE_DIR", BASE / "cache"))
URL = "https://www.jepx.jp/_download.php"
REFERER = "https://www.jepx.jp/electricpower/market-data/spot/"
AREAS = ["北海道", "東北", "東京", "中部", "北陸", "関西", "中国", "四国", "九州"]
SERIES = ["システム"] + AREAS
JST = dt.timezone(dt.timedelta(hours=9))

HISTORY_DAYS = 365             # 分析用に保持する過去の日数
WEATHER_FC_AGE = 3 * 3600      # 気象予報の再取得間隔
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
# エリアごとの気象の代表地点（2地点の平均を使う）
POINTS = {
    "北海道": [(43.06, 141.35), (42.92, 143.20)],   # 札幌, 帯広
    "東北":   [(38.27, 140.87), (37.75, 140.47)],   # 仙台, 福島
    "東京":   [(35.69, 139.69), (36.56, 139.88)],   # 東京, 宇都宮
    "中部":   [(35.18, 136.91), (34.98, 138.38)],   # 名古屋, 静岡
    "北陸":   [(36.56, 136.66), (36.70, 137.21)],   # 金沢, 富山
    "関西":   [(34.69, 135.50), (34.23, 135.17)],   # 大阪, 和歌山
    "中国":   [(34.39, 132.46), (34.66, 133.92)],   # 広島, 岡山
    "四国":   [(34.34, 134.05), (33.84, 132.77)],   # 高松, 松山
    "九州":   [(33.59, 130.40), (31.60, 130.56)],   # 福岡, 鹿児島
}

PUBLISH_AFTER = dt.time(10, 5)  # この時刻以降、翌日分が無ければ取りに行く
MAX_AGE = 12 * 3600             # キャッシュの最大寿命
RETRY_GAP = 20 * 60             # 翌日分待ちのときの再取得間隔


def fiscal_year(d: dt.date) -> int:
    """JEPXのCSVは年度（4月始まり）単位。"""
    return d.year if d.month >= 4 else d.year - 1


def download(fy: int) -> bytes:
    body = urllib.parse.urlencode(
        {"dir": "spot_summary", "file": f"spot_summary_{fy}.csv"}).encode()
    req = urllib.request.Request(
        f"{URL}?timestamp={int(time.time() * 1000)}", data=body, headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": REFERER,
            "User-Agent": "Mozilla/5.0 (Macintosh) jepx-widget/1.0 (personal use)",
        })
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    if raw.lstrip()[:1] == b"<" or len(raw) < 100:
        raise RuntimeError("CSVではない応答が返りました（JEPX側の仕様変更の可能性）")
    return raw


def decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp932"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    raise RuntimeError("CSVの文字コードを判定できません")


def num(s):
    try:
        return round(float(s), 2)
    except (TypeError, ValueError):
        return None


def parse(text: str) -> dict:
    """{ 'YYYY-MM-DD': { 'システム': [48], '北海道': [48], ... } }"""
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return {}
    head = [h.strip() for h in rows[0]]

    def col(*keys):
        for i, h in enumerate(head):
            if all(k in h for k in keys):
                return i
        return None

    i_date, i_code, i_sys = col("受渡日"), col("時刻コード"), col("システムプライス")
    i_area = {a: col("エリアプライス", a) for a in AREAS}
    if None in (i_date, i_code, i_sys) or None in i_area.values():
        # 見出しが想定と違う場合は既知の列位置で読む
        print("警告: 見出しが想定と異なるため列位置で読み込みます", file=sys.stderr)
        i_date, i_code, i_sys = 0, 1, 5
        i_area = {a: 6 + k for k, a in enumerate(AREAS)}

    last = max(i_sys, *i_area.values())
    out = {}
    for r in rows[1:]:
        if len(r) <= last:
            continue
        try:
            d = dt.datetime.strptime(r[i_date].strip().replace("-", "/"), "%Y/%m/%d").date()
            k = int(r[i_code]) - 1
        except ValueError:
            continue
        if not 0 <= k < 48:
            continue
        day = out.setdefault(d.isoformat(), {s: [None] * 48 for s in SERIES})
        day["システム"][k] = num(r[i_sys])
        for a, i in i_area.items():
            day[a][k] = num(r[i])
    return out


# ---------- 取得の記録（いつ取得に成功・挑戦したか） ----------
# ファイルの更新時刻ではなく記録ファイルで管理する。GitHub Actionsのキャッシュから戻したときに
# 更新時刻が変わっても、アクセス頻度の判断が狂わないようにするため。

STATE_FILE = "state.json"
FAIL_GAP = 20 * 60  # 失敗したときに次に挑戦するまでの間隔


def load_state():
    try:
        return json.loads((CACHE / STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state):
    write_atomic(CACHE / STATE_FILE, json.dumps(state, ensure_ascii=False, indent=1))


def record(state, key, path=None):
    """取得記録（なければ既存ファイルの更新時刻で補う＝旧版からの移行用）"""
    rec = state.setdefault(key, {})
    if "ok" not in rec and path is not None and path.exists():
        rec["ok"] = path.stat().st_mtime
    return rec


def may_try(rec, force):
    if not force and time.time() - rec.get("try", 0) < FAIL_GAP:
        return False
    rec["try"] = time.time()
    return True


def load_fy(fy: int, now: dt.datetime, tomorrow: dt.date, force: bool, state: dict):
    """キャッシュを使い、必要なときだけダウンロードする。戻り値: (parsed, error)"""
    path = CACHE / f"spot_summary_{fy}.csv"
    parsed = parse(decode(path.read_bytes())) if path.exists() else {}
    rec = record(state, f"csv_{fy}", path)
    fy_end = dt.date(fy + 1, 3, 31)
    ok_date = dt.datetime.fromtimestamp(rec["ok"], JST).date() if "ok" in rec else None
    if path.exists() and ok_date and ok_date > fy_end + dt.timedelta(days=1):
        return parsed, None  # 年度が終わった後に取得した完全版

    age = time.time() - rec.get("ok", 0)
    stale = not path.exists() or age > MAX_AGE
    waiting = (fiscal_year(tomorrow) == fy and now.time() >= PUBLISH_AFTER
               and tomorrow.isoformat() not in parsed and age > RETRY_GAP)
    if not (force or stale or waiting) or not may_try(rec, force):
        return parsed, None
    try:
        raw = download(fy)
        new = parse(decode(raw))
        if not new:
            raise RuntimeError("CSVから価格を読み取れませんでした")
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(raw)
        tmp.replace(path)
        rec["ok"] = time.time()
        return new, None
    except Exception as e:  # 取得失敗時は手元のキャッシュで表示を続ける
        return parsed, f"{type(e).__name__}: {e}"


def fetch_json(url, params):
    req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}",
                                 headers={"User-Agent": "jepx-widget/1.0 (personal use)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def weather_params(extra):
    pts = [p for a in AREAS for p in POINTS[a]]
    return {"latitude": ",".join(str(p[0]) for p in pts),
            "longitude": ",".join(str(p[1]) for p in pts),
            "hourly": "temperature_2m,shortwave_radiation", "timezone": "Asia/Tokyo", **extra}


def load_weather(today, force, state):
    """Open-Meteo の過去値（再解析）と予報を取得・キャッシュし、
    {エリア: {"YYYY-MM-DDTHH:00": (気温, その1時間の平均日射量)}} を返す。"""
    arc_path, fc_path = CACHE / "weather_archive.json", CACHE / "weather_forecast.json"
    errors = []
    arc = record(state, "weather_archive", arc_path)
    arc_day = dt.datetime.fromtimestamp(arc["ok"], JST).date() if "ok" in arc else None
    if (force or not arc_path.exists() or arc_day != today) and may_try(arc, force):  # 過去値は1日1回
        try:
            d = fetch_json(ARCHIVE_URL, weather_params({
                "start_date": (today - dt.timedelta(days=HISTORY_DAYS + 1)).isoformat(),
                "end_date": (today - dt.timedelta(days=2)).isoformat()}))
            write_atomic(arc_path, json.dumps(d))
            arc["ok"] = time.time()
        except Exception as e:
            errors.append(f"過去の気象: {type(e).__name__}: {e}")
    fc = record(state, "weather_forecast", fc_path)
    fc_old = not fc_path.exists() or time.time() - fc.get("ok", 0) > WEATHER_FC_AGE
    if (force or fc_old) and may_try(fc, force):  # 予報は3時間ごと
        try:
            d = fetch_json(FORECAST_URL, weather_params({"past_days": 7, "forecast_days": 2}))
            write_atomic(fc_path, json.dumps(d))
            fc["ok"] = time.time()
        except Exception as e:
            errors.append(f"気象予報: {type(e).__name__}: {e}")

    def points(path):
        if not path.exists():
            return []
        d = json.loads(path.read_text())
        return d if isinstance(d, list) else [d]

    sources = [points(fc_path), points(arc_path)]  # 後の過去値（再解析）を優先
    out, idx = {}, 0
    for a in AREAS:
        acc = {}
        for _ in POINTS[a]:
            merged = {}
            for src in sources:
                if len(src) <= idx:
                    continue
                h = src[idx]["hourly"]
                T, R = h["temperature_2m"], h["shortwave_radiation"]
                for i, t in enumerate(h["time"]):
                    # 日射量は「直前1時間の平均」なので、次の時刻の値がこの1時間の平均
                    tv, rv = T[i], (R[i + 1] if i + 1 < len(R) else None)
                    old = merged.get(t, (None, None))
                    merged[t] = (tv if tv is not None else old[0], rv if rv is not None else old[1])
            idx += 1
            for t, (tv, rv) in merged.items():
                e = acc.setdefault(t, ([], []))
                if tv is not None:
                    e[0].append(tv)
                if rv is not None:
                    e[1].append(rv)
        out[a] = {t: (round(sum(v[0]) / len(v[0]), 1) if v[0] else None,
                      round(sum(v[1]) / len(v[1])) if v[1] else None) for t, v in acc.items()}
    return out, errors


def avg(xs):
    v = [x for x in xs if x is not None]
    return round(sum(v) / len(v), 2) if v else None


def day_weather(ws, date):
    hours = [ws.get(f"{date}T{h:02d}:00", (None, None)) for h in range(24)]
    return [x[0] for x in hours], [x[1] for x in hours]


def build_history(prices, weather, start, end):
    """分析用の日次データ：日付, 日平均価格, 昼10-14時, 夕方17-21時, 日平均気温, 最高気温, 昼の日射量"""
    rows = {a: [] for a in AREAS}
    d = start
    while d <= end:
        key = d.isoformat()
        if key in prices:
            for a in AREAS:
                temps, rads = day_weather(weather.get(a, {}), key)
                if sum(t is not None for t in temps) < 20:
                    continue
                p = prices[key][a]
                tv = [t for t in temps if t is not None]
                rows[a].append([key, avg(p), avg(p[20:28]), avg(p[34:42]),
                                round(sum(tv) / len(tv), 1), max(tv), avg(rads[10:14])])
        d += dt.timedelta(days=1)
    return {"fields": ["date", "p_all", "p_mid", "p_eve", "t_mean", "t_max", "r_mid"], "rows": rows}


def build_daily(prices, start, end):
    """長期推移用：日付ごとのシステム＋9エリアの日平均価格"""
    rows, d = [], start
    while d <= end:
        key = d.isoformat()
        if key in prices:
            rows.append([key] + [avg(prices[key][s]) for s in SERIES])
        d += dt.timedelta(days=1)
    return {"fields": ["date"] + SERIES, "rows": rows}


def write_archive(prices, weather, start, end):
    """過去分の30分値と時間別気象を月ごとのファイル（archive/YYYY-MM.js）に書き出す。
    画面は表示する月のファイルだけを読み込む。中身が変わった月だけ書き直す。"""
    arch = BASE / "archive"
    arch.mkdir(exist_ok=True)
    months, d = {}, start
    while d <= end:
        key = d.isoformat()
        if key in prices:
            m = months.setdefault(key[:7], {"days": {}, "weather": {a: {} for a in AREAS}})
            m["days"][key] = prices[key]
            for a in AREAS:
                temps, rads = day_weather(weather.get(a, {}), key)
                if any(t is not None for t in temps):
                    m["weather"][a][key] = {"temp": temps, "rad": rads}
        d += dt.timedelta(days=1)
    for mon, obj in months.items():
        body = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        text = f'window.JEPX_ARCHIVE=window.JEPX_ARCHIVE||{{}};window.JEPX_ARCHIVE["{mon}"]={body};\n'
        path = arch / f"{mon}.js"
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            write_atomic(path, text)
    for p in arch.glob("*.js"):  # 保持期間を過ぎた月は消す
        if p.stem not in months:
            p.unlink()
    return sorted(months)


def write_atomic(path: Path, text: str):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def main():
    force = "--force" in sys.argv
    CACHE.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(JST)
    today = now.date()
    tomorrow = today + dt.timedelta(days=1)

    start = today - dt.timedelta(days=HISTORY_DAYS)
    state = load_state()
    days, errors, prices = {}, [], {}
    for fy in range(fiscal_year(start), fiscal_year(tomorrow) + 1):
        parsed, err = load_fy(fy, now, tomorrow, force, state)
        if err:
            errors.append(err)
        prices.update(parsed)
    for d in (today, tomorrow):
        if d.isoformat() in prices:
            days[d.isoformat()] = prices[d.isoformat()]

    weather, w_errors = load_weather(today, force, state)
    save_state(state)
    wx = {a: {} for a in AREAS}
    for a in AREAS:
        for d in (today, tomorrow):
            temps, rads = day_weather(weather.get(a, {}), d.isoformat())
            if any(t is not None for t in temps):
                wx[a][d.isoformat()] = {"temp": temps, "rad": rads}

    fetched = [v["ok"] for k, v in state.items() if k.startswith("csv_") and "ok" in v]
    payload = {
        "generated": now.isoformat(timespec="seconds"),
        "fetched": (dt.datetime.fromtimestamp(max(fetched), JST).isoformat(timespec="seconds")
                    if fetched else None),
        "error": " / ".join(errors) or None,
        "series": SERIES,
        "days": days,
        "weather": wx,
        "weather_error": " / ".join(w_errors) or None,
        "history": build_history(prices, weather, start, tomorrow),
        "daily": build_daily(prices, start, tomorrow),
        "archive_months": write_archive(prices, weather, start, today - dt.timedelta(days=1)),
    }
    js = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    write_atomic(BASE / "data.json", js)
    write_atomic(BASE / "data.js", f"window.JEPX={js};\n")
    status = "取得エラー: " + payload["error"] if errors else "OK"
    if w_errors:
        status += " / " + " / ".join(w_errors)
    n_hist = len(payload["history"]["rows"]["東京"])
    print(f"{now:%Y-%m-%d %H:%M} {status} 日付: {', '.join(days) or 'なし'} 分析用履歴: {n_hist}日")


if __name__ == "__main__":
    main()
