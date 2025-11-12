"""Generate intelligent search suggestions for historical research."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from .chat_llm import is_enabled

# Import registry and telemetry
try:
    from app.prompts.registry import get_search_suggestions_prompts
    from app.prompts.telemetry import log_search_suggestions
except ImportError:
    # Fallback: try backend path if app.prompts doesn't exist
    try:
        from backend.app.prompts.registry import get_search_suggestions_prompts
        from backend.app.prompts.telemetry import log_search_suggestions
    except ImportError:
        # Last resort: create stub functions
        logger = logging.getLogger(__name__)
        logger.warning("Prompt registry not found, using fallback")
        def get_search_suggestions_prompts(version: str | None = None) -> tuple[str, str]:
            return ("Search suggestions system prompt", "Search suggestions user prompt: {topic} {context}")
        def log_search_suggestions(*args, **kwargs) -> None:
            pass

logger = logging.getLogger(__name__)

# Load prompts from registry
SUGGESTIONS_SYSTEM, SUGGESTIONS_USER = get_search_suggestions_prompts()
# Alias for backward compatibility
SUG_SYS = SUGGESTIONS_SYSTEM
SUG_USER = SUGGESTIONS_USER
PROMPT_VERSION = os.getenv("PROMPTS_SEARCH_SUGGESTIONS_VERSION", "v2")

# JSON schema for suggestions validation
SUGGESTIONS_SCHEMA = {
    "type": "array",
    "items": {"type": "string"},
    "minItems": 5,
    "maxItems": 8
}


async def _generate_search_suggestions(topic: str, recent_results: list[Any]) -> list[str]:
    """
    Generate search query suggestions for a topic.
    
    Args:
        topic: The topic the user wants to explore
        recent_results: Recent search results to inform suggestions
        
    Returns:
        List of suggested search queries
    """
    if not is_enabled():
        return []
    
    try:
        from openai import OpenAI

        from .config import OPENAI_API_KEY
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Build context from recent results
        context = ""
        if recent_results:
            context = "\nRecent results found:\n"
            for r in recent_results[:3]:
                title = r.title if hasattr(r, 'title') else r.get('title', 'Untitled')
                context += f"- {title}\n"
        
        # Use prompts from registry
        user_prompt = SUGGESTIONS_USER.format(topic=topic, context=context)
        
        # Track validation for telemetry
        is_valid = False
        suggestions = []
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.7,
                messages=[
                    {"role": "system", "content": SUGGESTIONS_SYSTEM},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},  # Force JSON output
            )
            
            text = (response.choices[0].message.content or "").strip()
            
            # Clean up markdown code blocks if present
            if text.startswith("```"):
                text = text.strip("`")
                if text.lower().startswith("json"):
                    text = text[4:].lstrip()
            
            # Try to parse as JSON
            try:
                data = json.loads(text)
                # Handle both direct array and object with array
                if isinstance(data, list):
                    suggestions = [str(s).strip() for s in data if s]
                elif isinstance(data, dict):
                    # Look for common keys that might contain the array
                    for key in ["suggestions", "queries", "results", "items"]:
                        if key in data and isinstance(data[key], list):
                            suggestions = [str(s).strip() for s in data[key] if s]
                            break
                    # If no key found, try to find any array value
                    if not suggestions:
                        for value in data.values():
                            if isinstance(value, list):
                                suggestions = [str(s).strip() for s in value if s]
                                break
                
                # Validate array length
                if suggestions and 5 <= len(suggestions) <= 8:
                    is_valid = True
                    suggestions = suggestions[:8]
                elif suggestions:
                    # Adjust to valid range
                    suggestions = suggestions[:8]
                    is_valid = len(suggestions) >= 5
            except json.JSONDecodeError:
                # Retry once with JSON-only reminder
                logger.warning("JSON decode failed, retrying with reminder")
                retry_prompt = user_prompt + "\n\nCRITICAL: Return ONLY a JSON array of strings. No prose, no markdown."
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        temperature=0.7,
                        messages=[
                            {"role": "system", "content": SUGGESTIONS_SYSTEM},
                            {"role": "user", "content": retry_prompt}
                        ],
                        response_format={"type": "json_object"},
                    )
                    text = (response.choices[0].message.content or "").strip()
                    if text.startswith("```"):
                        text = text.strip("`")
                        if text.lower().startswith("json"):
                            text = text[4:].lstrip()
                    data = json.loads(text)
                    if isinstance(data, list):
                        suggestions = [str(s).strip() for s in data if s]
                    elif isinstance(data, dict):
                        for value in data.values():
                            if isinstance(value, list):
                                suggestions = [str(s).strip() for s in value if s]
                                break
                    if suggestions and 5 <= len(suggestions) <= 8:
                        is_valid = True
                        suggestions = suggestions[:8]
                except Exception as retry_err:
                    logger.error(f"Retry also failed: {retry_err}")
                    # Last resort: extract from text
                    json_match = re.search(r'\[.*?\]', text, re.DOTALL)
                    if json_match:
                        try:
                            suggestions = json.loads(json_match.group(0))
                            if isinstance(suggestions, list):
                                suggestions = [str(s).strip() for s in suggestions if s][:8]
                                is_valid = len(suggestions) >= 5
                        except json.JSONDecodeError:
                            pass
                    
                    # Last resort: split by lines
                    if not suggestions:
                        lines = [line.strip() for line in text.split('\n') if line.strip()]
                        for line in lines[:8]:
                            cleaned = re.sub(r'^\d+[\.\)]\s*', '', line)
                            cleaned = cleaned.strip('"\'`')
                            if cleaned and len(cleaned) > 5:
                                suggestions.append(cleaned)
                        suggestions = suggestions[:8]
                        is_valid = len(suggestions) >= 5
        except Exception as e:
            logger.warning(f"Error in search suggestions API call: {e}")
            suggestions = []
        finally:
            # Log telemetry
            try:
                log_search_suggestions(PROMPT_VERSION, topic, len(suggestions), is_valid)
            except Exception:
                pass  # Don't fail on telemetry errors
        
        return suggestions[:8] if suggestions else []
        
    except Exception as e:
        logger.warning(f"Error generating search suggestions: {e}")
        return []
