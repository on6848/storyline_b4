import json
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "dataset" / "bungo_relationships.json"

LEVELS = [
    ("country", "国", "bungo_country.json", "storyline_country.html"),
    ("region", "地方", "bungo_region.json", "storyline_region.html"),
    ("prefecture", "都道府県", "bungo_prefecture.json", "storyline_prefecture.html"),
    ("city", "市区町村", "bungo_city.json", "storyline_city.html"),
    ("facility", "施設", "bungo_facility.json", "storyline_facility.html"),
]

COUNTRY_OVERRIDES = {
    "イギリス": "イギリス",
    "ロンドン": "イギリス",
    "フランス": "フランス",
    "リヨン・パリ": "フランス",
    "アメリカ": "アメリカ",
    "サンフランシスコ": "アメリカ",
    "中国": "中国",
    "清国公使館": "中国",
    "北米・欧州": "海外",
    "米欧旅行": "海外",
    "海外": "海外",
    "欧州": "海外",
}

REGION_OVERRIDES = {
    "イギリス": "海外",
    "ロンドン": "海外",
    "フランス": "海外",
    "リヨン・パリ": "海外",
    "アメリカ": "海外",
    "サンフランシスコ": "海外",
    "中国": "海外",
    "清国公使館": "海外",
    "北米・欧州": "海外",
    "米欧旅行": "海外",
    "海外": "海外",
    "欧州": "海外",
}


def walk_tree(node, parent=None, depth=0, meta=None):
    if meta is None:
        meta = {}
    node_id = node.get("id")
    if isinstance(node_id, int):
        meta[node_id] = {"parent": parent, "depth": depth, "children": [c.get("id") for c in node.get("children", [])]}
    for child in node.get("children", []):
        walk_tree(child, node_id if isinstance(node_id, int) else parent, depth + 1, meta)
    return meta


def path_to_root(loc_id, meta):
    path = []
    cur = loc_id
    seen = set()
    while isinstance(cur, int) and cur not in seen:
        seen.add(cur)
        path.append(cur)
        cur = meta.get(cur, {}).get("parent")
    path.reverse()
    return path


def level_location(loc_id, level, names, meta):
    path = path_to_root(loc_id, meta)
    named = [p for p in path if p in names]
    loc_name = names.get(loc_id, "")
    overseas_id = next((item for item in named if names[item] == "海外"), None)

    if level == "facility":
        if overseas_id is not None:
            return overseas_id
        return loc_id
    if level == "city":
        if overseas_id is not None:
            return overseas_id
        return named[3] if len(named) > 3 else named[-1]
    if level == "prefecture":
        if overseas_id is not None:
            return overseas_id
        return named[2] if len(named) > 2 else named[-1]
    if level == "region":
        if overseas_id is not None:
            return overseas_id
        target_name = REGION_OVERRIDES.get(loc_name)
        if target_name:
            return name_to_id(names, target_name)
        return named[1] if len(named) > 1 else named[0]
    if level == "country":
        target_name = COUNTRY_OVERRIDES.get(loc_name)
        if target_name:
            return name_to_id(names, target_name)
        if overseas_id is not None:
            descendants = named[named.index(overseas_id) + 1:]
            if descendants and names[descendants[0]] == "欧州":
                descendants = descendants[1:]
            return descendants[0] if descendants else overseas_id
        return name_to_id(names, "日本")
    raise ValueError(level)


def name_to_id(names, name):
    for loc_id, loc_name in names.items():
        if loc_name == name:
            return loc_id
    raise KeyError(name)


def interval_index_for_year(labels, year):
    if year <= labels[0]:
        return 0
    for idx in range(len(labels) - 1):
        if labels[idx] <= year < labels[idx + 1]:
            return idx
    return len(labels) - 2


def session_start_year(session, labels):
    return session.get("startYear", labels[session["start"]])


def session_end_year(session, labels):
    return session.get("endYear", labels[session["end"]] if session["end"] < len(labels) else labels[-1])


def build_simple_tree(location_ids):
    return {
        "id": "root",
        "name": "所在地",
        "children": [{"id": loc_id, "children": []} for loc_id in location_ids],
    }


