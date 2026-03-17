"""Disaster relief navigator for a Nemotron-focused hackathon MVP.

This script helps a user affected by natural disasters:
- capture their situation
- map needs to relevant state and federal resources
- generate a structured action plan
- optionally ask NVIDIA Nemotron to turn that plan into a more polished response

The default experience works without any third-party packages or API keys.
It can:
- run fully offline with bundled disaster resources
- cache website snapshots locally when connectivity is available
- use NVIDIA Nemotron Super online or switch to a local Nemotron server
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib import error, request
from urllib.parse import urlparse


SYSTEM_PROMPT = """You are ReliefRoute, an AI assistant for U.S. residents affected by
natural disasters.

Your job:
1. Explain the person's most urgent safety and recovery priorities.
2. Use only the provided structured plan, resource list, and retrieved evidence.
3. Keep the response compassionate, practical, and direct.
4. Organize the answer into:
   - Immediate priorities
   - What to do in the next 24 hours
   - Benefits and resources to contact
   - Documents to gather
   - Special risks or warnings
5. Do not invent benefits, phone numbers, deadlines, eligibility rules, or qualification decisions.
6. Never say the user definitely qualifies. Use phrasing like "may be relevant" or "check eligibility with".
7. If retrieved evidence is missing for a claim, say you do not have enough grounded information.
8. If the plan says the user is in immediate danger, say to call 911.
"""

DEFAULT_ONLINE_NEMOTRON_MODEL = os.getenv(
    "RELIEFROUTE_ONLINE_MODEL",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
)
DEFAULT_ONLINE_BASE_URL = os.getenv(
    "RELIEFROUTE_ONLINE_BASE_URL",
    "https://integrate.api.nvidia.com/v1",
)
DEFAULT_LOCAL_NEMOTRON_MODEL = os.getenv("RELIEFROUTE_LOCAL_MODEL", "nemotron")
DEFAULT_LOCAL_BASE_URL = os.getenv(
    "RELIEFROUTE_LOCAL_BASE_URL",
    "http://127.0.0.1:1234/v1",
)


@dataclass(frozen=True)
class Resource:
    name: str
    category: str
    url: str
    description: str
    state_code: str = "CA"
    disaster_types: tuple[str, ...] = ("wildfire", "earthquake")
    counties: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    required_information: tuple[str, ...] = ()
    required_documents: tuple[str, ...] = ()


@dataclass
class UserProfile:
    state_code: str
    disaster_type: str
    county: str
    situation: str
    housing_damage: str
    insurance_status: str
    household_size: int
    has_medical_need: bool
    has_mobility_need: bool
    needs_shelter: bool
    needs_food: bool
    needs_documents: bool
    needs_pet_help: bool
    income_disrupted: bool
    safe_now: bool


@dataclass
class ActionPlan:
    title: str
    risk_level: str
    immediate_priorities: list[str] = field(default_factory=list)
    next_24_hours: list[str] = field(default_factory=list)
    resources: list[Resource] = field(default_factory=list)
    state_resources: list[Resource] = field(default_factory=list)
    federal_resources: list[Resource] = field(default_factory=list)
    documents_to_gather: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    state_services_by_state: dict[str, list[Resource]] = field(default_factory=dict)


class HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.ignored_tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.ignored_tags.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.ignored_tags and self.ignored_tags[-1] == tag:
            self.ignored_tags.pop()

    def handle_data(self, data: str) -> None:
        if self.ignored_tags:
            return
        text = data.strip()
        if text:
            self.parts.append(text)

    def get_text(self) -> str:
        return " ".join(self.parts)


STATE_NAMES: dict[str, str] = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
}

ZIP3_STATE_RANGES: dict[str, tuple[tuple[int, int], ...]] = {
    "AL": ((350, 369),),
    "AK": ((995, 999),),
    "AZ": ((850, 853), (855, 857), (859, 865)),
    "AR": ((716, 729),),
    "CA": ((900, 908), (910, 918), (919, 925), (926, 928), (930, 939), (940, 961)),
    "CO": ((800, 816),),
    "CT": ((60, 69),),
    "DE": ((197, 199),),
    "FL": ((320, 339), (341, 342), (344, 344), (346, 347), (349, 349)),
    "GA": ((300, 319), (398, 399)),
    "HI": ((967, 968),),
    "ID": ((832, 838),),
    "IL": ((600, 629),),
    "IN": ((460, 479),),
    "IA": ((500, 528),),
    "KS": ((660, 679),),
    "KY": ((400, 427),),
    "LA": ((700, 714),),
    "ME": ((39, 49),),
    "MD": ((206, 219),),
    "MA": ((10, 27), (55, 55)),
    "MI": ((480, 499),),
    "MN": ((550, 567),),
    "MS": ((386, 397),),
    "MO": ((630, 658),),
    "MT": ((590, 599),),
    "NE": ((680, 693),),
    "NV": ((889, 898),),
    "NH": ((30, 38),),
    "NJ": ((70, 89),),
    "NM": ((870, 884),),
    "NY": ((5, 5), (100, 149)),
    "NC": ((270, 289),),
    "ND": ((580, 588),),
    "OH": ((430, 459),),
    "OK": ((730, 731), (734, 749)),
    "OR": ((970, 979),),
    "PA": ((150, 196),),
    "RI": ((28, 29),),
    "SC": ((290, 299),),
    "SD": ((570, 577),),
    "TN": ((370, 385),),
    "TX": ((733, 733), (750, 799), (885, 885)),
    "UT": ((840, 847),),
    "VT": ((50, 59),),
    "VA": ((201, 201), (220, 246)),
    "WA": ((980, 994),),
    "WV": ((247, 268),),
    "WI": ((530, 549),),
    "WY": ((820, 831),),
}


def default_cache_dir() -> Path:
    return Path(__file__).resolve().parent / "cache"


def default_data_dir() -> Path:
    return Path(__file__).resolve().parent / "data"


def default_rag_db_path() -> Path:
    return Path(__file__).resolve().parent / "reliefroute_rag.sqlite3"


def default_rag_dir() -> Path:
    return Path(__file__).resolve().parent / "rag"


def rag_db_paths_for_state(state_code: str, rag_dir: Path | None = None) -> dict[str, Path]:
    base_dir = rag_dir or default_rag_dir()
    normalized_state = state_code.upper()
    return {
        "federal": base_dir / "federal.sqlite3",
        "state": base_dir / f"{normalized_state.lower()}.sqlite3",
    }


def slugify_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def clean_text(raw_html: str) -> str:
    extractor = HTMLTextExtractor()
    extractor.feed(raw_html)
    text = extractor.get_text()
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"@font-face\s*\{.*?\}", " ", text, flags=re.DOTALL)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"gtag\([^)]*\)", " ", text)
    text = re.sub(r"window\.\w+\s*=\s*[^;]+;?", " ", text)
    text = re.sub(r"[{};]|\\u[0-9a-fA-F]{4}", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Remove common boilerplate fragments and keep the highest-signal prefix.
    boilerplate_markers = [
        "Skip to main content",
        "An official website of the United States government",
        "window.dataLayer",
        "gtag",
        "@font-face",
    ]
    for marker in boilerplate_markers:
        text = text.replace(marker, " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def cache_path_for(resource: Resource, cache_dir: Path) -> Path:
    return cache_dir / f"{slugify_url(resource.url)}.json"


def fetch_resource_text(resource: Resource, timeout: int = 20) -> str:
    req = request.Request(
        resource.url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        method="GET",
    )
    with request.urlopen(req, timeout=timeout) as response:
        raw_html = response.read().decode("utf-8", errors="replace")
    return clean_text(raw_html)


def best_summary_from_text(text: str, limit: int = 1800) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    kept: list[str] = []
    total = 0
    for sentence in sentences:
        stripped = sentence.strip()
        if len(stripped) < 30:
            continue
        if any(token in stripped.lower() for token in ["cookie", "javascript", "analytics", "font", "privacy policy"]):
            continue
        kept.append(stripped)
        total += len(stripped) + 1
        if total >= limit:
            break
    summary = " ".join(kept).strip()
    return (summary or text)[:limit]


def write_resource_cache(
    resource: Resource,
    cache_dir: Path,
    summary: str,
    summary_source: str,
    source_text: str | None = None,
) -> dict:
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "name": resource.name,
        "url": resource.url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary[:1800],
        "summary_source": summary_source,
        "source_text": (source_text or summary)[:12000],
    }
    with open(cache_path_for(resource, cache_dir), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return payload


def read_resource_cache(resource: Resource, cache_dir: Path) -> dict | None:
    path = cache_path_for(resource, cache_dir)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_cached_resource_summaries(resources: list[Resource], cache_dir: Path) -> list[dict]:
    cached: list[dict] = []
    for resource in resources:
        payload = read_resource_cache(resource, cache_dir)
        if payload:
            cached.append(payload)
    return cached


def load_zip_state_map(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return {str(key).zfill(5): str(value).upper() for key, value in data.items()}


def resource_from_record(record: dict) -> Resource:
    return Resource(
        name=record["name"],
        category=record["category"],
        url=record["url"],
        description=record["description"],
        state_code=record.get("state_code", "CA"),
        disaster_types=tuple(record.get("disaster_types", ["wildfire", "earthquake"])),
        counties=tuple(record.get("counties", [])),
        tags=tuple(record.get("tags", [])),
        required_information=tuple(record.get("required_information", [])),
        required_documents=tuple(record.get("required_documents", [])),
    )


def load_resource_database() -> list[Resource]:
    data_dir = default_data_dir()
    resources: list[Resource] = []

    federal_path = data_dir / "federal_resources.json"
    with open(federal_path, "r", encoding="utf-8") as handle:
        for record in json.load(handle):
            resources.append(resource_from_record(record))

    states_dir = data_dir / "states"
    for state_code in sorted(STATE_NAMES):
        state_path = states_dir / f"{state_code.lower()}.json"
        with open(state_path, "r", encoding="utf-8") as handle:
            for record in json.load(handle):
                resources.append(resource_from_record(record))

    return resources


RESOURCE_DB = load_resource_database()


def infer_state_from_zipcode(zipcode: str | None, zip_state_map: dict[str, str]) -> str | None:
    if not zipcode:
        return None
    cleaned = "".join(ch for ch in zipcode if ch.isdigit())[:5]
    if len(cleaned) != 5:
        return None
    if cleaned in zip_state_map:
        return zip_state_map[cleaned]
    zip3 = int(cleaned[:3])
    for state_code, ranges in ZIP3_STATE_RANGES.items():
        for start, end in ranges:
            if start <= zip3 <= end:
                return state_code
    return None


def split_resources(resources: list[Resource]) -> tuple[list[Resource], list[Resource]]:
    state_resources: list[Resource] = []
    federal_resources: list[Resource] = []
    for resource in resources:
        if resource.category == "federal aid" or "federal" in resource.tags:
            federal_resources.append(resource)
        else:
            state_resources.append(resource)
    return state_resources, federal_resources


def available_resources_for_state(state_code: str) -> list[Resource]:
    return [resource for resource in RESOURCE_DB if resource.state_code in {state_code, "US"}]


def resource_database_links_by_category(state_code: str) -> dict[str, list[Resource]]:
    resources = available_resources_for_state(state_code)
    state_resources, federal_resources = split_resources(resources)
    return {
        "state": state_resources,
        "federal": federal_resources,
    }


def rag_resource_sets_for_state(state_code: str) -> dict[str, list[Resource]]:
    categorized = resource_database_links_by_category(state_code)
    return {
        "federal": categorized["federal"],
        "state": categorized["state"],
    }


def group_state_resources(resources: list[Resource]) -> dict[str, list[Resource]]:
    grouped: dict[str, list[Resource]] = {}
    for resource in resources:
        if resource.state_code == "US":
            continue
        grouped.setdefault(resource.state_code, []).append(resource)
    return grouped


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> list[str]:
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def normalized_terms(text: str) -> list[str]:
    raw_terms = [term.lower() for term in re.findall(r"[a-zA-Z0-9]+", text)]
    normalized: list[str] = []
    for term in raw_terms:
        if len(term) <= 2:
            continue
        normalized.append(term)
        if term.endswith("s") and len(term) > 3:
            normalized.append(term[:-1])
    return normalized


def get_resource_text_for_rag(resource: Resource, cache_dir: Path) -> str:
    cached = read_resource_cache(resource, cache_dir)
    if cached:
        source_text = cached.get("source_text")
        if source_text:
            return str(source_text)
        if cached.get("summary"):
            return str(cached["summary"])
    try:
        return fetch_resource_text(resource)
    except Exception:  # noqa: BLE001
        fallback_parts = [
            resource.name,
            resource.description,
            f"Required information: {', '.join(resource.required_information) or 'none listed'}",
            f"Required documents: {', '.join(resource.required_documents) or 'none listed'}",
        ]
        return " ".join(fallback_parts)


def build_local_rag_database(resources: list[Resource], cache_dir: Path, db_path: Path) -> list[str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    statuses: list[str] = []
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS resource_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_name TEXT NOT NULL,
                state_code TEXT NOT NULL,
                category TEXT NOT NULL,
                url TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL
            )
            """
        )
        connection.execute("DELETE FROM resource_chunks")

        for resource in resources:
            try:
                source_text = get_resource_text_for_rag(resource, cache_dir)
                chunks = chunk_text(source_text)
                for idx, chunk in enumerate(chunks):
                    connection.execute(
                        """
                        INSERT INTO resource_chunks
                        (resource_name, state_code, category, url, chunk_index, content)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            resource.name,
                            resource.state_code,
                            resource.category,
                            resource.url,
                            idx,
                            chunk,
                        ),
                    )
                statuses.append(f"indexed {resource.name} with {len(chunks)} chunks")
            except Exception as exc:  # noqa: BLE001
                statuses.append(f"failed to index {resource.name}: {exc}")
        connection.commit()
    finally:
        connection.close()
    return statuses


def build_scoped_rag_databases(state_code: str, cache_dir: Path, rag_dir: Path) -> list[str]:
    statuses: list[str] = []
    rag_paths = rag_db_paths_for_state(state_code, rag_dir)
    for scope, resources in rag_resource_sets_for_state(state_code).items():
        statuses.append(f"{scope} database: {rag_paths[scope]}")
        for status in build_local_rag_database(resources, cache_dir, rag_paths[scope]):
            statuses.append(f"[{scope}] {status}")
    return statuses


def query_local_rag_database(db_path: Path, question: str, limit: int = 5) -> list[dict]:
    if not db_path.exists():
        return []
    terms = normalized_terms(question)
    if not terms:
        return []
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT resource_name, state_code, category, url, chunk_index, content
            FROM resource_chunks
            """
        ).fetchall()
    finally:
        connection.close()

    scored: list[tuple[int, sqlite3.Row]] = []
    for row in rows:
        haystack_terms = normalized_terms(row["content"])
        haystack_set = set(haystack_terms)
        score = sum(haystack_terms.count(term) for term in terms if term in haystack_set)
        if score:
            scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    results: list[dict] = []
    for score, row in scored[:limit]:
        results.append(
            {
                "score": score,
                "resource_name": row["resource_name"],
                "state_code": row["state_code"],
                "category": row["category"],
                "url": row["url"],
                "chunk_index": row["chunk_index"],
                "content": row["content"],
            }
        )
    return results


