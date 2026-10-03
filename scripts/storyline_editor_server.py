"""Local Storyline data editor and preview server."""

import json
import math
import re
import shutil
import subprocess
import sys
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError

from article_import import import_article
from build_bungo_granularity import BASE, ROOT, main as rebuild


SAVE_LOCK = threading.Lock()


def validate(data):
    errors = []
    if not isinstance(data, dict):
        return ["データはJSONオブジェクトにしてください。"]
    people = data.get("characters", [])
    places = data.get("locations", [])
    sessions = data.get("sessions", [])
    events = data.get("events", [])
    evidence_items = data.get("locationEvidence", [])
    labels = data.get("timeLabels", [])
    if not all(isinstance(x, list) for x in (people, places, sessions, events, evidence_items, labels)):
        return ["配列の形式が正しくありません。"]

    def ids(items, label):
        found = set()
        for item in items:
            value = item.get("id") if isinstance(item, dict) else None
            if not isinstance(value, int) or value < 0 or value in found:
                errors.append(f"{label}のIDが重複または不正です: {value}")
            found.add(value)
        return found

    person_ids = ids(people, "人物")
    place_ids = ids(places, "場所")
    ids(sessions, "セッション")
    if not people or not places or not sessions:
        errors.append("人物・場所・セッションをそれぞれ1件以上登録してください。")
    names = [p.get("name", "").strip() for p in places]
    if len(set(names)) != len(names) or any(not n for n in names):
        errors.append("場所名は重複せず、空欄にしないでください。")
    if "日本" not in names or "海外" not in names:
        errors.append("場所ツリーには日本と海外が必要です。")
    try:
        years = [float(x) for x in labels]
        if len(years) < 2 or years != sorted(set(years)):
            errors.append("時間目盛りは昇順で2つ以上必要です。")
    except (TypeError, ValueError):
        errors.append("時間目盛りが不正です。")
        years = []
    for person in people:
        birth = person.get("birthYear")
        death = person.get("deathYear")
        if not person.get("name", "").strip() or not isinstance(birth, (int, float)) or not isinstance(death, (int, float)) or not math.isfinite(birth) or not math.isfinite(death) or birth >= death:
            errors.append("人物の名前または生没年が不正です。")
        if not any(person.get("id") in session.get("members", []) for session in sessions):
            errors.append(f"{person.get('name', '人物')}: 所在地セッションを1件以上設定してください。")
        color = person.get("color")
        if color is not None and not re.fullmatch(r"#[0-9a-fA-F]{6}", color or ""):
            errors.append(f"{person.get('name', '人物')}: 線の色は#rrggbb形式で指定してください。")
    tree_seen = set()

    def walk(node):
        if not isinstance(node, dict):
            errors.append("場所ツリーのノードが不正です。")
            return
        value = node.get("id")
        if value != "root":
            if value in tree_seen or value not in place_ids:
                errors.append(f"場所ツリーのIDが重複または未登録です: {value}")
            tree_seen.add(value)
        for child in node.get("children", []):
            walk(child)

    walk(data.get("locationTree", {}))
    if tree_seen != place_ids:
        errors.append("すべての場所をツリーに1回ずつ配置してください。")
    root_children = {next((place.get("name") for place in places if place.get("id") == child.get("id")), None) for child in data.get("locationTree", {}).get("children", []) if isinstance(child, dict)}
    if not {"日本", "海外"}.issubset(root_children):
        errors.append("日本と海外は所在地ツリーの直下に配置してください。")
    for session in sessions:
        sid = session.get("id")
        if session.get("location") not in place_ids:
            errors.append(f"セッション {sid}: 場所が存在しません。")
        members = session.get("members", [])
        if not members or len(members) != len(set(members)) or set(members) - person_ids:
            errors.append(f"セッション {sid}: メンバーが不正です。")
        start = session.get("startYear", years[session["start"]] if years and isinstance(session.get("start"), int) and 0 <= session["start"] < len(years) else None)
        end = session.get("endYear", years[session["end"]] if years and isinstance(session.get("end"), int) and 0 <= session["end"] < len(years) else None)
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or not math.isfinite(start) or not math.isfinite(end) or start >= end:
            errors.append(f"セッション {sid}: 開始・終了時刻が不正です。")
        if not isinstance(session.get("start"), int) or not isinstance(session.get("end"), int) or not years or not (0 <= session["start"] < session["end"] < len(years)):
            errors.append(f"セッション {sid}: 時間目盛りへの対応が不正です。")
    for event in events:
        year = event.get("year")
        if event.get("character") not in person_ids or not event.get("title", "").strip() or not isinstance(year, (int, float)) or not math.isfinite(year):
            errors.append("作品の人物、年またはタイトルが不正です。")
    for evidence in evidence_items:
        if not isinstance(evidence, dict) or evidence.get("character") not in person_ids or evidence.get("location") not in place_ids or not isinstance(evidence.get("year"), (int, float)) or not math.isfinite(evidence["year"]) or not isinstance(evidence.get("source"), str):
            errors.append("所在地の出典データが不正です。")
    return errors


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def json_response(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/data":
            self.json_response(200, json.loads(BASE.read_text(encoding="utf-8")))
            return
        super().do_GET()

    def end_headers(self):
        if self.path.startswith("/dataset/") or self.path.startswith("/storyline_"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_POST(self):
        if self.path not in {"/api/data", "/api/article"}:
            self.json_response(404, {"error": "Not found"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 5_000_000:
                raise ValueError("データサイズが不正です。")
            data = json.loads(self.rfile.read(size))
            if self.path == "/api/article":
                person = data.get("person", {})
                locations = data.get("locations", [])
                if not isinstance(person, dict) or not isinstance(locations, list) or not isinstance(data.get("url"), str):
                    raise ValueError("人物・場所・URLを指定してください。")
                self.json_response(200, import_article(data["url"], person, locations))
                return
            errors = validate(data)
            if errors:
                self.json_response(400, {"errors": errors})
                return
            with SAVE_LOCK:
                original = BASE.read_bytes()
                if data != json.loads(original):
                    BASE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                try:
                    rebuild()
                except Exception:
                    BASE.write_bytes(original)
                    rebuild()
                    raise
            self.json_response(200, {"ok": True})
        except (ValueError, json.JSONDecodeError) as error:
            self.json_response(400, {"errors": [str(error)]})
        except (HTTPError, URLError, TimeoutError) as error:
            self.json_response(502, {"errors": [f"記事を取得できませんでした: {error}"]})
        except Exception as error:
            self.json_response(500, {"errors": [f"再生成に失敗しました: {error}"]})


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--no-browser"]  # editor.batはWindows側で開く
    port = int(args[0]) if args else 8001
    url = f"http://127.0.0.1:{port}/editor.html"
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        server = None  # 起動済みならそのサーバーを開くだけ
    print(f"Storyline editor: {url}", flush=True)
    if "--no-browser" in sys.argv:
        pass
    # WSLではWindows側の既定ブラウザで開く
    elif shutil.which("explorer.exe"):
        subprocess.run(["explorer.exe", url])
    else:
        webbrowser.open(url)
    if server:
        server.serve_forever()