def reindex_locations(base, sessions, secondary_sessions=()):
    used = sorted(
        {s["location"] for s in sessions} | {s["location"] for s in secondary_sessions},
        key=lambda loc_id: base["locations_by_id"][loc_id]["name"],
    )
    remap = {old_id: new_id for new_id, old_id in enumerate(used)}
    locations = []
    for old_id in used:
      loc = deepcopy(base["locations_by_id"][old_id])
      loc["sourceId"] = old_id
      loc["id"] = remap[old_id]
      locations.append(loc)

    reindexed_sessions = []
    for idx, session in enumerate(sessions):
        item = deepcopy(session)
        item["id"] = idx
        item["sourceLocation"] = item["location"]
        item["location"] = remap[item["location"]]
        reindexed_sessions.append(item)

    reindexed_secondary = []
    for session in secondary_sessions:
        item = deepcopy(session)
        item["sourceLocation"] = item["location"]
        item["location"] = remap[item["location"]]
        reindexed_secondary.append(item)

    return locations, reindexed_sessions, reindexed_secondary


def explicit_location_by_member_and_time(base, level, names, meta, labels, time_values):
    by_member = {character["id"]: {} for character in base["characters"]}
    for t_idx, year in enumerate(time_values):
        for session in base["sessions"]:
            session_start = session_start_year(session, labels)
            session_end = session_end_year(session, labels)
            if not (session_start <= year < session_end):
                continue
            loc = level_location(session["location"], level, names, meta)
            country_loc = level_location(session["location"], "country", names, meta)
            group = country_loc if level != "country" and names.get(loc) == "海外" else loc
            duration = session_end - session_start
            priority = (duration, -session["id"])
            for member in session["members"]:
                by_member.setdefault(member, {}).setdefault(t_idx, []).append({"loc": loc, "group": group, "priority": priority})
    for member in by_member.values():
        for entries in member.values():
            entries.sort(key=lambda entry: entry["priority"])
    return by_member


def infer_member_location_at_time(t, explicit_by_time):
    if t in explicit_by_time:
        return explicit_by_time[t][0]

    previous_times = [time for time in explicit_by_time if time < t]
    if previous_times:
        return explicit_by_time[max(previous_times)][0]

    next_times = [time for time in explicit_by_time if time > t]
    if next_times:
        return explicit_by_time[min(next_times)][0]

    return None


def secondary_sessions_for_level(base, explicit, time_values):
    """Time ranges where a member is also active in a *second*, lower-priority
    location while their primary session (used for the main line) is elsewhere.
    Only the runner-up is tracked (a third simultaneous location is dropped) to
    keep the extra "ubiquitous actor" branch simple."""
    life_windows = {character["id"]: (character["birthYear"], character["deathYear"]) for character in base["characters"]}
    sessions = []
    for member, times_by_index in explicit.items():
        life_start, life_end = life_windows[member]
        open_loc = None
        open_start_idx = None
        for t_idx, year in enumerate(time_values):
            entries = times_by_index.get(t_idx)
            in_life = life_start <= year < life_end
            current_loc = entries[1]["loc"] if in_life and entries and len(entries) > 1 else None
            if current_loc != open_loc:
                if open_loc is not None:
                    sessions.append({"character": member, "location": open_loc, "startYear": time_values[open_start_idx], "endYear": year})
                open_loc = current_loc
                open_start_idx = t_idx if current_loc is not None else None
        if open_loc is not None:
            sessions.append({"character": member, "location": open_loc, "startYear": time_values[open_start_idx], "endYear": time_values[-1]})
    return sessions