def query_scoped_rag_databases(
    state_code: str,
    rag_dir: Path,
    question: str,
    scope: str,
    limit: int = 5,
) -> list[dict]:
    rag_paths = rag_db_paths_for_state(state_code, rag_dir)
    scopes = ["federal", "state"] if scope == "all" else [scope]
    combined: list[dict] = []
    for current_scope in scopes:
        for result in query_local_rag_database(rag_paths[current_scope], question, limit=limit):
            enriched = dict(result)
            enriched["scope"] = current_scope
            combined.append(enriched)
    combined.sort(key=lambda item: item["score"], reverse=True)
    return combined[:limit]


def grounding_queries_for_profile(profile: UserProfile) -> dict[str, str]:
    return {
        "federal": (
            f"{profile.disaster_type} disaster assistance federal housing documents "
            f"{profile.insurance_status} household {profile.household_size}"
        ),
        "state": (
            f"{profile.state_code} {profile.disaster_type} shelter food insurance state assistance "
            f"{profile.county} documents"
        ),
    }


def build_grounded_model_payload(
    profile: UserProfile,
    plan: ActionPlan,
    cache_dir: Path,
    rag_dir: Path,
    rag_limit_per_scope: int = 4,
) -> tuple[dict | None, str | None]:
    rag_paths = rag_db_paths_for_state(profile.state_code, rag_dir)
    if not rag_paths["federal"].exists() or not rag_paths["state"].exists():
        return None, (
            "Strict grounding is enabled, but the scoped RAG databases are missing. "
            "Run --build-rag-db first."
        )

    queries = grounding_queries_for_profile(profile)
    federal_evidence = query_scoped_rag_databases(
        profile.state_code,
        rag_dir,
        queries["federal"],
        "federal",
        limit=rag_limit_per_scope,
    )
    state_evidence = query_scoped_rag_databases(
        profile.state_code,
        rag_dir,
        queries["state"],
        "state",
        limit=rag_limit_per_scope,
    )

    if not federal_evidence or not state_evidence:
        return None, (
            "Strict grounding found insufficient federal or state evidence. "
            "Refresh caches and rebuild the scoped RAG databases before using Nemotron."
        )

    payload = plan_to_payload(profile, plan, cache_dir)
    payload["grounding_evidence"] = {
        "federal": federal_evidence,
        "state": state_evidence,
        "instructions": [
            "Only reference resources supported by the retrieved evidence.",
            "Do not make qualification or eligibility determinations.",
            "If a resource may be relevant, say 'may be relevant' and point the user to the official resource.",
        ],
    }
    return payload, None


