from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from .config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

# Import registry and telemetry
try:
    from app.prompts.registry import get_archive_detective_prompts
    from app.prompts.telemetry import log_router
except ImportError:
    # Fallback: try backend path if app.prompts doesn't exist
    try:
        from backend.app.prompts.registry import get_archive_detective_prompts
        from backend.app.prompts.telemetry import log_router
    except ImportError:
        # Last resort: create stub functions
        logger.warning("Prompt registry not found, using fallback")
        def get_archive_detective_prompts(version: str | None = None) -> tuple[str, str]:
            return ("Archive Detective system prompt", "Router prompt")
        def log_router(*args, **kwargs) -> None:
            pass

# Load prompts from registry (version from env, default v2)
SYSTEM_PROMPT, ROUTER_PROMPT = get_archive_detective_prompts()
PROMPT_VERSION = os.getenv("PROMPTS_ARCHIVE_DETECTIVE_VERSION", "v2")

# JSON schema for router output validation
ROUTER_SCHEMA = {
    "type": "object",
    "oneOf": [
        {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "reason": {"type": "string"}
            },
            "required": ["command", "reason"],
            "additionalProperties": False
        },
        {
            "type": "object",
            "properties": {
                "say": {"type": "string"},
                "reason": {"type": "string"}
            },
            "required": ["say", "reason"],
            "additionalProperties": False
        }
    ]
}


def is_enabled() -> bool:
    return bool(OPENAI_API_KEY)


def _client():
    from openai import OpenAI
    import httpx
    
    # Create httpx client without proxy settings to avoid conflicts
    # OpenAI library may inherit proxy settings from environment
    http_client = httpx.Client(
        timeout=60.0,
        # Explicitly don't pass proxies
    )
    
    # Create OpenAI client with explicit httpx client
    return OpenAI(
        api_key=OPENAI_API_KEY or None,
        http_client=http_client,
    )


# SYSTEM constant replaced by SYSTEM_PROMPT from registry (loaded above)
SYSTEM = SYSTEM_PROMPT  # Backward compatibility


