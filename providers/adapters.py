import os
from typing import Optional

import requests
from dotenv import load_dotenv
from google import genai
from mistralai.client import Mistral

from reliability.manager import RELIABILITY_MANAGER

load_dotenv()


class ProviderAdapterError(RuntimeError):
    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value or not value.strip():
        raise ProviderAdapterError(f"Missing required environment variable: {name}")
    return value.strip()


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------
# Gemini quota is project-level, so each configured project/key is carried as
# a separate routing capacity.  The env names are intentionally explicit.

GEMINI_KEY_ENV = {
    1: "GEMINI_API_KEY",
    2: "GEMINI_API_KEY_2",
    3: "GEMINI_API_KEY_3",
    4: "GEMINI_API_KEY_4",
}


def _gemini_env_name(key_number: int) -> str:
    try:
        return GEMINI_KEY_ENV[int(key_number)]
    except (KeyError, TypeError, ValueError) as exc:
        raise ProviderAdapterError(
            f"Unsupported Gemini key number: {key_number}. Expected 1-4."
        ) from exc


def call_gemini(
    prompt: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> str:
    """Call Gemini using a supplied key, or GEMINI_API_KEY (key 1)."""
    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    api_key = api_key or _require_env("GEMINI_API_KEY")
    model = model or _env("GEMINI_MODEL", "gemini-3.5-flash-lite")

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model, contents=prompt)
    except Exception as exc:
        raise ProviderAdapterError(
            f"Gemini API error (model '{model}'): {exc}"
        ) from exc

    content = getattr(response, "text", None)
    if content is None or not str(content).strip():
        raise ProviderAdapterError(f"Gemini returned empty content: {response}")

    return str(content)


def call_gemini_with_key(
    prompt: str,
    key_number: int,
    model: Optional[str] = None,
) -> str:
    """Call Gemini with a specific configured project/API key (1-4)."""
    env_name = _gemini_env_name(key_number)
    api_key = _require_env(env_name)
    return call_gemini(prompt=prompt, model=model, api_key=api_key)


# ---------------------------------------------------------------------------
# Mistral
# ---------------------------------------------------------------------------


def call_mistral(
    prompt: str,
    model: Optional[str] = None,
) -> str:
    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    api_key = _require_env("MISTRAL_API_KEY")
    model = model or _env("MISTRAL_MODEL", "ministral-3b-2512")

    try:
        client = Mistral(api_key=api_key)
        response = client.chat.complete(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        raise ProviderAdapterError(
            f"Mistral API error (model '{model}'): {exc}"
        ) from exc

    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, TypeError) as exc:
        raise ProviderAdapterError(f"Unexpected Mistral response: {response}") from exc

    if content is None or not str(content).strip():
        raise ProviderAdapterError(f"Mistral returned empty content: {response}")

    return str(content)


# ---------------------------------------------------------------------------
# Groq
# ---------------------------------------------------------------------------

GROQ_KEY_ENV = {
    1: "GROQ_API_KEY",
    2: "GROQ_API_KEY_1",
}


def _groq_env_name(key_number: int) -> str:
    try:
        return GROQ_KEY_ENV[int(key_number)]
    except (KeyError, TypeError, ValueError) as exc:
        raise ProviderAdapterError(
            f"Unsupported Groq key number: {key_number}. Expected 1-2."
        ) from exc


def call_groq(
    prompt: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> str:
    """Call Groq's OpenAI-compatible chat endpoint."""
    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    api_key = api_key or _require_env("GROQ_API_KEY")
    model = model or _env("GROQ_MODEL", "openai/gpt-oss-120b")
    url = "https://api.groq.com/openai/v1/chat/completions"

    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
    except requests.RequestException as exc:
        raise ProviderAdapterError(f"Groq network error: {exc}") from exc

    if not response.ok:
        raise ProviderAdapterError(
            f"Groq API error {response.status_code}: {response.text}"
        )

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ProviderAdapterError(
            f"Unexpected Groq response: {response.text}"
        ) from exc

    if content is None or not str(content).strip():
        raise ProviderAdapterError(f"Groq returned empty content: {data}")

    return str(content)


def call_groq_with_key(
    prompt: str,
    key_number: int,
    model: Optional[str] = None,
) -> str:
    env_name = _groq_env_name(key_number)
    api_key = _require_env(env_name)
    return call_groq(prompt=prompt, model=model, api_key=api_key)


# ---------------------------------------------------------------------------
# Cloudflare Workers AI
# ---------------------------------------------------------------------------


def call_cloudflare(
    prompt: str,
    model: Optional[str] = None,
) -> str:
    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    account_id = _require_env("CLOUDFLARE_ACCOUNT_ID")
    api_token = _require_env("CLOUDFLARE_API_TOKEN")
    model = model or _env(
        "CLOUDFLARE_MODEL",
        "@cf/meta/llama-3.1-8b-instruct",
    )

    url = (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{account_id}/ai/run/{model}"
    )

    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            json={"messages": [{"role": "user", "content": prompt}]},
            timeout=60,
        )
    except requests.RequestException as exc:
        raise ProviderAdapterError(f"Cloudflare network error: {exc}") from exc

    if not response.ok:
        raise ProviderAdapterError(
            f"Cloudflare API error {response.status_code}: {response.text}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise ProviderAdapterError(
            f"Cloudflare returned non-JSON response: {response.text}"
        ) from exc

    if not data.get("success"):
        raise ProviderAdapterError(f"Cloudflare request failed: {data}")

    result = data.get("result")
    if isinstance(result, dict):
        for field in ("response", "text"):
            value = result.get(field)
            if value is not None and str(value).strip():
                return str(value)

    raise ProviderAdapterError(f"Unexpected Cloudflare response: {data}")


