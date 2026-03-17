from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socket import timeout as SocketTimeout
from typing import Any
from urllib import error, request


ROOT = Path(__file__).resolve().parent
HF_CHAT_URL = "https://router.huggingface.co/v1/chat/completions"
HF_MODEL = os.getenv("HF_MODEL", "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16")
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
    with request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


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


def call_huggingface(messages: list[dict[str, str]]) -> tuple[str, str]:
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN is not set.")

    body = {
        "model": os.getenv("HF_MODEL", HF_MODEL),
        "messages": messages,
        "temperature": 0.2,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data = post_json(HF_CHAT_URL, body, headers)
    return data["choices"][0]["message"]["content"].strip(), "huggingface"


def call_lmstudio(messages: list[dict[str, str]]) -> tuple[str, str]:
    body = {
        "model": os.getenv("LM_STUDIO_MODEL", LM_STUDIO_MODEL),
        "messages": messages,
        "temperature": 0.2,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    data = post_json(f"{os.getenv('LM_STUDIO_BASE_URL', LM_STUDIO_BASE_URL).rstrip('/')}/chat/completions", body, headers)
    return data["choices"][0]["message"]["content"].strip(), "lmstudio"


def generate_response(user_prompt: str, profile: dict[str, Any], plan: dict[str, Any], history: list[dict[str, str]]) -> tuple[str, str]:
    messages = build_model_messages(user_prompt, profile, plan, history)
    try:
        return call_huggingface(messages)
    except (RuntimeError, error.URLError, error.HTTPError, KeyError, IndexError, TypeError, SocketTimeout):
        return call_lmstudio(messages)


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
                    "huggingface_model": os.getenv("HF_MODEL", HF_MODEL),
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
