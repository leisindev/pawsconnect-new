"""Model access layer for PawsConnect.

Every model call goes through `chat()`. In LIVE mode it calls the OpenAI API
(key read from the OPENAI_API_KEY environment variable, never hardcoded) and
records the response in cache/responses.json. In DEMO (cached) mode it replays
the recorded response for the same cache key, so the whole feature pipeline -
parsing, voting, judging, flagging - runs identically without an API key.
"""
import base64
import json
import os
import time
from pathlib import Path

MODEL = os.getenv("PAWS_MODEL", "gpt-4o-mini")
CACHE_PATH = Path(__file__).parent / "cache" / "responses.json"


class CacheMiss(Exception):
    """Raised in demo mode when an input has no recorded response."""


def _load_cache() -> dict:
    """Read the cache. If the file is damaged (e.g. two writers at once), keep the first
    valid JSON object, back up the damaged file, and carry on instead of crashing."""
    if not CACHE_PATH.exists():
        return {}
    text = CACHE_PATH.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            data, _ = json.JSONDecoder().raw_decode(text.lstrip())
        except json.JSONDecodeError:
            data = {}
        CACHE_PATH.with_suffix(".corrupt.bak").write_text(text, encoding="utf-8")
        _save_cache(data)
        print(f"[llm] cache file was damaged; recovered {len(data)} entries (backup: responses.corrupt.bak)")
        return data


def _save_cache(cache: dict) -> None:
    """Atomic write: write a temp file, then swap it in, so a crash or a second
    process can never leave half-written JSON behind."""
    CACHE_PATH.parent.mkdir(exist_ok=True)
    tmp = CACHE_PATH.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, CACHE_PATH)


def cache_info() -> dict:
    """How many cached responses exist and where they came from (live vs seed)."""
    cache = _load_cache()
    sources = {}
    for v in cache.values():
        sources[v.get("source", "live")] = sources.get(v.get("source", "live"), 0) + 1
    return {"count": len(cache), "sources": sources}


def has_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def image_part(path: str) -> dict:
    """Encode an image file as an OpenAI vision content part (base64 data URL)."""
    data = Path(path).read_bytes()
    ext = Path(path).suffix.lower().lstrip(".")
    mime = "image/png" if ext == "png" else "image/jpeg"
    b64 = base64.b64encode(data).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "low"}}


def chat(messages, cache_key: str, live: bool, temperature: float = 0.0,
         json_mode: bool = True, max_tokens: int = 900) -> str:
    """Return the model's text reply for `messages`.

    cache_key identifies this exact call (feature : input id : step) so that
    demo mode can replay it.
    """
    if not live:
        cache = _load_cache()
        if cache_key not in cache:
            raise CacheMiss(cache_key)
        return cache[cache_key]["content"]

    from openai import OpenAI  # imported lazily so demo mode needs no key

    client = OpenAI()  # reads OPENAI_API_KEY from the environment
    kwargs = dict(model=MODEL, messages=messages, temperature=temperature, max_tokens=max_tokens)
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    content = resp.choices[0].message.content

    cache = _load_cache()
    cache[cache_key] = {
        "content": content,
        "model": MODEL,
        "temperature": temperature,
        "source": "live",
        "recorded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_cache(cache)
    return content


def parse_json(text: str) -> dict:
    """Parse a JSON reply, tolerating ```json fences."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{"):]
    return json.loads(t[t.find("{"): t.rfind("}") + 1])
