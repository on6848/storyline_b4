"""Extract dated location statements from a person's article."""

import calendar
import ipaddress
import json
import os
import re
import socket
from datetime import date
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


MAX_BYTES = 2_000_000
USER_AGENT = "StorylineEditor/0.1 (local research visualization)"
# LLM-based extraction (StoryExplorer, arXiv:2411.05435, section 5.1: a chain-of-thought
# prompt frames the model as a data analyst extracting entities from text).
# Used ahead of the regex pipeline below when an API key is configured; falls
# back to the regex pipeline on any failure so imports keep working offline.
# Uses Gemini's free tier (https://aistudio.google.com/apikey) so this costs nothing.
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_DEFAULT_MODEL = "gemini-2.0-flash"
LLM_MAX_PARAGRAPHS = 400
YEAR_RE = re.compile(r"(?<!\d)(1[6-9]\d{2}|20\d{2})年(?:（[^）]{0,24}）)?")
ERA_RE = re.compile(r"(明治|大正|昭和|平成|令和)(元|\d{1,2})年")
REL_RE = re.compile(r"(翌年|同年)(?:の)?")
MONTH_RE = re.compile(r"(?<!\d)(1[0-2]|[1-9])月(?:\s*([1-9]|[12]\d|3[01])日)?")
MOVE_RE = re.compile(r"生まれ|生れる|出生|生誕|上京|渡英|渡米|渡仏|渡欧|渡航|渡り|帰国|帰郷|帰還|留学|旅行|移住|転居|移っ|移り|移る|移動|赴任|派遣|滞在|到着|住ん|住む|住まい|入学|入塾|入っ|進学|離れ|戻っ|帰っ|赴い|赴く|訪れ|訪問")
FALLBACK = {"上京": "東京都", "渡英": "イギリス", "渡米": "アメリカ", "渡仏": "フランス", "帰国": "日本", "帰郷": None}
SYNONYMS = {"英国": "イギリス", "英國": "イギリス", "米国": "アメリカ", "米國": "アメリカ", "仏国": "フランス", "清国": "中国", "東京": "東京都", "江戸": "東京都", "横浜": "横浜市", "大阪": "大阪府", "京都": "京都府"}
# Cities and countries without a tree node still appear as reviewable candidates.
PLACE_NAMES = ("名古屋", "松江", "北京", "ハルビン", "ペテルブルク", "ロシア", "シンガポール")
ERA_BASE = {"明治": 1867, "大正": 1911, "昭和": 1925, "平成": 1988, "令和": 2018}