def is_local_base_url(base_url: str) -> bool:
    parsed = urlparse(base_url)
    return parsed.hostname in {"127.0.0.1", "localhost", "0.0.0.0"}


def validate_nemotron_model_name(model: str, context: str) -> None:
    if "nemotron" not in model.lower():
        raise SystemExit(
            f"ReliefRoute CA expects a Nemotron model for {context}. "
            f"Set a Nemotron model name, got: {model}"
        )


def validate_local_nemotron_config(model: str, base_url: str) -> None:
    validate_nemotron_model_name(model, "local inference")
    if not is_local_base_url(base_url):
        raise SystemExit(
            "ReliefRoute CA is configured for a downloaded local Nemotron instance. "
            "Set --local-api-base-url to your local LM Studio server, usually http://127.0.0.1:1234/v1."
        )


def prompt_bool(question: str) -> bool:
    while True:
        answer = input(f"{question} [y/n]: ").strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please answer y or n.")


def prompt_choice(question: str, choices: Iterable[str]) -> str:
    options = list(choices)
    while True:
        print(question)
        for idx, choice in enumerate(options, start=1):
            print(f"  {idx}. {choice}")
        raw = input("Choose a number: ").strip()
        if raw.isdigit():
            picked = int(raw)
            if 1 <= picked <= len(options):
                return options[picked - 1]
        print("Please choose one of the listed numbers.")


