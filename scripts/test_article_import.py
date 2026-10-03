import json
import os
from pathlib import Path

import article_import
from article_import import ArticleParagraphs, check_url, date_tokens, extract_candidates, extract_candidates_llm


base = json.loads((Path(__file__).resolve().parents[1] / "dataset" / "bungo_relationships.json").read_text(encoding="utf-8"))
person = next(item for item in base["characters"] if item["name"] == "末広鉄腸")
paragraphs = [
    "1849年、宇和島市に生まれた。",
    "1888年4月28日にサンフランシスコへ到着、5月16日にイギリスへ到着。翌年2月帰国した。",
]
items = extract_candidates(paragraphs, person, base["locations"], "https://example.org/person")
assert [(item["year"], item["place"]) for item in items] == [
    (1849.0, "宇和島市"),
    (1888.3224, "サンフランシスコ"),
    (1888.37158, "イギリス"),
    (1889.08333, "日本"),
]

parser = ArticleParagraphs()
parser.feed('<p>1908年、ロシアに赴任。同年、ペテルブルクへ移る。</p>'
            '<h2 id="年譜">年譜</h2><p>※日付1872年までは旧暦</p>'
            '<ul><li>1868年 - 11月、名古屋に移る。</li>'
            '<li>1872年 - 5月、退学。10月、東京に移り、麹町区に住む。</li>'
            '<li>1902年 - 5月、職を辞す。大陸に渡りハルビンで働く。</li></ul>'
            '<h2 id="作品一覧">作品一覧</h2><ul><li>1909年、ロシアに赴任。</li></ul>')
assert len(parser.paragraphs) == 5
futabayashi = {"birthYear": 1864, "deathYear": 1909}
imported = extract_candidates(parser.paragraphs, futabayashi, base["locations"], "https://example.org/article")
assert {(item["year"], item["place"]) for item in imported} >= {
    (1868.0, "名古屋"), (1872.0, "東京都"), (1902.33333, "ハルビン"),
    (1908.0, "ロシア"), (1908.0, "ペテルブルク"),
}
assert not any(item["year"] == 1905 for item in imported)
assert date_tokens("1908年に赴任し、同年に移る。翌年帰国。", 1904)[0][-1][2] == 1909
modern = ["江戸市ヶ谷（現在の東京都新宿区市ヶ谷）。", "江戸市ヶ谷に生まれた。"]
# Isolated location list (not the live dataset) so this stays correct even after
# someone adds a real "新宿区" via the editor's own place-creation feature.
no_ward_locations = [loc for loc in base["locations"] if loc["name"] not in {"新宿区", "市ヶ谷"}]
modern_items = extract_candidates(modern, futabayashi, no_ward_locations, "https://example.org/article")
assert modern_items[0]["place"] == "東京都新宿区市ヶ谷" and modern_items[0]["location"] is None
modern_locations = no_ward_locations + [{"id": 9999, "name": "新宿区"}]
modern_items = extract_candidates(modern, futabayashi, modern_locations, "https://example.org/article")
assert modern_items[0]["place"] == "新宿区" and modern_items[0]["location"] == 9999
try:
    check_url("https://127.0.0.1/private")
except ValueError:
    pass
else:
    raise AssertionError("private URLs must be rejected")

# LLM extraction path: no API key configured -> signals "not attempted" (None),
# distinct from "found nothing" ([]), so import_article() knows to fall back.
os.environ.pop("GEMINI_API_KEY", None)
assert extract_candidates_llm(paragraphs, person, base["locations"], "https://example.org/person") is None

# With a key "configured", mock the model call and check resolution/dedup/year-bounds.
os.environ["GEMINI_API_KEY"] = "test-key"
try:
    raw_items = [
        {"year": 1888, "month": 4, "day": 28, "location_name": "サンフランシスコ", "evidence": "4月28日到着", "confidence": 0.9},
        {"year": 1888, "month": 4, "day": 28, "location_name": "サンフランシスコ", "evidence": "dup, lower confidence", "confidence": 0.5},
        {"year": 1905, "location_name": "東京都", "evidence": "out of lifespan, must be dropped", "confidence": 0.9},
        {"year": 1849, "location_name": "宇和島市", "evidence": "生まれた", "confidence": None},
    ]
    original_call = article_import.call_llm_extractor
    article_import.call_llm_extractor = lambda paragraphs, person, locations: raw_items
    try:
        llm_items = extract_candidates_llm(paragraphs, person, base["locations"], "https://example.org/person")
    finally:
        article_import.call_llm_extractor = original_call
finally:
    os.environ.pop("GEMINI_API_KEY", None)

assert [(item["year"], item["place"], item["confidence"]) for item in llm_items] == [
    (1849.0, "宇和島市", 0.75),
    (1888.3224, "サンフランシスコ", 0.9),
]
assert not any(item["year"] == 1905 for item in llm_items)

print("article import: ok")
