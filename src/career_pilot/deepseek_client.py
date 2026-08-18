from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict

from .config import load_env_file


class DeepSeekError(RuntimeError):
    """A safe, user-facing DeepSeek API error."""


@dataclass(frozen=True)
class DeepSeekSettings:
    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-pro"
    timeout_seconds: int = 60

    @classmethod
    def from_env(cls) -> "DeepSeekSettings":
        load_env_file()
        api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise DeepSeekError("尚未配置 DEEPSEEK_API_KEY，请在本地 .env 文件中填写，勿发到聊天中。")
        return cls(
            api_key=api_key,
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip(),
            model=os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro").strip(),
        )


def build_payload(model: str, system_prompt: str, user_prompt: str) -> Dict[str, object]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "stream": False,
        "max_tokens": 2500,
    }


class DeepSeekClient:
    def __init__(self, settings: DeepSeekSettings):
        self.settings = settings

    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, object]:
        endpoint = self.settings.base_url.rstrip("/") + "/chat/completions"
        payload = build_payload(self.settings.model, system_prompt, user_prompt)
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            safe_body = error.read().decode("utf-8", errors="replace")[:500]
            raise DeepSeekError(f"DeepSeek API 返回 HTTP {error.code}：{safe_body}") from error
        except urllib.error.URLError as error:
            raise DeepSeekError(f"无法连接 DeepSeek API：{error.reason}") from error
        except TimeoutError as error:
            raise DeepSeekError("DeepSeek API 请求超时，请稍后重试。") from error

        try:
            envelope = json.loads(body)
            content = envelope["choices"][0]["message"]["content"]
            result = json.loads(content)
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
            raise DeepSeekError("DeepSeek 返回了无法解析的 JSON 结果。") from error
        if not isinstance(result, dict):
            raise DeepSeekError("DeepSeek 返回结果不是 JSON 对象。")
        return result
