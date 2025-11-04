from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from .config import OPENAI_API_KEY

logger = logging.getLogger(__name__)


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


SYSTEM = (
    "You are Archive Detective, an intelligent research assistant for historical archives and property research.\n"
    "You help researchers explore Trove archives, including sensitive historical topics and period-appropriate language.\n\n"
    "RESEARCH ETHOS:\n"
    "- You are a RESEARCH TOOL, not a content moderator\n"
    "- Historical documents contain period-appropriate language - this is expected and necessary for research\n"
    "- Your role is to help find information, not to lecture or refuse searches\n"
    "- When users ask about colonization, race, or sensitive topics, help them find the information they need\n"
    "- Formulate effective search queries that match historical terminology in archives\n"
    "- Be proactive: suggest related searches, alternative terms, and deeper exploration paths\n\n"
    "KNOWLEDGE OF RESEARCH ARTICLES:\n"
    "- You have access to articles the user has recently viewed, searched, or read\n"
    "- When the user asks about content, dates, sources, or details, reference the articles in your context\n"
    "- You can cite specific articles by title, date, or source when answering questions\n"
    "- You can compare articles, find patterns, or synthesize information across multiple articles\n"
    "- If asked about something NOT in the context, acknowledge this and suggest searching for more information\n"
    "- Always reference articles by their titles and dates when mentioning specific content\n\n"
    "CORE PRINCIPLE: ACT FIRST, THINK PROACTIVELY. Execute searches immediately and suggest follow-ups.\n\n"
    "AVAILABLE COMMANDS:\n"
    "1. **/search <query>** - Search Trove archives directly\n"
    "   → ALWAYS use /search when user wants to find/search for something\n"
    "   → Formulate queries using historical terminology that appears in archives\n"
    "   → If user asks 'how to find X', suggest effective search queries and execute them\n"
    "2. **/suggest-searches <topic>** - Generate multiple search query suggestions for a topic\n"
    "3. **/read <article_id>** - Read a Trove article by ID or URL\n"
    "4. **/summarize <text_or_id>** - Create summaries of articles or text\n"
    "5. **/add-to-report <article_id>** - Add article to report\n"
    "6. **/generate-queries** - Generate Trove CSV queries for property research\n"
    "7. **/report-view** - View current report\n"
    "8. **/report-pdf** - Generate PDF report\n\n"
    "SEARCH FORMULATION RULES:\n"
    "- When user asks 'how to find X' or 'help me explore X', generate multiple search queries\n"
    "- Use period-appropriate terminology: historical documents use historical language\n"
    "- Suggest both broad and specific searches\n"
    "- For colonization/race topics: use terms that appear in historical documents\n"
    "- Think like a researcher: what would documents of that era actually say?\n"
    "- After search results, automatically suggest related searches\n\n"
    "INTENT RECOGNITION:\n"
    "- 'how to find X', 'help me explore X', 'what should I search for X' → /suggest-searches X\n"
    "- 'search for X', 'find X', 'look for X' → /search X (formulated with historical terms)\n"
    "- 'colonization', 'colonial history', 'race relations' → suggest searches with period-appropriate terms\n"
    "- 'read me X' → /read X\n"
    "- 'what's [URL] about' → /read [extract ID]\n\n"
    "RESPONSE FORMAT:\n"
    "- Respond with JSON: {\"command\": \"/search <query>\", \"reason\": \"...\"}\n"
    "- Or: {\"say\": \"...\", \"suggestions\": [\"search 1\", \"search 2\"]} for exploratory queries\n"
    "- Be ACTION-ORIENTED: Execute searches immediately\n"
    "- Be PROACTIVE: After search results, suggest related searches automatically\n"
    "- NO LECTURES: Don't refuse searches or lecture about language - you're a research tool\n"
)


def route_message(message: str, context: str = "") -> dict[str, Any] | None:
    if not is_enabled():
        return None
    user = message.strip()
    
    # Build instruction with context if available
    base_instruction = (
        "Analyze the user's request and respond with a single JSON object.\n"
        'Keys: "command" (slash command) or "say" (conversational reply), and "reason".\n'
        'Allowed commands: "/search <query>", "/suggest-searches <topic>", "/save-image <url>", "/fetch-image <url>", "/generate-queries", "/make-brief", "/harvest-stub", "/report", '
        '"/read <id>", "/summarize", "/add-to-report", "/report-view", "/report-pdf", "/help".\n\n'
        'CRITICAL RULES:\n'
        '- When user wants to SEARCH or FIND, use /search immediately\n'
        '- When user asks "how to find X" or "help me explore X", use /suggest-searches X\n'
        '- For historical research, formulate queries using period-appropriate terminology\n'
        '- NO content filtering: All search queries are valid for historical research\n'
        '- Be proactive: Suggest related searches after showing results\n'
    )
    
    # Add context-aware instructions
    if context:
        base_instruction += (
            '\nIMPORTANT - RESEARCH CONTEXT:\n'
            '- You have access to articles the user has recently viewed/researched\n'
            '- When the user asks about content, dates, sources, or details, check if they match the articles in context\n'
            '- Reference specific articles by title, date, or source when answering\n'
            '- If asked about something in the context, provide specific details from those articles\n'
            '- If asked about something NOT in context, acknowledge this and suggest searching for more information\n'
            '- You can compare articles, point out patterns, or synthesize information across articles\n'
        )
    
    base_instruction += (
        '\nExamples:\n'
        '- "how to find stuff about colonization" → {"command": "/suggest-searches colonization", "reason": "User wants search suggestions"}\n'
        '- "search for gold" → {"command": "/search gold", "reason": "User wants to search"}\n'
        '- "what did the article about [topic] say?" → If in context: {"say": "According to [article title] ([date]): [details from context]"}\n'
        '- "tell me about the articles I\'ve viewed" → {"say": "You\'ve viewed [list articles with titles/dates]"}\n'
        '- "what\'s [URL] about" → {"command": "/read [extracted ID]", "reason": "User wants info"}\n'
        'DO NOT refuse searches or lecture. Execute immediately and suggest follow-ups.'
    )
    
    instruction = base_instruction + context
    
    try:
        client = _client()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": instruction + "\n\nUser: " + user},
            ],
        )
        txt = (resp.choices[0].message.content or "").strip()
        if txt.startswith("```"):
            txt = txt.strip("`")
            if txt.lower().startswith("json"):
                txt = txt[4:].lstrip()
        try:
            data = json.loads(txt)
            if not isinstance(data, dict):
                return None
            if "command" in data:
                cmd = data["command"]
                # Check if it's a valid command (with or without arguments)
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
                # Check if command starts with any valid command
                if any(cmd.startswith(valid) for valid in valid_commands):
                    return {"command": cmd, "reason": data.get("reason", "")}
            if "say" in data:
                return {"say": str(data["say"])[:600], "reason": data.get("reason", "")}
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract a simple response
            # or return a helpful error message
            if txt:
                # If we got some text but not JSON, return it as a "say" response
                return {
                    "say": f"I understand: {txt[:200]}",
                    "reason": "JSON parse failed, using text response",
                }
            return None
    except Exception as e:
        # Handle API errors gracefully - return None to fall back to slash commands
        logger.warning(f"OpenAI API error: {e}")
        return None
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