class ArticleParagraphs(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paragraphs = []
        self.in_p = 0
        self.skip = 0
        self.buffer = []
        self.in_li = 0
        self.section = ""

    def handle_starttag(self, tag, attrs):
        if tag == "h2":
            self.section = dict(attrs).get("id", "")
        if tag == "li" and re.search(r"年譜|年表", self.section):
            self.in_li += 1
            if self.in_li == 1:
                self.buffer = []
        elif tag == "p" and not self.in_li:
            self.in_p += 1
            self.buffer = []
        elif tag in {"script", "style", "sup", "table"} and (self.in_p or self.in_li):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag == "li" and self.in_li:
            if self.in_li == 1:
                value = re.sub(r"\s+", " ", "".join(self.buffer)).strip()
                if value:
                    self.paragraphs.append(value)
                self.buffer = []
            self.in_li -= 1
        elif tag == "p" and self.in_p:
            value = re.sub(r"\s+", " ", "".join(self.buffer)).strip()
            if value:
                self.paragraphs.append(value)
            self.in_p -= 1
            self.buffer = []
        elif tag in {"script", "style", "sup", "table"} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if (self.in_p or self.in_li) and not self.skip:
            self.buffer.append(data)


def check_url(url):
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError("公開HTTPS記事のURLを入力してください。")
    host = parts.hostname
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    except socket.gaierror as error:
        raise ValueError("記事のホスト名を解決できません。") from error
    if not addresses or any(not ipaddress.ip_address(value).is_global for value in addresses):
        raise ValueError("公開サイトのURLを入力してください。")
    return parts


class CheckedRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def read_url(url):
    check_url(url)
    opener = build_opener(CheckedRedirect())
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"})
    with opener.open(request, timeout=15) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/json"}:
            raise ValueError("HTML記事を指定してください。")
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("記事が大きすぎます。")
        charset = response.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def fetch_article(url):
    parts = check_url(url)
    if parts.hostname == "ja.wikipedia.org" and (parts.path.startswith("/wiki/") or parts.path == "/w/index.php"):
        title = unquote(parts.path.removeprefix("/wiki/")).replace("_", " ") if parts.path.startswith("/wiki/") else parse_qs(parts.query).get("title", [""])[0]
        if not title:
            raise ValueError("Wikipediaの記事名が見つかりません。")
        api = "https://ja.wikipedia.org/w/api.php?" + urlencode({"action": "parse", "page": title, "prop": "text", "format": "json", "formatversion": 2, "redirects": 1})
        payload = json.loads(read_url(api))
        if "error" in payload:
            raise ValueError(payload["error"].get("info", "記事を取得できません。"))
        page = payload.get("parse", {})
        html = page.get("text", "")
        title = page.get("title", title)
        canonical = "https://ja.wikipedia.org/wiki/" + quote(title.replace(" ", "_"))
    else:
        html = read_url(url)
        title = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        title = re.sub(r"\s+", " ", title.group(1)).strip() if title else parts.hostname
        canonical = url
    parser = ArticleParagraphs()
    parser.feed(html)
    if not parser.paragraphs:
        raise ValueError("記事の本文を抽出できません。")
    return title, canonical, parser.paragraphs


def decimal_year(year, month=None, day=None):
    if month is None:
        return float(year)
    if day is None:
        return round(year + (month - 1) / 12, 5)
    try:
        d = date(year, month, day)
    except ValueError:
        return None
    days = 366 if calendar.isleap(year) else 365
    return round(year + (d.timetuple().tm_yday - 1) / days, 5)


def location_aliases(locations):
    by_name = {place["name"]: place["id"] for place in locations}
    aliases = []
    for name, loc_id in by_name.items():
        if name not in {"海外", "日本", "欧州"}:
            aliases.append((name, name, loc_id))
        for part in name.split("・"):
            if len(part) >= 3 and part != name:
                aliases.append((part, name, loc_id))
    for alias, canonical in SYNONYMS.items():
        if canonical in by_name:
            aliases.append((alias, canonical, by_name[canonical]))
    for name in PLACE_NAMES:
        aliases.append((name, name, by_name.get(name)))
    aliases.sort(key=lambda item: (-len(item[0]), item[0], item[1]))
    return aliases, by_name


def modern_place_aliases(paragraphs, aliases, by_name):
    replacements = {}
    for paragraph in paragraphs:
        for match in re.finditer(r"([一-龥ぁ-んァ-ヶ・]{2,20})[（(]現在の([^）)]+)[）)]", paragraph):
            historical, modern = match.group(1), match.group(2).strip()
            known = [(modern.find(alias), len(alias), name, loc_id) for alias, name, loc_id in aliases
                     if loc_id is not None and alias in modern and not (alias == "京都" and "東京都" in modern)]
            if modern in by_name:
                replacements[historical] = (by_name[modern], modern)
            elif known and max(known)[0] > 0:
                _, _, name, loc_id = max(known)
                replacements[historical] = (loc_id, name)
            else:
                replacements[historical] = (None, modern)
    return replacements


def locate(text, aliases, by_name, modern_aliases=None):
    if modern_aliases:
        matches = [(len(alias), alias, target) for alias, target in modern_aliases.items() if alias in text]
        if matches:
            _, _, (loc_id, name) = max(matches, key=lambda item: (item[0], item[1]))
            return loc_id, name, loc_id is not None
    matches = [(text.find(alias), len(alias), name, loc_id) for alias, name, loc_id in aliases if alias in text]
    if matches:
        # The most specific mention wins; when equally specific, use the last one in the clause.
        match = sorted(matches, key=lambda item: (-item[1], -item[0], item[2]))[0]
        return match[3], match[2], True
    for cue, canonical in FALLBACK.items():
        if cue in text and canonical in by_name:
            return by_name[canonical], canonical, False
    unknown = re.search(r"([一-龥ぁ-んァ-ヶ]{2,12}(?:市|区|県|府|町|村|国))(?=へ|に|で|から|を)", text)
    return None, unknown.group(1) if unknown else "", False


def date_tokens(sentence, context_year):
    markers = []
    for match in YEAR_RE.finditer(sentence):
        markers.append((match.start(), match.end(), int(match.group(1)), "year"))
    for match in ERA_RE.finditer(sentence):
        year = ERA_BASE[match.group(1)] + (1 if match.group(2) == "元" else int(match.group(2)))
        if not any(token[0] <= match.start() < token[1] for token in markers):
            markers.append((match.start(), match.end(), year, "year"))
    for match in REL_RE.finditer(sentence):
        markers.append((match.start(), match.end(), 1 if match.group(1) == "翌年" else 0, "relative"))
    markers.sort(key=lambda item: (item[0], item[1]))
    current = context_year
    tokens = []
    for start, end, value, kind in markers:
        if kind == "relative":
            if current is None:
                continue
            current += value
        else:
            current = value
        tokens.append((start, end, current, None, None, "year"))
    dated = list(tokens)
    for match in MONTH_RE.finditer(sentence):
        preceding = [token for token in tokens if token[0] < match.start()]
        year = preceding[-1][2] if preceding else context_year
        if year is not None:
            dated.append((match.start(), match.end(), year, int(match.group(1)), int(match.group(2)) if match.group(2) else None, "month"))
    dated.sort(key=lambda item: (item[0], 0 if item[5] == "year" else 1))
    # An era and Gregorian year in the same parentheses describe one date.
    compact = []
    for token in dated:
        if token[5] == "year" and compact and compact[-1][5] == "year" and compact[-1][2] == token[2] and token[0] - compact[-1][1] <= 3:
            continue
        compact.append(token)
    return compact, current


def extract_candidates(paragraphs, person, locations, url):
    aliases, by_name = location_aliases(locations)
    modern_aliases = modern_place_aliases(paragraphs, aliases, by_name)
    candidates = []
    context_year = None
    old_calendar_until = None
    for paragraph in paragraphs:
        old_calendar_note = re.search(r"(?:日付)?(1[6-9]\d{2})年までは旧暦", paragraph)
        if old_calendar_note:
            old_calendar_until = int(old_calendar_note.group(1))
            continue
        paragraph_date = None
        for sentence in re.split(r"[。！？]", paragraph):
            sentence = sentence.strip()
            if not sentence:
                continue
            tokens, context_year = date_tokens(sentence, context_year)
            if not tokens and re.search(r"生まれ|生れる|出生", sentence):
                tokens = [(0, 0, person["birthYear"], None, None, "birth")]
            elif not tokens and paragraph_date and MOVE_RE.search(sentence):
                tokens = [(0, 0, paragraph_date[2], paragraph_date[3], paragraph_date[4], "inherited")]
            if tokens:
                paragraph_date = tokens[-1]
            for index, token in enumerate(tokens):
                start = token[1]
                end = tokens[index + 1][0] if index + 1 < len(tokens) else len(sentence)
                fragment = sentence[start:end].strip(" 、（）")
                if not fragment or not MOVE_RE.search(fragment):
                    continue
                old_calendar = old_calendar_until is not None and token[2] <= old_calendar_until and re.match(r"\d{4}年\s*[-－]", paragraph)
                year = decimal_year(token[2]) if old_calendar else decimal_year(token[2], token[3], token[4])
                if year is None or not person["birthYear"] <= year < person["deathYear"]:
                    continue
                clauses = re.split("[、，]", fragment)
                for clause_index, clause in enumerate(clauses):
                    implied_move = clause_index > 0 and "離れ" in clauses[clause_index - 1] and re.search(r"[へにでの]", clause)
                    if not MOVE_RE.search(clause) and not implied_move:
                        continue
                    if "離れ" in clause:
                        continue
                    if "帰国途中" in clause or "帰国することになる" in clause:
                        continue
                    loc_id, place, explicit = locate(clause, aliases, by_name, modern_aliases)
                    if loc_id is None and not place:
                        continue
                    confidence = 0.95 if explicit and token[4] else 0.86 if explicit and token[3] else 0.82 if explicit else 0.7
                    if old_calendar:
                        confidence = min(confidence, 0.6)
                    evidence = re.sub(r"\s+", " ", clause).strip()[:100]
                    candidates.append({"year": year, "location": loc_id, "place": place, "evidence": evidence, "source": url, "confidence": confidence})
    return dedupe_candidates(candidates)


def dedupe_candidates(candidates):
    deduped = {}
    for item in candidates:
        key = (item["year"], item["location"], item["place"])
        if key not in deduped or item["confidence"] > deduped[key]["confidence"]:
            deduped[key] = item
    return sorted(deduped.values(), key=lambda item: (item["year"], item["place"]))


def _llm_system_prompt():
    return (
        "あなたは歴史上の人物の経歴から、日付と場所の移動を正確に抽出する熟練データアナリストです。"
        "与えられた文章だけを根拠にし、記載のない年や場所を創作してはいけません。"
        "出力は有効なJSON配列のみとし、前置き・説明文・コードフェンスは一切含めないでください。"
    )


def _llm_user_prompt(paragraphs, person, locations):
    location_names = sorted({loc["name"] for loc in locations if loc.get("name")})
    numbered = "\n".join(paragraphs[:LLM_MAX_PARAGRAPHS])
    return (
        f"人物: {person.get('name', '')}（生年 {person.get('birthYear')} - 没年 {person.get('deathYear')}）\n\n"
        "手順:\n"
        "1. 各文を読み、この人物が特定の年(または年月日)に特定の場所へ出生・移動・滞在・帰国した、という記述を探す。\n"
        "2. 元号(明治・大正・昭和・平成・令和)は西暦に変換する。「翌年」「同年」などの相対表現は直前に確定した年を基準に解決する。\n"
        "3. 場所の名称は、可能であれば次の既知の場所リストの表記に合わせる(リストに無ければ記事中の表記のまま): "
        f"{'、'.join(location_names)}\n"
        "4. 1件ごとに、その根拠となった記事中の短い引用(evidence)を必ず含める。\n"
        "5. 確信が持てない項目は confidence を低くする(0.0〜0.95の範囲)。\n\n"
        "出力は次の形式のJSON配列のみ(月日が不明な場合は month/day を null にする):\n"
        '[{"year": 1888, "month": 4, "day": 28, "location_name": "サンフランシスコ", '
        '"evidence": "4月28日にサンフランシスコへ到着", "confidence": 0.9}]\n\n'
        "本文:\n"
        f"{numbered}"
    )


def call_llm_extractor(paragraphs, person, locations):
    """Call the configured LLM to extract (time, place, evidence) quadruples.

    Returns None when no API key is configured (silent fallback to regex).
    Raises on any API/parse failure so the caller can log and still fall back.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    model = os.environ.get("ARTICLE_IMPORT_LLM_MODEL", GEMINI_DEFAULT_MODEL)
    url = GEMINI_API_URL.format(model=model) + "?" + urlencode({"key": api_key})
    body = json.dumps({
        "systemInstruction": {"parts": [{"text": _llm_system_prompt()}]},
        "contents": [{"parts": [{"text": _llm_user_prompt(paragraphs, person, locations)}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 4096},
    }).encode("utf-8")
    request = Request(url, data=body, headers={"content-type": "application/json"})
    with build_opener().open(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    raw_candidates = payload.get("candidates") or []
    if not raw_candidates:
        raise ValueError("Geminiから有効な応答がありませんでした。")
    parts = raw_candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts)
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        raise ValueError("LLMの応答からJSON配列を抽出できませんでした。")
    return json.loads(match.group(0))


def _resolve_location_name(location_name, aliases, by_name):
    if location_name in by_name:
        return by_name[location_name], location_name
    for alias, canonical, loc_id in aliases:
        if loc_id is not None and alias in location_name:
            return loc_id, canonical
    return None, location_name


def extract_candidates_llm(paragraphs, person, locations, url):
    """LLM counterpart to extract_candidates(), same output schema.

    Returns None (not an empty list) when extraction was not attempted
    (no API key), so the caller can distinguish "skip" from "found nothing".
    """
    raw_items = call_llm_extractor(paragraphs, person, locations)
    if raw_items is None:
        return None
    aliases, by_name = location_aliases(locations)
    candidates = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        try:
            year_raw = raw.get("year")
            if year_raw is None:
                continue
            month = raw.get("month")
            day = raw.get("day")
            year = decimal_year(
                int(year_raw),
                int(month) if isinstance(month, (int, float)) else None,
                int(day) if isinstance(day, (int, float)) else None,
            )
        except (TypeError, ValueError):
            continue
        if year is None or not person["birthYear"] <= year < person["deathYear"]:
            continue
        location_name = str(raw.get("location_name") or "").strip()
        if not location_name:
            continue
        loc_id, place = _resolve_location_name(location_name, aliases, by_name)
        confidence = raw.get("confidence")
        confidence = min(max(float(confidence), 0.0), 0.95) if isinstance(confidence, (int, float)) else 0.75
        evidence = re.sub(r"\s+", " ", str(raw.get("evidence") or "")).strip()[:100]
        candidates.append({"year": year, "location": loc_id, "place": place, "evidence": evidence, "source": url, "confidence": confidence})
    return dedupe_candidates(candidates)


def import_article(url, person, locations):
    title, canonical, paragraphs = fetch_article(url)
    try:
        llm_candidates = extract_candidates_llm(paragraphs, person, locations, canonical)
    except Exception as error:
        print(f"[article_import] LLM抽出に失敗したため正規表現にフォールバックします: {error}")
        llm_candidates = None
    if llm_candidates is not None:
        return {"title": title, "url": canonical, "candidates": llm_candidates, "method": "llm"}
    return {"title": title, "url": canonical, "candidates": extract_candidates(paragraphs, person, locations, canonical), "method": "regex"}