def collect_profile_from_prompt() -> UserProfile:
    disaster_type = prompt_choice(
        "What disaster are you dealing with?",
        ["wildfire", "earthquake"],
    )
    county = input("Which California county are you in? ").strip() or "Unknown County"
    situation = input("Briefly describe what happened: ").strip()
    housing_damage = prompt_choice(
        "What best describes your housing situation?",
        ["no damage", "minor damage", "major damage", "destroyed", "not sure"],
    )
    insurance_status = prompt_choice(
        "What is your insurance status?",
        ["insured", "underinsured", "uninsured", "not sure"],
    )
    household_size_raw = input("How many people are in your household? ").strip() or "1"
    household_size = int(household_size_raw)

    return UserProfile(
        state_code="CA",
        disaster_type=disaster_type,
        county=county,
        situation=situation or "No additional details provided.",
        housing_damage=housing_damage,
        insurance_status=insurance_status,
        household_size=household_size,
        has_medical_need=prompt_bool("Does anyone in the household have urgent medical needs?"),
        has_mobility_need=prompt_bool("Does anyone need mobility or disability-related support?"),
        needs_shelter=prompt_bool("Do you need emergency shelter tonight?"),
        needs_food=prompt_bool("Do you need food support right now?"),
        needs_documents=prompt_bool("Do you need help replacing important documents?"),
        needs_pet_help=prompt_bool("Do you need help evacuating or sheltering pets?"),
        income_disrupted=prompt_bool("Has the disaster disrupted your income?"),
        safe_now=prompt_bool("Are you currently in a safe place?"),
    )