def merge_sessions(base, level, names, meta):
    labels = [int(label) for label in base["timeLabels"]]
    time_values = set(labels)
    for character in base["characters"]:
        time_values.add(character["birthYear"])
        time_values.add(character["deathYear"])
    for session in base["sessions"]:
        time_values.add(session_start_year(session, labels))
        time_values.add(session_end_year(session, labels))
    for evidence in base.get("locationEvidence", []):
        time_values.add(evidence["year"])
    time_values = sorted(time_values)

    start = min(i for i, year in enumerate(time_values) if any(character["birthYear"] <= year < character["deathYear"] for character in base["characters"]))
    end = max(i for i, year in enumerate(time_values) if any(character["birthYear"] <= year < character["deathYear"] for character in base["characters"])) + 1
    explicit = explicit_location_by_member_and_time(base, level, names, meta, labels, time_values)
    life_windows = {
        character["id"]: (
            character["birthYear"],
            character["deathYear"],
        )
        for character in base["characters"]
    }

    frames = []
    for t in range(start, end):
        year = time_values[t]
        by_location = {}
        for character in base["characters"]:
            member = character["id"]
            life_start_year, life_end_year = life_windows[member]
            if not (life_start_year <= year < life_end_year):
                continue
            loc = infer_member_location_at_time(t, explicit.get(member, {}))
            if loc is None:
                continue
            by_location.setdefault((loc["loc"], loc.get("group", loc["loc"])), set()).add(member)

        frames.append({
            loc: tuple(sorted(members))
            for loc, members in by_location.items()
            if members
        })

    open_sessions = {}
    sessions = []

    def close_session(loc, group, members, session_start, session_end):
        if not members or session_start >= session_end:
            return
        item = {
            "id": len(sessions),
            "location": loc,
            "members": list(members),
            "start": session_start,
            "end": session_end,
            "startYear": time_values[session_start],
            "endYear": time_values[session_end] if session_end < len(time_values) else time_values[-1],
        }
        if group != loc:
            item["groupLocation"] = group
        sessions.append(item)

    for offset, frame in enumerate(frames):
        t = start + offset
        next_open = {}
        for loc, members in sorted(frame.items()):
            key = (loc, members)
            if key in open_sessions:
                next_open[key] = open_sessions[key]
            else:
                next_open[key] = t

        for key, session_start in open_sessions.items():
            if key not in next_open:
                loc_key, members = key
                close_session(loc_key[0], loc_key[1], members, session_start, t)

        open_sessions = next_open

    for key, session_start in open_sessions.items():
        loc_key, members = key
        close_session(loc_key[0], loc_key[1], members, session_start, end)

    return sessions, time_values, explicit


def write_html(filename, data_file, title):
    src = (ROOT / "index_region_alpha_demo.html").read_text(encoding="utf-8")
    src = src.replace(
        'var DATASET = { path: "dataset/bungo_relationships.json", name: "日本近現代文学史: 啓蒙期・翻訳文学・政治小説" };',
        f'var DATASET = {{ path: "dataset/{data_file}", name: "日本近現代文学史: {title}" }};',
    )
    src = src.replace("<title>文豪の関係性 Storyline</title>", f"<title>日本近現代文学史: {title}</title>")
    (ROOT / filename).write_text(src, encoding="utf-8")


def main():
    base = json.loads(BASE.read_text(encoding="utf-8"))
    names = {loc["id"]: loc["name"] for loc in base["locations"]}
    base["locations_by_id"] = {loc["id"]: loc for loc in base["locations"]}
    meta = walk_tree(base["locationTree"])

    for level, label, data_file, html_file in LEVELS:
        sessions, time_values, explicit = merge_sessions(base, level, names, meta)
        secondary = secondary_sessions_for_level(base, explicit, time_values)
        locations, sessions, secondary = reindex_locations(base, sessions, secondary)
        used_locations = [loc["id"] for loc in locations]
        out = deepcopy(base)
        out.pop("locations_by_id", None)
        out["title"] = f"日本近現代文学史: {label}粒度"
        out["description"] = base["description"] + f" セッション粒度: {label}。"
        out["granularity"] = label
        out["locations"] = locations
        out["sessions"] = sessions
        out["secondarySessions"] = secondary
        out["timeValues"] = time_values
        out["locationTree"] = build_simple_tree(used_locations)
        (ROOT / "dataset" / data_file).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_html(html_file, data_file, f"{label}粒度")


if __name__ == "__main__":
    main()