def _validate_router_output(data: dict[str, Any]) -> bool:
    """
    Validate router output matches schema.
    
    Args:
        data: Router output dict
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(data, dict):
        return False
    
    # Check for required keys
    if "command" in data:
        if "reason" not in data:
            return False
        # Validate command format
        cmd = data["command"]
        valid_commands = {
            "/search",
            "/suggest-searches",
            "/save-image",
            "/fetch-image",
            "/generate-queries",
            "/make-brief",
            "/harvest-stub",
            "/report",
            "/read",
            "/summarize",
            "/add-to-report",
            "/report-view",
            "/report-pdf",
            "/help",
        }
        if not any(cmd.startswith(valid) for valid in valid_commands):
            return False
        return True
    elif "say" in data:
        if "reason" not in data:
            return False
        return True
    
    return False


def route_message(message: str, context: str = "") -> dict[str, Any] | None:
    """
    Route user message to appropriate command or generate conversational response.
    
    Uses structured outputs with JSON schema validation and retry logic.
    """
    if not is_enabled():
        return None
    user = message.strip()
    
    # Build instruction from router prompt template
    instruction = ROUTER_PROMPT
    
    # Add context if available
    if context:
        instruction += "\n\nRESEARCH CONTEXT:\n" + context
    
    # Add user message
    instruction += f"\n\nUser: {user}"
    
    # Track chosen action for telemetry
    chosen_action = None
    is_valid = False
    output = None
    
    try:
        client = _client()
        
        # First attempt with structured outputs
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.1,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": instruction},
                ],
                response_format={"type": "json_object"},
            )
            txt = (resp.choices[0].message.content or "").strip()
        except Exception as e:
            logger.warning(f"Structured output failed, trying without: {e}")
            # Fallback to regular completion
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.1,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": instruction},
                ],
            )
            txt = (resp.choices[0].message.content or "").strip()
        
        # Clean up markdown code blocks if present
        if txt.startswith("```"):
            txt = txt.strip("`")
            if txt.lower().startswith("json"):
                txt = txt[4:].lstrip()
        
        # Parse JSON
        try:
            data = json.loads(txt)
            if not isinstance(data, dict):
                # Retry once with reminder
                logger.warning("Router returned non-dict, retrying with JSON reminder")
                retry_instruction = instruction + "\n\nCRITICAL: Return ONLY a JSON object with 'command' and 'reason' OR 'say' and 'reason'. No prose, no markdown."
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    temperature=0.1,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": retry_instruction},
                    ],
                    response_format={"type": "json_object"},
                )
                txt = (resp.choices[0].message.content or "").strip()
                if txt.startswith("```"):
                    txt = txt.strip("`")
                    if txt.lower().startswith("json"):
                        txt = txt[4:].lstrip()
                data = json.loads(txt)
            
            # Validate schema
            is_valid = _validate_router_output(data)
            output = data
            
            if is_valid:
                if "command" in data:
                    chosen_action = "command"
                    cmd = data["command"]
                    return {"command": cmd, "reason": data.get("reason", "")}
                elif "say" in data:
                    chosen_action = "say"
                    return {"say": str(data["say"])[:600], "reason": data.get("reason", "")}
            else:
                logger.warning(f"Invalid router response schema: {data}")
                # Try to extract valid parts
                if "command" in data or "say" in data:
                    chosen_action = "command" if "command" in data else "say"
                    return {
                        ("command" if "command" in data else "say"): data.get("command") or data.get("say", ""),
                        "reason": data.get("reason", "Response validation failed"),
                    }
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error: {e}, text: {txt[:200]}")
            # Retry once with JSON-only reminder
            try:
                retry_instruction = instruction + "\n\nCRITICAL: Return ONLY valid JSON. No prose, no markdown, no explanations. Just JSON."
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    temperature=0.1,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": retry_instruction},
                    ],
                    response_format={"type": "json_object"},
                )
                txt = (resp.choices[0].message.content or "").strip()
                if txt.startswith("```"):
                    txt = txt.strip("`")
                    if txt.lower().startswith("json"):
                        txt = txt[4:].lstrip()
                data = json.loads(txt)
                is_valid = _validate_router_output(data)
                output = data
                if is_valid:
                    if "command" in data:
                        chosen_action = "command"
                        return {"command": data["command"], "reason": data.get("reason", "")}
                    elif "say" in data:
                        chosen_action = "say"
                        return {"say": str(data["say"])[:600], "reason": data.get("reason", "")}
            except Exception as retry_err:
                logger.error(f"Retry also failed: {retry_err}")
                # Last resort: return a say response
                if txt:
                    chosen_action = "say"
                    return {
                        "say": f"I understand: {txt[:200]}",
                        "reason": "JSON parse failed after retry, using text response",
                    }
    except Exception as e:
        # Handle API errors gracefully - return None to fall back to slash commands
        logger.warning(f"OpenAI API error: {e}")
    finally:
        # Log telemetry
        try:
            log_router(PROMPT_VERSION, user, output, is_valid, chosen_action)
        except Exception as tel_err:
            logger.debug(f"Telemetry logging failed: {tel_err}")
    
    return None


def call_responses_api(
    input_text: str,
    model: str = "gpt-5-nano",
    store: bool = True,
    timeout: float = 30.0,
) -> dict[str, Any] | None:
    """
    Call OpenAI Responses API endpoint (/v1/responses).

    Args:
        input_text: The input text/prompt to send to the API
        model: Model to use (default: "gpt-5-nano")
        store: Whether to store the response (default: True)
        timeout: Request timeout in seconds (default: 30.0)

    Returns:
        Dictionary with response data, or None on error
    """
    if not is_enabled():
        logger.warning("OpenAI API key not configured")
        return None

    url = "https://api.openai.com/v1/responses"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }
    payload = {
        "model": model,
        "input": input_text,
        "store": store,
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(
            f"OpenAI Responses API HTTP error: {e.response.status_code} - {e.response.text}"
        )
        return None
    except httpx.RequestError as e:
        logger.error(f"OpenAI Responses API request error: {e}")
        return None
    except Exception as e:
        logger.error(f"OpenAI Responses API unexpected error: {e}")
        return None