def build_plan(profile: UserProfile) -> ActionPlan:
    risk_level = "high" if (not profile.safe_now or profile.has_medical_need or profile.needs_shelter) else "moderate"
    state_name = STATE_NAMES.get(profile.state_code, profile.state_code)
    has_california_211 = profile.state_code == "CA"
    plan = ActionPlan(
        title=f"{state_name} {profile.disaster_type.title()} Recovery Plan for {profile.county}",
        risk_level=risk_level,
    )

    if not profile.safe_now:
        plan.immediate_priorities.append("You are not currently safe. Move to a safer location and call 911 if there is immediate danger.")

    if profile.disaster_type == "wildfire":
        plan.immediate_priorities.append("Monitor evacuation orders and fire updates before returning to any affected area.")
        plan.immediate_priorities.append("Avoid smoke exposure when possible, especially for children, older adults, and anyone with breathing issues.")
        plan.warnings.append("Do not re-enter an evacuation zone until local officials say it is safe.")
    else:
        plan.immediate_priorities.append("Watch for aftershocks and avoid structures with visible structural damage.")
        plan.immediate_priorities.append("Shut off utilities only if you suspect leaks or damage and know it is safe to do so.")
        plan.warnings.append("Aftershocks can happen after the initial quake; damaged buildings may become more dangerous over time.")

    if profile.has_medical_need:
        plan.immediate_priorities.append("Prioritize medication access, medical devices, and transportation to care if needed.")

    if profile.needs_shelter:
        if has_california_211:
            plan.next_24_hours.append("Find same-day shelter options through 211 California or the Red Cross.")
        else:
            plan.next_24_hours.append("Find same-day shelter options through your state emergency management agency, local 211 if available, or the Red Cross.")

    if profile.needs_food:
        if has_california_211:
            plan.next_24_hours.append("Locate food distribution or emergency food support through 211 California and CalFresh partners.")
        else:
            plan.next_24_hours.append("Locate food distribution or emergency food support through your state emergency management agency, local 211 if available, or state benefit agencies.")

    if profile.housing_damage in {"major damage", "destroyed"}:
        plan.next_24_hours.append("Document all property damage with photos and notes before cleanup if it is safe to do so.")
        plan.next_24_hours.append("Start insurance and disaster assistance applications as soon as possible.")
        plan.documents_to_gather.extend(
            [
                "photos or videos of damage",
                "lease, mortgage, or proof of address",
                "insurance policy number and insurer contact details",
            ]
        )

    if profile.insurance_status in {"underinsured", "uninsured", "not sure"}:
        plan.next_24_hours.append("Check for state and federal disaster assistance, and ask for insurance counseling if coverage is unclear.")

    if profile.needs_documents:
        plan.next_24_hours.append("Make a list of missing IDs, insurance papers, banking records, and school or medical documents for replacement.")
        plan.documents_to_gather.append("a list of missing documents and any backups you still have")

    if profile.income_disrupted:
        plan.next_24_hours.append("Review emergency food, unemployment, and local cash-assistance pathways if work has been interrupted.")

    if profile.has_mobility_need:
        plan.warnings.append("Ask for accessible shelter, transportation, and medical-device support early, since these resources can fill quickly.")

    if profile.needs_pet_help:
        plan.next_24_hours.append("Ask shelters and county services about pet-friendly sheltering or animal evacuation support.")

    plan.documents_to_gather.extend(
        [
            "government ID if available",
            "household member names and birth dates",
            "current phone number and safe contact information",
        ]
    )

    plan.resources = select_resources(profile)
    plan.state_resources, plan.federal_resources = split_resources(plan.resources)
    plan.state_services_by_state = group_state_resources(plan.state_resources)
    dedupe_in_place(plan.documents_to_gather)
    dedupe_in_place(plan.immediate_priorities)
    dedupe_in_place(plan.next_24_hours)
    dedupe_in_place(plan.warnings)
    return plan


def select_resources(profile: UserProfile) -> list[Resource]:
    chosen: list[Resource] = []
    for resource in RESOURCE_DB:
        if resource.state_code not in {profile.state_code, "US"}:
            continue
        if profile.disaster_type not in resource.disaster_types:
            continue

        include = False
        if resource.category in {
            "state emergency coordination",
            "preparedness and recovery",
            "federal aid",
            "insurance support",
            "local referrals",
        }:
            include = True
        if profile.needs_shelter and "shelter" in resource.tags:
            include = True
        if profile.needs_food and "food" in resource.tags:
            include = True
        if profile.needs_pet_help and "pets" in resource.tags:
            include = True
        if profile.insurance_status != "insured" and "insurance" in resource.tags:
            include = True
        if profile.income_disrupted and "benefits" in resource.tags:
            include = True
        if profile.disaster_type == "wildfire" and "fire" in resource.tags:
            include = True
        if profile.disaster_type == "earthquake" and "earthquake" in resource.tags:
            include = True

        if include:
            chosen.append(resource)

    # Keep results manageable while allowing richer per-state databases to surface.
    return chosen[:12]


def dedupe_in_place(items: list[str]) -> None:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
    items[:] = deduped


