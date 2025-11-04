# 💬 Chat Functionality - How to Use

## Current Status

The chat interface is available at:
- **Archive Detective Chat**: `/chat` or `https://autographic-jacob-unsalably.ngrok-free.dev/chat`
- **Research Desk**: `/desk` or `https://autographic-jacob-unsalably.ngrok-free.dev/desk`

## How Chat Works

### 1. Slash Commands (Always Work)
These work immediately without AI:
- `/search gold discoveries` - Search Trove
- `/read <article_id>` - Read an article
- `/suggest-searches <topic>` - Get search suggestions
- `/help` - Show all commands

### 2. Natural Language (Requires OpenAI API Key)
If you have `OPENAI_API_KEY` set in `.env`, the chat can:
- Understand natural language: "search for gold discoveries"
- Route to appropriate commands automatically
- Provide conversational responses

### 3. Fallback Behavior
If AI isn't available, the chat:
- Detects search requests in your message
- Suggests the appropriate command
- Provides helpful guidance

## Testing Your Chat

Try these in the chat interface:

1. **Direct command:**
   ```
   /search gold discoveries NSW
   ```

2. **Natural language (if AI enabled):**
   ```
   tell me about gold discoveries in New South Wales
   ```

3. **Help:**
   ```
   /help
   ```

## Access Points

- **Web App**: http://127.0.0.1:8000/chat
- **Public Tunnel**: https://autographic-jacob-unsalably.ngrok-free.dev/chat
- **From Dashboard**: Click "Archive Detective" in sidebar

## Troubleshooting

If chat isn't conversational:
1. Check `.env` has `OPENAI_API_KEY` set
2. Try slash commands first: `/search <query>`
3. Check server logs for errors
4. The chat should still work with commands even without AI

## Quick Fix

If natural language isn't working, use slash commands:
- Instead of: "search for gold"
- Use: `/search gold`

The chat will still help you search and find information!

