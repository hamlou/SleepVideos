import re
import time
from dataclasses import dataclass
from typing import Callable

import requests

from .config import Settings
from .log import log

TIMEOUT = 300
DEAD_CODES = {401, 402, 403, 404}


class AllProvidersFailed(RuntimeError):
    pass


@dataclass
class Provider:
    name: str
    call: Callable[[str, bool], str | None]
    dead: bool = False
    min_gap: float = 0.0
    last: float = 0.0


def _openai_compat(url: str, key: str, model: str, extra: dict | None = None, max_tokens: int = 8000):
    def call(prompt: str, json_mode: bool) -> str | None:
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", **(extra or {})}
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.8,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
        if r.status_code == 400 and json_mode:
            body.pop("response_format")
            r = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
        _raise(r)
        if "json" not in r.headers.get("content-type", ""):
            raise HTTPFail(404, f"non-JSON reply ({r.headers.get('content-type')}): {r.text[:80]}")
        return r.json()["choices"][0]["message"]["content"]

    return call


class HTTPFail(Exception):
    def __init__(self, code: int, body: str):
        super().__init__(f"HTTP {code}: {body[:200]}")
        self.code = code


def _raise(r: requests.Response) -> None:
    if r.status_code == 402 and ("FREE_LIMIT" in r.text or "Retry after" in r.text):
        raise HTTPFail(429, r.text)
    if r.status_code != 200:
        raise HTTPFail(r.status_code, r.text)


def _gemini_models(key: str) -> list[str]:
    r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}&pageSize=200", timeout=30)
    _raise(r)
    names = [
        m["name"].removeprefix("models/")
        for m in r.json().get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]
    def rank(n: str) -> tuple:
        bad = any(t in n for t in ("image", "tts", "audio", "live", "embedding", "thinking-exp", "lite"))
        ver = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)", n)[:1]] or [0.0]
        return (bad, "flash" not in n, "preview" in n or "exp" in n, -ver[0])
    return sorted(names, key=rank)[:3]


def _gemini(key: str, model: str):
    def call(prompt: str, json_mode: bool) -> str | None:
        cfg = {"temperature": 0.8, "maxOutputTokens": 8192}
        if json_mode:
            cfg["responseMimeType"] = "application/json"
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
            json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": cfg},
            timeout=TIMEOUT,
        )
        _raise(r)
        parts = r.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)

    return call


def _cohere(key: str):
    def call(prompt: str, json_mode: bool) -> str | None:
        body = {"model": "command-a-03-2025", "messages": [{"role": "user", "content": prompt}], "temperature": 0.8}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = requests.post(
            "https://api.cohere.com/v2/chat",
            headers={"Authorization": f"Bearer {key}"},
            json=body,
            timeout=TIMEOUT,
        )
        _raise(r)
        return "".join(c.get("text", "") for c in r.json()["message"]["content"])

    return call


def build_providers(s: Settings) -> list[Provider]:
    p: list[Provider] = []
    if s.github_token:
        gh = "https://models.github.ai/inference/chat/completions"
        hdr = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        for m in ("openai/gpt-4.1-mini", "openai/gpt-4.1", "meta/Llama-3.3-70B-Instruct"):
            p.append(Provider(f"github:{m}", _openai_compat(gh, s.github_token, m, hdr)))
    for k in s.gemini:
        try:
            for m in _gemini_models(k):
                p.append(Provider(f"gemini:{m}", _gemini(k, m)))
        except Exception as e:
            log(f"gemini key skipped ({e})")
    for k in s.groq:
        for m in ("llama-3.3-70b-versatile", "openai/gpt-oss-120b"):
            p.append(Provider(f"groq:{m}", _openai_compat("https://api.groq.com/openai/v1/chat/completions", k, m)))
    for k in s.cerebras:
        for m in ("gpt-oss-120b", "llama-3.3-70b"):
            p.append(Provider(f"cerebras:{m}", _openai_compat("https://api.cerebras.ai/v1/chat/completions", k, m)))
    for k in s.mistral:
        p.append(Provider("mistral", _openai_compat("https://api.mistral.ai/v1/chat/completions", k, "mistral-small-latest")))
    for k in s.openrouter:
        p.append(Provider("openrouter", _openai_compat("https://openrouter.ai/api/v1/chat/completions", k, "openrouter/free")))
    for k in s.cohere:
        p.append(Provider("cohere", _cohere(k)))
    p.append(Provider(
        "pollinations",
        min_gap=0.0 if s.pollinations_token else 47.0,
        call=
        _openai_compat(
            "https://text.pollinations.ai/openai",
            s.pollinations_token or "anon",
            "openai",
        ),
    ))
    return p


_THINK = re.compile(r"<think>[\s\S]*?</think>", re.I)


class LLM:
    def __init__(self, s: Settings):
        self.providers = build_providers(s)
        self.sticky = 0
        log("LLM chain: " + " → ".join(x.name for x in self.providers))

    def ask(self, prompt: str, json_mode: bool = False, validate: Callable[[str], bool] | None = None) -> str:
        n = len(self.providers)
        for attempt in range(2):
            for off in range(n):
                i = (self.sticky + off) % n
                pv = self.providers[i]
                if pv.dead:
                    continue
                wait = pv.min_gap - (time.time() - pv.last)
                if wait > 0:
                    time.sleep(wait)
                try:
                    pv.last = time.time()
                    out = pv.call(prompt, json_mode)
                except HTTPFail as e:
                    if e.code in DEAD_CODES:
                        pv.dead = True
                        log(f"  ✗ {pv.name} disabled ({e})")
                    else:
                        log(f"  ✗ {pv.name} {e}")
                        if e.code == 429:
                            time.sleep(5)
                    continue
                except Exception as e:
                    log(f"  ✗ {pv.name} {type(e).__name__}: {str(e)[:160]}")
                    continue
                out = _THINK.sub("", out or "").strip()
                if len(out) < 40 or (validate and not validate(out)):
                    log(f"  ✗ {pv.name} output rejected ({len(out)} chars): {out[-160:]!r}")
                    continue
                self.sticky = i
                return out
            log(f"  all providers failed, round {attempt + 1}; cooling down 60s")
            time.sleep(60)
        raise AllProvidersFailed("Every LLM provider failed. See log above for per-provider reasons.")