def plan_to_payload(profile: UserProfile, plan: ActionPlan, cache_dir: Path) -> dict:
    cached_resources = load_cached_resource_summaries(plan.resources, cache_dir)
    resource_database = resource_database_links_by_category(profile.state_code)
    return {
        "user_profile": {
            "state_code": profile.state_code,
            "disaster_type": profile.disaster_type,
            "county": profile.county,
            "situation": profile.situation,
            "housing_damage": profile.housing_damage,
            "insurance_status": profile.insurance_status,
            "household_size": profile.household_size,
            "has_medical_need": profile.has_medical_need,
            "has_mobility_need": profile.has_mobility_need,
            "needs_shelter": profile.needs_shelter,
            "needs_food": profile.needs_food,
            "needs_documents": profile.needs_documents,
            "needs_pet_help": profile.needs_pet_help,
            "income_disrupted": profile.income_disrupted,
            "safe_now": profile.safe_now,
        },
        "action_plan": {
            "title": plan.title,
            "risk_level": plan.risk_level,
            "immediate_priorities": plan.immediate_priorities,
            "next_24_hours": plan.next_24_hours,
            "documents_to_gather": plan.documents_to_gather,
            "warnings": plan.warnings,
            "resources": [
                {
                    "name": resource.name,
                    "state_code": resource.state_code,
                    "category": resource.category,
                    "url": resource.url,
                    "description": resource.description,
                    "required_information": list(resource.required_information),
                    "required_documents": list(resource.required_documents),
                }
                for resource in plan.resources
            ],
            "state_resources": [
                {
                    "name": resource.name,
                    "state_code": resource.state_code,
                    "category": resource.category,
                    "url": resource.url,
                    "description": resource.description,
                    "required_information": list(resource.required_information),
                    "required_documents": list(resource.required_documents),
                }
                for resource in plan.state_resources
            ],
            "federal_resources": [
                {
                    "name": resource.name,
                    "state_code": resource.state_code,
                    "category": resource.category,
                    "url": resource.url,
                    "description": resource.description,
                    "required_information": list(resource.required_information),
                    "required_documents": list(resource.required_documents),
                }
                for resource in plan.federal_resources
            ],
            "cached_resource_summaries": cached_resources,
        },
        "resource_database_links": {
            "state": [
                {
                    "name": resource.name,
                    "state_code": resource.state_code,
                    "category": resource.category,
                    "url": resource.url,
                    "description": resource.description,
                }
                for resource in resource_database["state"]
            ],
            "federal": [
                {
                    "name": resource.name,
                    "state_code": resource.state_code,
                    "category": resource.category,
                    "url": resource.url,
                    "description": resource.description,
                }
                for resource in resource_database["federal"]
            ],
        },
    }


def render_local_plan(plan: ActionPlan, cache_dir: Path) -> str:
    lines = [plan.title, f"Risk level: {plan.risk_level}", ""]

    lines.append("Immediate priorities")
    lines.extend(f"- {item}" for item in plan.immediate_priorities)
    lines.append("")

    lines.append("Next 24 hours")
    lines.extend(f"- {item}" for item in plan.next_24_hours)
    lines.append("")

    lines.append("State and local services")
    for resource in plan.state_resources:
        lines.append(f"- {resource.name}: {resource.description} ({resource.url})")
    lines.append("")

    lines.append("Federal services")
    for resource in plan.federal_resources:
        lines.append(f"- {resource.name}: {resource.description} ({resource.url})")
    lines.append("")

    lines.append("Information and documents by service")
    for resource in plan.resources:
        info_text = ", ".join(resource.required_information) if resource.required_information else "none listed"
        doc_text = ", ".join(resource.required_documents) if resource.required_documents else "none listed"
        lines.append(f"- {resource.name}")
        lines.append(f"  Information needed: {info_text}")
        lines.append(f"  Documents to prepare: {doc_text}")
    lines.append("")

    lines.append("Documents to gather")
    lines.extend(f"- {item}" for item in plan.documents_to_gather)

    if plan.warnings:
        lines.append("")
        lines.append("Warnings")
        lines.extend(f"- {item}" for item in plan.warnings)

    cached_resources = load_cached_resource_summaries(plan.resources, cache_dir)
    if cached_resources:
        lines.append("")
        lines.append("Offline cached notes")
        for item in cached_resources:
            fetched_at = item.get("fetched_at", "unknown time")
            summary_source = item.get("summary_source", "unknown")
            summary = item.get("summary", "").strip()
            preview = textwrap.shorten(summary, width=220, placeholder="...")
            lines.append(
                f"- {item.get('name', 'resource')} cached {fetched_at} via {summary_source}: {preview}"
            )

    return "\n".join(lines)


