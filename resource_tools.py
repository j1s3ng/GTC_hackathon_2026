from __future__ import annotations

import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib import error, request


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "cache"


class HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._ignore_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._ignore_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._ignore_depth:
            self._ignore_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignore_depth:
            return
        stripped = data.strip()
        if stripped:
            self._parts.append(stripped)

    def get_text(self) -> str:
        return " ".join(self._parts)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_resources(state_code: str) -> list[dict[str, Any]]:
    federal = load_json(DATA_DIR / "federal_resources.json")
    state_path = DATA_DIR / "states" / f"{state_code.lower()}.json"
    state_resources = load_json(state_path) if state_path.exists() else []
    resources: list[dict[str, Any]] = []
    for item in federal:
        resources.append({**item, "jurisdiction": "federal", "state_code": "US"})
    for item in state_resources:
        resources.append({**item, "jurisdiction": "state", "state_code": state_code.upper()})
    return resources


def slugify_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def cache_path_for_url(url: str, cache_dir: Path | None = None) -> Path:
    directory = cache_dir or CACHE_DIR
    return directory / f"{slugify_url(url)}.json"


def clean_text(raw_html: str) -> str:
    extractor = HTMLTextExtractor()
    extractor.feed(raw_html)
    text = extractor.get_text()
    for marker in (
        "Skip to main content",
        "An official website of the United States government",
        "Cookie Policy",
    ):
        text = text.replace(marker, " ")
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_resource_text(url: str, timeout: int = 20) -> str:
    req = request.Request(
        url,
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


def summarize_text(text: str, limit: int = 1500) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    kept: list[str] = []
    total = 0
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 30:
            continue
        kept.append(sentence)
        total += len(sentence) + 1
        if total >= limit:
            break
    return (" ".join(kept) or text)[:limit]


def write_cache(resource: dict[str, Any], text: str, cache_dir: Path | None = None, source: str = "network") -> dict[str, Any]:
    directory = cache_dir or CACHE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "name": resource.get("name"),
        "url": resource.get("url"),
        "jurisdiction": resource.get("jurisdiction"),
        "state_code": resource.get("state_code"),
        "summary": summarize_text(text),
        "source_text": text[:12000],
        "summary_source": source,
    }
    path = cache_path_for_url(resource["url"], directory)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def read_cache(resource: dict[str, Any], cache_dir: Path | None = None) -> dict[str, Any] | None:
    path = cache_path_for_url(resource["url"], cache_dir)
    if not path.exists():
        return None
    return load_json(path)


def refresh_resources(state_code: str, cache_dir: Path | None = None) -> list[str]:
    statuses: list[str] = []
    for resource in load_resources(state_code):
        try:
            text = fetch_resource_text(resource["url"])
            write_cache(resource, text, cache_dir=cache_dir, source="network")
            statuses.append(f"cached {resource['name']}")
        except Exception as exc:  # noqa: BLE001
            cached = read_cache(resource, cache_dir=cache_dir)
            if cached:
                statuses.append(f"offline fallback for {resource['name']}: using cache")
            else:
                statuses.append(f"failed {resource['name']}: {exc}")
    return statuses


def keyword_score(query: str, text: str) -> int:
    terms = [token for token in re.findall(r"[a-z0-9]+", query.lower()) if len(token) > 2]
    haystack = text.lower()
    return sum(haystack.count(term) for term in terms)


def retrieve_resource_evidence(
    query: str,
    state_code: str,
    selected_resources: list[dict[str, Any]] | None = None,
    cache_dir: Path | None = None,
    refresh: bool = False,
    limit: int = 5,
) -> dict[str, Any]:
    resources = selected_resources or load_resources(state_code)
    results: list[dict[str, Any]] = []
    for resource in resources:
        payload = None
        source_mode = "cache"
        if refresh:
            try:
                text = fetch_resource_text(resource["url"])
                payload = write_cache(resource, text, cache_dir=cache_dir, source="network")
                source_mode = "network"
            except Exception:
                payload = read_cache(resource, cache_dir=cache_dir)
                source_mode = "cache"
        else:
            payload = read_cache(resource, cache_dir=cache_dir)
        if not payload:
            payload = {
                "name": resource.get("name"),
                "url": resource.get("url"),
                "summary": resource.get("description", ""),
                "source_text": " ".join(resource.get("required_documents", []) + resource.get("required_information", [])),
                "summary_source": "metadata",
            }
            source_mode = "metadata"
        searchable = " ".join(
            [
                resource.get("name", ""),
                resource.get("category", ""),
                resource.get("description", ""),
                payload.get("summary", ""),
                payload.get("source_text", ""),
                " ".join(resource.get("required_documents", [])),
                " ".join(resource.get("required_information", [])),
            ]
        )
        score = keyword_score(query, searchable)
        if score <= 0 and limit < len(resources):
            continue
        snippet = payload.get("summary") or summarize_text(payload.get("source_text", ""), limit=500)
        results.append(
            {
                "name": resource.get("name"),
                "url": resource.get("url"),
                "jurisdiction": resource.get("jurisdiction"),
                "state_code": resource.get("state_code"),
                "score": score,
                "source_mode": source_mode,
                "snippet": snippet[:500],
                "required_documents": resource.get("required_documents", []),
                "required_information": resource.get("required_information", []),
            }
        )
    results.sort(key=lambda item: (item["score"], item["source_mode"] == "network"), reverse=True)
    return {
        "query": query,
        "state_code": state_code.upper(),
        "results": results[:limit],
    }


def build_tool_block(tool_result: dict[str, Any]) -> str:
    lines = [
        "Resource lookup tool results:",
        f"State: {tool_result['state_code']}",
        f"Query: {tool_result['query']}",
    ]
    for item in tool_result["results"]:
        lines.append(
            f"- {item['name']} [{item['jurisdiction']}] via {item['source_mode']}: {item['snippet']}"
        )
        if item["required_information"]:
            lines.append(f"  required information: {', '.join(item['required_information'])}")
        if item["required_documents"]:
            lines.append(f"  required documents: {', '.join(item['required_documents'])}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh and query ReliefRoute resource cache.")
    parser.add_argument("--state-code", default="CA")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--query")
    args = parser.parse_args()

    if args.refresh:
        for status in refresh_resources(args.state_code):
            print(status)

    if args.query:
        result = retrieve_resource_evidence(args.query, args.state_code, refresh=args.refresh)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
