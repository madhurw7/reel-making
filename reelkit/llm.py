"""Minimal Ollama client (stdlib only): structured chat, model unload, memory checks."""
from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.error
import urllib.request


class LLMError(RuntimeError):
    pass


def _post(url: str, payload: dict, timeout: float = 900) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise LLMError(f"Ollama {e.code}: {e.read().decode(errors='replace')[:400]}") from e
    except TimeoutError as e:
        raise LLMError(f"Ollama did not answer within {timeout:.0f}s (model too slow for this machine right now?)") from e
    except urllib.error.URLError as e:
        if isinstance(e.reason, TimeoutError):
            raise LLMError(f"Ollama did not answer within {timeout:.0f}s") from e
        raise LLMError(f"cannot reach Ollama at {url} ({e.reason}). Start it with `ollama serve` or open the app.") from e


def _json_block(text: str) -> str:
    """The outermost {...} in a reply (models without schema support may wrap JSON in fences or prose)."""
    a, b = text.find("{"), text.rfind("}")
    return text[a: b + 1] if a != -1 and b > a else text


def _loads(text: str):
    """Parse a model's JSON reply, forgiving the usual slips of unconstrained models (fences, trailing commas)."""
    block = _json_block(text)
    try:
        return json.loads(block)
    except json.JSONDecodeError:
        return json.loads(re.sub(r",\s*([}\]])", r"\1", block))


def chat_json(cfg: dict, model: str, system: str, user: str, schema: dict, temperature: float | None = None,
              max_tokens: int = 2500):
    """One chat turn constrained to `schema`. Returns (parsed_json, stats).
    `max_tokens` caps the reply: without it a small model that starts repeating itself can generate for minutes.
    A reply that is cut off or is not valid JSON is retried (with the problem named) before giving up."""
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "format": schema,
        "stream": False,
        "keep_alive": "5m",
        "options": {"temperature": cfg["temperature"] if temperature is None else temperature,
                    "num_ctx": cfg.get("num_ctx", 8192), "num_predict": max_tokens},
    }
    if not cfg.get("think", False):
        payload["think"] = False
    url = cfg["ollama_url"].rstrip("/") + "/api/chat"
    t0 = time.perf_counter()
    out, data, problem = None, None, ""
    for _ in range(5):
        try:
            out = _post(url, payload)
        except LLMError as e:
            msg = str(e).lower()
            if "think" in payload and "think" in msg:               # model has no thinking mode: drop the flag
                payload.pop("think")
            elif "format" in payload and "structured output" in msg:
                # Some builds (e.g. gemma4 on Ollama's MLX engine) cannot constrain output to a schema.
                # Put the schema in the prompt instead; the caller validates the result.
                payload.pop("format")
                payload["messages"][0]["content"] = (
                    system + "\n\nReturn ONLY one JSON object, no markdown fences and no commentary. "
                    "It must match this JSON Schema:\n" + json.dumps(schema))
            else:
                raise
            continue
        text = out.get("message", {}).get("content", "")
        if out.get("done_reason") == "length":
            problem = f"the reply was cut off at {max_tokens} tokens: it is too long or repeats itself"
        else:
            try:
                data = _loads(text)
                break
            except json.JSONDecodeError as e:
                problem = f"the reply was not valid JSON ({e.msg} at character {e.pos})"
        if len(payload["messages"]) > 2:                            # one corrective retry, then give up
            break
        payload["messages"] += [
            {"role": "assistant", "content": text[:1500]},
            {"role": "user", "content": f"That did not work: {problem}. Answer again with ONE complete, valid JSON "
                                        "object and nothing else. Be shorter. Inside strings, write single quotes "
                                        "instead of double quotes. Never repeat an item."}]
    if data is None:
        raise LLMError(f"{model}: {problem or 'could not get a response'}")
    wall = time.perf_counter() - t0
    n, dur = out.get("eval_count", 0), out.get("eval_duration", 0) / 1e9
    return data, {"wall_s": round(wall, 1), "out_tokens": n, "tokens_per_s": round(n / dur, 1) if dur else 0.0,
                  "load_s": round(out.get("load_duration", 0) / 1e9, 1)}


def unload(cfg: dict, model: str | None = None) -> None:
    """Free the model's memory (the voice stage needs it). Unloads everything Ollama has loaded if model is None."""
    base = cfg["ollama_url"].rstrip("/")
    try:
        names = [model] if model else [m["name"] for m in
                                       json.loads(urllib.request.urlopen(base + "/api/ps", timeout=5).read())["models"]]
        for name in names:
            _post(base + "/api/generate", {"model": name, "keep_alive": 0}, timeout=30)
    except Exception:
        pass                                                        # Ollama not running = nothing loaded


def swap_used_mb() -> float:
    try:
        out = subprocess.run(["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True).stdout
        return float(out.split("used =")[1].split("M")[0])
    except Exception:
        return 0.0
