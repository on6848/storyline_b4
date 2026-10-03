import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_bungo_granularity.py"
BASE = ROOT / "dataset" / "bungo_relationships.json"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_bungo_granularity", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_level(builder, base, names, meta, level, label, data_file):
    generated = json.loads((ROOT / "dataset" / data_file).read_text(encoding="utf-8"))
    source_to_new = {loc["sourceId"]: loc["id"] for loc in generated["locations"]}
    labels = [int(item) for item in base["timeLabels"]]
    time_values = generated.get("timeValues", labels)
    life_windows = {
        character["id"]: (
            character["birthYear"],
            character["deathYear"],
        )
        for character in base["characters"]
    }

    expected_sessions, _time_values, _explicit = builder.merge_sessions(base, level, names, meta)
    expected = {
        (s["start"], s["end"], source_to_new[s["location"]], s.get("groupLocation", s["location"]), tuple(s["members"]))
        for s in expected_sessions
    }
    actual = {
        (s["start"], s["end"], s["location"], s.get("groupLocation", generated["locations"][s["location"]].get("sourceId", s["location"])), tuple(s["members"]))
        for s in generated["sessions"]
    }

    mergeable = []
    for left in generated["sessions"]:
        for right in generated["sessions"]:
            if left["id"] == right["id"]:
                continue
            if (
                left["location"] == right["location"]
                and left.get("groupLocation") == right.get("groupLocation")
                and left["members"] == right["members"]
                and left["end"] == right["start"]
            ):
                mergeable.append((left["id"], right["id"]))

    conflicts = []
    gaps = []
    start = min(s["start"] for s in generated["sessions"])
    end = max(s["end"] for s in generated["sessions"])
    for t in range(start, end):
        by_location = {}
        by_member = {}
        for session in generated["sessions"]:
            if not (session["start"] <= t < session["end"]):
                continue
            loc_source = generated["locations"][session["location"]].get("sourceId", session["location"])
            loc_key = (session["location"], session.get("groupLocation", loc_source))
            by_location.setdefault(loc_key, []).append(session["id"])
            for member in session["members"]:
                by_member.setdefault(member, []).append(session["id"])

        conflicts.extend(("location", t, loc, ids) for loc, ids in by_location.items() if len(ids) > 1)
        conflicts.extend(("member", t, member, ids) for member, ids in by_member.items() if len(ids) > 1)
        year = time_values[t] if t < len(time_values) else time_values[-1]
        for member, (life_start, life_end) in life_windows.items():
            if life_start <= year < life_end and member not in by_member:
                gaps.append((member, t))

    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    ok = not missing and not extra and not mergeable and not conflicts and not gaps
    return {
        "label": label,
        "ok": ok,
        "expected": len(expected),
        "actual": len(actual),
        "missing": missing,
        "extra": extra,
        "mergeable": mergeable,
        "conflicts": conflicts,
        "gaps": gaps,
    }


def main():
    builder = load_builder()
    base = json.loads(BASE.read_text(encoding="utf-8"))
    names = {loc["id"]: loc["name"] for loc in base["locations"]}
    base["locations_by_id"] = {loc["id"]: loc for loc in base["locations"]}
    meta = builder.walk_tree(base["locationTree"])

    failed = False
    for level, label, data_file, _html_file in builder.LEVELS:
        result = validate_level(builder, base, names, meta, level, label, data_file)
        print(
            f"{label}: expected={result['expected']} actual={result['actual']} "
            f"missing={len(result['missing'])} extra={len(result['extra'])} "
            f"mergeable={len(result['mergeable'])} conflicts={len(result['conflicts'])} "
            f"gaps={len(result['gaps'])}"
        )
        if not result["ok"]:
            failed = True
            print("  missing:", result["missing"][:5])
            print("  extra:", result["extra"][:5])
            print("  mergeable:", result["mergeable"][:5])
            print("  conflicts:", result["conflicts"][:5])
            print("  gaps:", result["gaps"][:5])

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
