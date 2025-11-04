#!/usr/bin/env python3
"""Test script to verify OpenAI API integration."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.archive_detective.chat_llm import (
    call_responses_api,
    is_enabled,
    route_message,
)


def test_chat_completions():
    """Test the existing chat completions API."""
    print("Testing Chat Completions API (route_message)...")
    if not is_enabled():
        print("  ❌ API key not configured")
        return False

    result = route_message("Hello, can you help me?")
    if result:
        print(f"  ✅ Chat completions API working: {result}")
        return True
    else:
        print("  ⚠️  Chat completions API returned None (may be expected)")
        return True  # None is acceptable for route_message


def test_responses_api():
    """Test the new Responses API."""
    print("\nTesting Responses API (call_responses_api)...")
    if not is_enabled():
        print("  ❌ API key not configured")
        return False

    result = call_responses_api("write a haiku about ai", model="gpt-5-nano", store=True)
    if result:
        print(f"  ✅ Responses API working: {result}")
        return True
    else:
        print("  ❌ Responses API returned None (error occurred)")
        return False


if __name__ == "__main__":
    print("OpenAI API Integration Test")
    print("=" * 50)

    if not is_enabled():
        print("❌ OPENAI_API_KEY is not configured in .env")
        sys.exit(1)

    print("✅ API key is configured\n")

    chat_ok = test_chat_completions()
    responses_ok = test_responses_api()

    print("\n" + "=" * 50)
    if chat_ok and responses_ok:
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("⚠️  Some tests had issues (see above)")
        sys.exit(1)