def call_model(
    payload: dict,
    model: str,
    base_url: str,
    api_key: str | None,
    system_prompt: str = SYSTEM_PROMPT,
) -> str:
    request_body = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Create a grounded disaster recovery response for this resident. "
                    "Only mention resources that may be relevant based on the provided evidence. "
                    "Do not say they qualify unless the evidence explicitly says so.\n\n"
                    f"{json.dumps(payload, indent=2)}"
                ),
            },
        ],
    }

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = request.Request(
        url=f"{base_url}/chat/completions",
        data=json.dumps(request_body).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
    except error.URLError as exc:
        return f"Model call failed: {exc}"

    try:
        return body["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        return "The model server returned an unexpected response shape."


def summarize_resource_with_model(
    resource: Resource,
    resource_text: str,
    model: str,
    base_url: str,
    api_key: str | None,
) -> str:
    payload = {
        "resource_name": resource.name,
        "resource_url": resource.url,
        "resource_text": resource_text[:12000],
        "instruction": (
            "Summarize this resource for offline California wildfire and earthquake recovery. "
            "Keep the summary concise, stable, practical, and action-oriented. "
            "Return plain text under 220 words."
        ),
    }
    return call_model(
        payload,
        model,
        base_url,
        api_key,
        system_prompt=(
            "You prepare offline cache summaries for a California disaster relief app. "
            "Keep only reliable, useful, evergreen guidance."
        ),
    )


def refresh_resource_cache(
    resources: list[Resource],
    cache_dir: Path,
    online_model: str,
    online_base_url: str,
    online_api_key: str | None,
) -> list[str]:
    statuses: list[str] = []
    validate_nemotron_model_name(online_model, "online cache refresh")
    for resource in resources:
        try:
            resource_text = fetch_resource_text(resource)
            summary_source = "raw-fallback"
            summary = best_summary_from_text(resource_text)
            if online_api_key:
                summary = summarize_resource_with_model(
                    resource,
                    resource_text,
                    online_model,
                    online_base_url,
                    online_api_key,
                )
                summary_source = f"online-model:{online_model}"
            payload = write_resource_cache(
                resource,
                cache_dir,
                summary,
                summary_source,
                source_text=resource_text,
            )
            statuses.append(
                f"cached {resource.name} at {payload['fetched_at']} via {payload['summary_source']}"
            )
        except Exception as exc:  # noqa: BLE001
            statuses.append(f"failed to cache {resource.name}: {exc}")
    return statuses


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="California earthquake and wildfire relief navigator."
    )
    parser.add_argument("--interactive", action="store_true", help="Collect inputs in a guided prompt.")
    parser.add_argument(
        "--profile-json",
        help="Path to a JSON file matching the UserProfile fields.",
    )
    parser.add_argument(
        "--state-code",
        default="CA",
        help="Two-letter state code for resource selection. Seeded with California today.",
    )
    parser.add_argument(
        "--zipcode",
        help="Optional ZIP code used to infer state selection when a local ZIP dataset is available.",
    )
    parser.add_argument(
        "--zip-state-map",
        help="Optional JSON path mapping 5-digit ZIP codes to two-letter state codes for 50-state expansion.",
    )
    parser.add_argument(
        "--use-online-nemotron",
        action="store_true",
        help="Call NVIDIA Nemotron Super online for the model-written response.",
    )
    parser.add_argument(
        "--use-local-nemotron",
        action="store_true",
        help="Call your downloaded local Nemotron model through LM Studio.",
    )
    parser.add_argument(
        "--online-model",
        default=DEFAULT_ONLINE_NEMOTRON_MODEL,
        help="NVIDIA Nemotron Super model name for online inference and cache summarization.",
    )
    parser.add_argument(
        "--online-api-base-url",
        default=DEFAULT_ONLINE_BASE_URL,
        help="NVIDIA OpenAI-compatible API base URL.",
    )
    parser.add_argument(
        "--online-api-key",
        default=os.getenv("RELIEFROUTE_ONLINE_API_KEY") or os.getenv("NVIDIA_API_KEY"),
        help="API key for NVIDIA-hosted Nemotron Super.",
    )
    parser.add_argument(
        "--local-model",
        default=DEFAULT_LOCAL_NEMOTRON_MODEL,
        help="Local Nemotron model name served by LM Studio.",
    )
    parser.add_argument(
        "--local-api-base-url",
        default=DEFAULT_LOCAL_BASE_URL,
        help="Local OpenAI-compatible API base URL. LM Studio usually uses http://127.0.0.1:1234/v1.",
    )
    parser.add_argument(
        "--local-api-key",
        default=os.getenv("RELIEFROUTE_LOCAL_API_KEY"),
        help="Optional API key for the local model server. LM Studio usually does not require one.",
    )
    parser.add_argument(
        "--cache-dir",
        default=str(default_cache_dir()),
        help="Directory used for cached website snapshots.",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Fetch fresh resource pages and summarize them with online Nemotron Super when available.",
    )
    parser.add_argument(
        "--show-cache-only",
        action="store_true",
        help="Print cached resource summaries for the selected plan and exit.",
    )
    parser.add_argument(
        "--build-rag-db",
        action="store_true",
        help="Build separate local SQLite RAG databases for federal and selected-state resources.",
    )
    parser.add_argument(
        "--rag-dir",
        default=str(default_rag_dir()),
        help="Directory containing local scoped SQLite RAG databases.",
    )
    parser.add_argument(
        "--rag-query",
        help="Optional query against the local RAG database.",
    )
    parser.add_argument(
        "--rag-scope",
        choices=("all", "federal", "state"),
        default="all",
        help="Which scoped RAG database to query.",
    )
    parser.add_argument(
        "--allow-ungrounded-model",
        action="store_true",
        help="Allow Nemotron use without scoped RAG evidence. Not recommended for disaster guidance.",
    )
    return parser.parse_args()


def load_profile_from_json(path: str) -> UserProfile:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    data.setdefault("state_code", "CA")
    return UserProfile(**data)


def example_profile() -> UserProfile:
    return UserProfile(
        state_code="CA",
        disaster_type="wildfire",
        county="Los Angeles County",
        situation="We evacuated after a fast-moving fire. The house may have major smoke and heat damage.",
        housing_damage="major damage",
        insurance_status="underinsured",
        household_size=4,
        has_medical_need=True,
        has_mobility_need=False,
        needs_shelter=True,
        needs_food=True,
        needs_documents=True,
        needs_pet_help=True,
        income_disrupted=True,
        safe_now=True,
    )


def main() -> None:
    args = parse_args()
    cache_dir = Path(args.cache_dir).expanduser()
    rag_dir = Path(args.rag_dir).expanduser()
    zip_state_map = load_zip_state_map(args.zip_state_map)
    inferred_state_code = infer_state_from_zipcode(args.zipcode, zip_state_map)
    selected_state_code = inferred_state_code or args.state_code.upper()

    if args.interactive:
        profile = collect_profile_from_prompt()
        if inferred_state_code:
            profile.state_code = inferred_state_code
        elif args.state_code:
            profile.state_code = args.state_code.upper()
    elif args.profile_json:
        profile = load_profile_from_json(args.profile_json)
        if inferred_state_code:
            profile.state_code = inferred_state_code
        elif args.state_code and args.state_code.upper() != "CA":
            profile.state_code = args.state_code.upper()
    else:
        profile = example_profile()
        profile.state_code = selected_state_code

    if profile.state_code != "CA":
        print(
            f"State selection is set to {profile.state_code}. "
            "The local database includes federal resources plus an official state emergency management link for all 50 states."
        )

    plan = build_plan(profile)
    state_resource_seed = available_resources_for_state(profile.state_code)
    if args.refresh_cache:
        validate_nemotron_model_name(args.online_model, "online cache refresh")
        print("=" * 72)
        print("Refreshing resource cache")
        print("=" * 72)
        for status in refresh_resource_cache(
            plan.resources,
            cache_dir,
            args.online_model,
            args.online_api_base_url.rstrip("/"),
            args.online_api_key,
        ):
            print(f"- {status}")
        print("")

    payload = plan_to_payload(profile, plan, cache_dir)
    grounded_payload, grounding_error = build_grounded_model_payload(
        profile,
        plan,
        cache_dir,
        rag_dir,
    )

    if args.show_cache_only:
        cached_resources = load_cached_resource_summaries(plan.resources, cache_dir)
        if not cached_resources:
            print("No cached resource snapshots found for this plan.")
            return
        print("=" * 72)
        print("Cached resource snapshots")
        print("=" * 72)
        for item in cached_resources:
            print(f"{item['name']} ({item['fetched_at']})")
            print(textwrap.fill(item["summary"], width=72))
            print("")
        return

    if args.build_rag_db:
        print("=" * 72)
        print("Building scoped local RAG databases")
        print("=" * 72)
        for status in build_scoped_rag_databases(profile.state_code, cache_dir, rag_dir):
            print(f"- {status}")
        rag_paths = rag_db_paths_for_state(profile.state_code, rag_dir)
        print(f"Federal RAG path: {rag_paths['federal']}")
        print(f"State RAG path: {rag_paths['state']}")
        print("")

    if args.rag_query:
        print("=" * 72)
        print("RAG query results")
        print("=" * 72)
        results = query_scoped_rag_databases(
            profile.state_code,
            rag_dir,
            args.rag_query,
            args.rag_scope,
        )
        if not results:
            print("No matching local RAG chunks found.")
        else:
            for result in results:
                preview = textwrap.shorten(result["content"], width=240, placeholder="...")
                print(
                    f"- {result['resource_name']} [{result['state_code']}] scope={result['scope']} "
                    f"score={result['score']} chunk={result['chunk_index']} ({result['url']})"
                )
                print(f"  {preview}")
        print("")

    ran_auxiliary_command = args.build_rag_db or args.rag_query or args.show_cache_only
    if ran_auxiliary_command and not (args.use_online_nemotron or args.use_local_nemotron):
        return

    if args.use_online_nemotron:
        validate_nemotron_model_name(args.online_model, "online inference")
    if args.use_local_nemotron:
        validate_local_nemotron_config(args.local_model, args.local_api_base_url)

    print("=" * 72)
    print("ReliefRoute")
    print("=" * 72)
    print(render_local_plan(plan, cache_dir))

    if args.use_online_nemotron:
        if grounding_error and not args.allow_ungrounded_model:
            print("\n" + "=" * 72)
            print("Nemotron skipped")
            print("=" * 72)
            print(grounding_error)
            print("Using the deterministic local plan above to avoid ungrounded guidance.")
            return
        print("\n" + "=" * 72)
        print(f"Online Nemotron Super Output ({args.online_model})")
        print("=" * 72)
        model_output = call_model(
            grounded_payload or payload,
            args.online_model,
            args.online_api_base_url.rstrip("/"),
            args.online_api_key,
        )
        print(textwrap.dedent(model_output).strip())
    elif args.use_local_nemotron:
        if grounding_error and not args.allow_ungrounded_model:
            print("\n" + "=" * 72)
            print("Nemotron skipped")
            print("=" * 72)
            print(grounding_error)
            print("Using the deterministic local plan above to avoid ungrounded guidance.")
            return
        print("\n" + "=" * 72)
        print(f"Local Nemotron Output ({args.local_model})")
        print("=" * 72)
        model_output = call_model(
            grounded_payload or payload,
            args.local_model,
            args.local_api_base_url.rstrip("/"),
            args.local_api_key,
        )
        print(textwrap.dedent(model_output).strip())
    else:
        print(
            "\nTip: use --use-online-nemotron for NVIDIA Nemotron Super, "
            "or --use-local-nemotron for your downloaded local Nemotron in LM Studio."
        )


if __name__ == "__main__":
    main()
