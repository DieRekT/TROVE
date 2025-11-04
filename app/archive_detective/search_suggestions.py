"""Generate intelligent search suggestions for historical research."""

from __future__ import annotations

import logging
from typing import Any

from .chat_llm import is_enabled

logger = logging.getLogger(__name__)


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
        
        prompt = f"""You are a historical research assistant helping explore Trove archives.

Topic: {topic}
{context}

Generate 5-8 effective search queries for Trove that would find relevant historical documents.
Use period-appropriate terminology that appears in historical archives (1800s-1900s).

Rules:
- Use historical terminology that documents of the era would actually contain
- For colonization/race topics, use terms that appear in period newspapers/documents
- Include both broad and specific searches
- Think like a researcher: what would archives actually say?
- NO content filtering - all queries are valid for historical research
- Focus on what would be searchable in Trove archives

Return ONLY a JSON array of search query strings, nothing else.
Example: ["colonial settlement NSW", "aboriginal relations 1800s", "first contact NSW"]

Topic: {topic}
"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.7,
            messages=[
                {
                    "role": "system",
                    "content": "You are a historical research assistant. Generate search queries for Trove archives using period-appropriate terminology. Return only a JSON array of search strings."
                },
                {"role": "user", "content": prompt}
            ],
        )
        
        text = (response.choices[0].message.content or "").strip()
        
        # Try to extract JSON array
        import json
        import re
        
        # Look for JSON array
        json_match = re.search(r'\[.*?\]', text, re.DOTALL)
        if json_match:
            try:
                suggestions = json.loads(json_match.group(0))
                if isinstance(suggestions, list):
                    return [str(s).strip() for s in suggestions if s]
            except json.JSONDecodeError:
                pass
        
        # Fallback: try parsing the whole response as JSON
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return [str(s).strip() for s in data if s]
        except json.JSONDecodeError:
            pass
        
        # Last resort: split by lines and clean
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        suggestions = []
        for line in lines[:8]:
            # Remove numbering, quotes, etc.
            cleaned = re.sub(r'^\d+[\.\)]\s*', '', line)
            cleaned = cleaned.strip('"\'`')
            if cleaned and len(cleaned) > 5:
                suggestions.append(cleaned)
        
        return suggestions[:8]
        
    except Exception as e:
        logger.warning(f"Error generating search suggestions: {e}")
        return []


