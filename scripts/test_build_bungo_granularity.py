import build_bungo_granularity as builder


def make_base():
    return {
        "timeLabels": ["1900", "1910"],
        "characters": [{"id": 0, "name": "テスト太郎", "birthYear": 1900, "deathYear": 1910}],
        "locations": [
            {"id": 0, "name": "日本"},
            {"id": 1, "name": "海外"},
            {"id": 2, "name": "自宅"},
            {"id": 3, "name": "大学"},
        ],
        "locationTree": {
            "id": "root",
            "children": [
                {"id": 0, "children": [{"id": 2, "children": []}, {"id": 3, "children": []}]},
                {"id": 1, "children": []},
            ],
        },
        "sessions": [
            {"id": 0, "location": 2, "members": [0], "start": 0, "end": 1, "startYear": 1900, "endYear": 1910},
            {"id": 1, "location": 3, "members": [0], "start": 0, "end": 1, "startYear": 1903, "endYear": 1905},
        ],
    }


base = make_base()
names = {loc["id"]: loc["name"] for loc in base["locations"]}
base["locations_by_id"] = {loc["id"]: loc for loc in base["locations"]}
meta = builder.walk_tree(base["locationTree"])

sessions, time_values, explicit = builder.merge_sessions(base, "facility", names, meta)
secondary = builder.secondary_sessions_for_level(base, explicit, time_values)

# The shorter, more specific "大学" session outranks the decade-long "自宅" one
# while it is active, so the primary line should show 3 segments...
primary_by_year = sorted((time_values[s["start"]], time_values[s["end"]], s["location"]) for s in sessions)
assert primary_by_year == [(1900, 1903, 2), (1903, 1905, 3), (1905, 1910, 2)], primary_by_year

# ...and the displaced "自宅" stretch should surface as a secondary (ubiquitous-actor) branch.
assert len(secondary) == 1, secondary
assert secondary[0]["character"] == 0
assert secondary[0]["location"] == 2
assert secondary[0]["startYear"] == 1903 and secondary[0]["endYear"] == 1905

# Reindexing must remap both the primary and secondary location ids consistently.
locations, reindexed_sessions, reindexed_secondary = builder.reindex_locations(base, sessions, secondary)
used_ids = {loc["sourceId"] for loc in locations}
assert used_ids == {2, 3}
home_new_id = next(loc["id"] for loc in locations if loc["sourceId"] == 2)
assert reindexed_secondary[0]["location"] == home_new_id

print("build_bungo_granularity secondary sessions: ok")