# ---------------------------------------------------------------------------
# OpenRouter
# ---------------------------------------------------------------------------


def call_openrouter(
    prompt: str,
    model: Optional[str] = None,
) -> str:
    """Use OpenRouter as an overflow/fallback adapter.

    By default, openrouter/free lets OpenRouter choose an eligible free model.
    The router can pass a concrete model when it has a reason to do so.
    """
    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    api_key = _require_env("OPENROUTER_API_KEY")
    model = model or _env("OPENROUTER_MODEL", "openrouter/free")

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": _env("OPENROUTER_SITE_URL", "http://localhost"),
                "X-Title": _env("OPENROUTER_APP_NAME", "ODDI AI"),
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
    except requests.RequestException as exc:
        raise ProviderAdapterError(f"OpenRouter network error: {exc}") from exc

    if not response.ok:
        raise ProviderAdapterError(
            f"OpenRouter API error {response.status_code}: {response.text}"
        )

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ProviderAdapterError(
            f"Unexpected OpenRouter response: {response.text}"
        ) from exc

    if content is None or not str(content).strip():
        raise ProviderAdapterError(f"OpenRouter returned empty content: {data}")

    return str(content)


# ---------------------------------------------------------------------------
# Unified routing adapter
# ---------------------------------------------------------------------------


def call_provider(
    provider: str,
    prompt: str,
    model: Optional[str] = None,
    capacity_id: Optional[str] = None,
    api_key_number: Optional[int] = None,
) -> str:
    """Execute the exact provider/capacity selected by the routing engine."""
    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    provider = provider.lower().strip()

    if provider == "gemini":
        if api_key_number is not None:
            return call_gemini_with_key(prompt, int(api_key_number), model)
        if capacity_id and capacity_id.startswith("gemini_key_"):
            try:
                return call_gemini_with_key(
                    prompt, int(capacity_id.rsplit("_", 1)[-1]), model
                )
            except ValueError as exc:
                raise ProviderAdapterError(str(exc)) from exc
        return call_gemini(prompt, model)

    if provider == "mistral":
        return call_mistral(prompt, model)

    if provider == "groq":
        if api_key_number is not None:
            return call_groq_with_key(prompt, int(api_key_number), model)
        if capacity_id and capacity_id.startswith("groq_key_"):
            return call_groq_with_key(
                prompt, int(capacity_id.rsplit("_", 1)[-1]), model
            )
        return call_groq(prompt, model)

    if provider == "cloudflare":
        return call_cloudflare(prompt, model)

    if provider == "openrouter":
        return call_openrouter(prompt, model)

    raise ProviderAdapterError(f"No adapter available for provider: {provider}")


def call_provider_with_fallback(
    prompt: str,
    providers: Optional[list[str]] = None,
) -> str:
    """Simple provider fallback for legacy callers.

    The production routing path should use execute_route(), because it preserves
    model/capacity decisions and reliability state.
    """
    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    if providers is None:
        providers = ["gemini", "mistral", "groq", "cloudflare", "openrouter"]

    errors = []
    for provider in providers:
        try:
            return call_provider(provider, prompt)
        except Exception as err:
            errors.append(f"{provider}: {err}")

    raise ProviderAdapterError(
        f"All providers failed. Details: {'; '.join(errors)}"
    )


# ---------------------------------------------------------------------------
# Routed execution + reliability
# ---------------------------------------------------------------------------


