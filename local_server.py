from __future__ import annotations

import json
import os
import re
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socket import timeout as SocketTimeout
from typing import Any
from urllib import error, request


ROOT = Path(__file__).resolve().parent
ONLINE_CHAT_URL = os.getenv("ONLINE_CHAT_URL", "https://api-inference.bitdeer.ai/v1/chat/completions")
ONLINE_MODEL = os.getenv("ONLINE_MODEL", os.getenv("HF_MODEL", "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B"))
LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "nemotron")
SYSTEM_PROMPT = """You are ReliefRoute, a disaster recovery assistant.

Use only the provided disaster profile, structured plan, and resource list.
Do not invent eligibility, deadlines, phone numbers, or qualification decisions.
Say a service may be relevant rather than guaranteed.
Keep the answer practical, specific, and concise.
"""


def load_env_file() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def json_response(handler: SimpleHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int = 30) -> dict[str, Any]:
    req = request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
        raise RuntimeError(f"HTTP {exc.code}: {details or exc.reason}") from exc


def get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 10) -> dict[str, Any]:
    req = request.Request(url=url, headers=headers or {}, method="GET")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
        raise RuntimeError(f"HTTP {exc.code}: {details or exc.reason}") from exc


def resolve_lmstudio_candidates() -> list[str]:
    configured = os.getenv("LM_STUDIO_MODEL", LM_STUDIO_MODEL)
    base_url = os.getenv("LM_STUDIO_BASE_URL", LM_STUDIO_BASE_URL).rstrip("/")

    data = get_json(f"{base_url}/models")
    model_ids = [item.get("id", "") for item in data.get("data", []) if isinstance(item, dict)]
    model_ids = [model_id for model_id in model_ids if model_id]

    candidates: list[str] = []
    if configured and "nemotron" in configured.lower() and configured in model_ids:
        candidates.append(configured)

    nemotron_matches = [model_id for model_id in model_ids if "nemotron" in model_id.lower()]
    for match in nemotron_matches:
        if match not in candidates:
            candidates.append(match)

    if candidates:
        return candidates

    if configured and "nemotron" in configured.lower() and configured not in model_ids:
        raise RuntimeError(
            f"Configured LM_STUDIO_MODEL '{configured}' not found. Available models: {', '.join(model_ids) if model_ids else 'none'}."
        )

    raise RuntimeError(
        f"No Nemotron model is available in LM Studio. Available models: {', '.join(model_ids) if model_ids else 'none'}."
    )


def build_model_messages(user_prompt: str, profile: dict[str, Any], plan: dict[str, Any], recent_history: list[dict[str, str]]) -> list[dict[str, str]]:
    history_slice = recent_history[-6:] if recent_history else []
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "User prompt:\n"
                f"{user_prompt}\n\n"
                "Recent chat history:\n"
                f"{json.dumps(history_slice, indent=2)}\n\n"
                "Inferred disaster profile:\n"
                f"{json.dumps(profile, indent=2)}\n\n"
                "Structured plan and resources:\n"
                f"{json.dumps(plan, indent=2)}"
            ),
        },
    ]


def sanitize_model_text(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()


def call_online(messages: list[dict[str, str]]) -> tuple[str, str]:
    token = (
        os.getenv("ONLINE_API_KEY")
        or os.getenv("BITDEER_API_KEY")
        or os.getenv("HF_TOKEN")
        or os.getenv("HUGGINGFACE_TOKEN")
    )
    if not token:
        raise RuntimeError("ONLINE_API_KEY is not set.")

    body = {
        "model": os.getenv("ONLINE_MODEL", ONLINE_MODEL),
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 600,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": os.getenv("ONLINE_USER_AGENT", "curl/8.7.1"),
    }
    data = post_json(os.getenv("ONLINE_CHAT_URL", ONLINE_CHAT_URL), body, headers)
    return sanitize_model_text(data["choices"][0]["message"]["content"]), "online"


def call_lmstudio(messages: list[dict[str, str]]) -> tuple[str, str]:
    candidate_models = resolve_lmstudio_candidates()
    headers = {"Content-Type": "application/json"}
    base_url = os.getenv("LM_STUDIO_BASE_URL", LM_STUDIO_BASE_URL).rstrip("/")
    errors_by_model: list[str] = []

    for model_name in candidate_models:
        body = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.2,
            "stream": False,
        }
        try:
            data = post_json(f"{base_url}/chat/completions", body, headers)
            return sanitize_model_text(data["choices"][0]["message"]["content"]), "lmstudio"
        except RuntimeError as exc:
            errors_by_model.append(f"{model_name}: {exc}")

    raise RuntimeError(
        "Nemotron models were found in LM Studio but could not be loaded. "
        f"Attempts: {' | '.join(errors_by_model)}"
    )


def generate_response(
    user_prompt: str,
    profile: dict[str, Any],
    plan: dict[str, Any],
    history: list[dict[str, str]],
    backend_mode: str = "auto",
    prefer_local: bool = False,
) -> tuple[str, str]:
    messages = build_model_messages(user_prompt, profile, plan, history)
    mode = (backend_mode or "").strip().lower()
    if mode == "local" or prefer_local:
        return call_lmstudio(messages)
    if mode == "online":
        return call_online(messages)

    try:
        return call_online(messages)
    except (RuntimeError, error.URLError, error.HTTPError, KeyError, IndexError, TypeError, SocketTimeout) as online_exc:
        try:
            return call_lmstudio(messages)
        except (RuntimeError, error.URLError, error.HTTPError, KeyError, IndexError, TypeError, SocketTimeout) as local_exc:
            raise RuntimeError(f"Online backend failed: {online_exc} | Local fallback failed: {local_exc}") from local_exc


class ReliefRouteHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/health":
            json_response(
                self,
                HTTPStatus.OK,
                {
                    "ok": True,
                    "online_chat_url": os.getenv("ONLINE_CHAT_URL", ONLINE_CHAT_URL),
                    "online_model": os.getenv("ONLINE_MODEL", ONLINE_MODEL),
                    "online_auth_configured": bool(
                        os.getenv("ONLINE_API_KEY")
                        or os.getenv("BITDEER_API_KEY")
                        or os.getenv("HF_TOKEN")
                        or os.getenv("HUGGINGFACE_TOKEN")
                    ),
                    "lmstudio_base_url": os.getenv("LM_STUDIO_BASE_URL", LM_STUDIO_BASE_URL),
                },
            )
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/chat":
            json_response(self, HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON body"})
            return

        try:
            answer, backend = generate_response(
                payload.get("prompt", ""),
                payload.get("profile", {}),
                payload.get("plan", {}),
                payload.get("history", []),
                str(payload.get("backend_mode", "auto")),
                bool(payload.get("prefer_local", False)),
            )
        except Exception as exc:  # noqa: BLE001
            json_response(
                self,
                HTTPStatus.BAD_GATEWAY,
                {"error": "Model backend unavailable", "details": str(exc)},
            )
            return

        json_response(self, HTTPStatus.OK, {"answer": answer, "backend": backend})


def main() -> None:
    load_env_file()
    host = os.getenv("RELIEFROUTE_HOST", "127.0.0.1")
    port = int(os.getenv("RELIEFROUTE_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), ReliefRouteHandler)
    print(f"Serving ReliefRoute on http://{host}:{port}/webui/")
    server.serve_forever()


if __name__ == "__main__":
    main()
