from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path


class ModelClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class ModelResponse:
    content: str
    model: str
    latency_ms: int
    usage: ModelUsage

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["usage"] = asdict(self.usage)
        return result


def load_env_file(path: Path) -> None:
    """Load a local env file without printing or returning secret values."""
    if not path.exists():
        raise ModelClientError(f"Environment file not found: {path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class OpenAICompatibleClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: int = 120,
    ) -> None:
        if not api_key or len(api_key) < 20:
            raise ModelClientError("LLM API key is missing or invalid")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_environment(cls) -> "OpenAICompatibleClient":
        return cls(
            api_key=os.environ.get("LLM_API_KEY", ""),
            base_url=os.environ.get(
                "LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
            ),
            model=os.environ.get("LLM_MODEL", "qwen3.7-plus"),
            timeout_seconds=int(os.environ.get("LLM_TIMEOUT", "120")),
        )

    def chat(self, system: str, user: str, max_tokens: int = 1200) -> ModelResponse:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "max_tokens": max_tokens,
            "stream": False,
            "enable_thinking": False,
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise ModelClientError(f"Model request failed with HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ModelClientError(f"Model request failed: {exc.reason}") from exc
        latency_ms = round((time.perf_counter() - started) * 1000)
        data = json.loads(raw)
        usage = data.get("usage", {})
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelClientError("Model response did not contain message content") from exc
        return ModelResponse(
            content=content,
            model=data.get("model", self.model),
            latency_ms=latency_ms,
            usage=ModelUsage(
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
                total_tokens=int(usage.get("total_tokens", 0)),
            ),
        )


def parse_json_object(content: str) -> dict[str, object]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ModelClientError("Model output is not a JSON object") from exc
    if not isinstance(value, dict):
        raise ModelClientError("Model output must be a JSON object")
    return value