def execute_route(route: dict, prompt: str) -> dict:
    """Execute routed candidates in order with shared reliability tracking."""
    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    # Phase 6/7: an explicit quota rejection must never call a provider.
    if route.get("allowed") is False:
        return {
            "status": "rejected",
            "success": False,
            "allowed": False,
            "reason": route.get("reason", "route_not_allowed"),
            "provider": None,
            "model": None,
            "capacity_id": None,
            "api_key_number": None,
            "attempts": 0,
            "failures": [],
        }

    candidates = route.get("candidates", [])
    if not candidates:
        raise ProviderAdapterError("Route contains no candidates.")

    failures = []

    for candidate in candidates:
        provider = candidate.get("provider")
        model = candidate.get("model")
        capacity_id = candidate.get("capacity_id")
        api_key_number = candidate.get("api_key_number")

        if not provider:
            failures.append({"candidate": candidate, "error": "Missing provider."})
            continue

        if not RELIABILITY_MANAGER.is_healthy(provider, capacity_id):
            failures.append({
                "provider": provider,
                "model": model,
                "capacity_id": capacity_id,
                "api_key_number": api_key_number,
                "error": "Capacity temporarily unhealthy.",
                "skipped": True,
            })
            continue

        try:
            response = call_provider(
                provider=provider,
                prompt=prompt,
                model=model,
                capacity_id=capacity_id,
                api_key_number=api_key_number,
            )

            if not response or not str(response).strip():
                raise ProviderAdapterError(f"{provider} returned empty content.")

            RELIABILITY_MANAGER.record_success(provider, capacity_id)

            return {
                "status": "success",
                "success": True,
                "response": response,
                "provider": provider,
                "model": model,
                "capacity_id": capacity_id,
                "api_key_number": api_key_number,
                "attempts": len(failures) + 1,
                "failures": failures,
            }

        except Exception as exc:
            reliability_state = RELIABILITY_MANAGER.record_failure(
                provider=provider,
                capacity_id=capacity_id,
                error=exc,
            )

            failures.append({
                "provider": provider,
                "model": model,
                "capacity_id": capacity_id,
                "api_key_number": api_key_number,
                "error": str(exc),
                "failure_type": reliability_state.get("failure_type"),
                "reliability_healthy": reliability_state.get("healthy"),
            })

    return {
        "status": "failed",
        "success": False,
        "allowed": True,
        "response": None,
        "provider": None,
        "model": None,
        "capacity_id": None,
        "api_key_number": None,
        "attempts": len(failures),
        "failures": failures,
        "reason": "all_candidates_failed",
    }


# ---------------------------------------------------------------------------
# Safe API-key health checks
# ---------------------------------------------------------------------------


def check_configured_api_keys(prompt: str = "Reply with exactly: ODDI_OK") -> dict:
    """Make one minimal live request per configured API key.

    This function intentionally reports status/errors only; it never returns
    or prints the secret API keys. Run it from the ODDI environment containing
    the real .env file.
    """
    results = {}

    for key_number, env_name in GEMINI_KEY_ENV.items():
        if os.getenv(env_name):
            try:
                reply = call_gemini_with_key(prompt, key_number)
                results[f"gemini_key_{key_number}"] = {
                    "configured": True,
                    "working": bool(reply.strip()),
                    "error": None,
                }
            except Exception as exc:
                results[f"gemini_key_{key_number}"] = {
                    "configured": True,
                    "working": False,
                    "error": str(exc),
                }
        else:
            results[f"gemini_key_{key_number}"] = {
                "configured": False,
                "working": False,
                "error": f"Missing {env_name}",
            }

    # Mistral
    if os.getenv("MISTRAL_API_KEY"):
        try:
            reply = call_mistral(prompt)
            results["mistral"] = {
                "configured": True,
                "working": bool(reply.strip()),
                "error": None,
            }
        except Exception as exc:
            results["mistral"] = {
                "configured": True,
                "working": False,
                "error": str(exc),
            }
    else:
        results["mistral"] = {
            "configured": False,
            "working": False,
            "error": "Missing MISTRAL_API_KEY",
        }

    # Groq keys
    for key_number, env_name in GROQ_KEY_ENV.items():
        if os.getenv(env_name):
            try:
                reply = call_groq_with_key(prompt, key_number)
                results[f"groq_key_{key_number}"] = {
                    "configured": True,
                    "working": bool(reply.strip()),
                    "error": None,
                }
            except Exception as exc:
                results[f"groq_key_{key_number}"] = {
                    "configured": True,
                    "working": False,
                    "error": str(exc),
                }
        else:
            results[f"groq_key_{key_number}"] = {
                "configured": False,
                "working": False,
                "error": f"Missing {env_name}",
            }

    # OpenRouter
    if os.getenv("OPENROUTER_API_KEY"):
        try:
            reply = call_openrouter(prompt)
            results["openrouter"] = {
                "configured": True,
                "working": bool(reply.strip()),
                "error": None,
            }
        except Exception as exc:
            results["openrouter"] = {
                "configured": True,
                "working": False,
                "error": str(exc),
            }
    else:
        results["openrouter"] = {
            "configured": False,
            "working": False,
            "error": "Missing OPENROUTER_API_KEY",
        }

    # Cloudflare requires both credentials.
    if os.getenv("CLOUDFLARE_ACCOUNT_ID") and os.getenv("CLOUDFLARE_API_TOKEN"):
        try:
            reply = call_cloudflare(prompt)
            results["cloudflare"] = {
                "configured": True,
                "working": bool(reply.strip()),
                "error": None,
            }
        except Exception as exc:
            results["cloudflare"] = {
                "configured": True,
                "working": False,
                "error": str(exc),
            }
    else:
        results["cloudflare"] = {
            "configured": False,
            "working": False,
            "error": "Missing CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN",
        }

    return results


if __name__ == "__main__":
    import json

    print(json.dumps(check_configured_api_keys(), indent=2))
