# Pin/Cite UI Integration Guide

This guide explains how to integrate the pin/unpin UI and `/cite` command functionality into your Trove application.

## What's Included

### Frontend Components (React/TypeScript)
- `frontend/components/ContextTray.tsx` - Research pill with pin/unpin tray
- `frontend/components/CitationsFooter.tsx` - Sources footer for AI responses
- `frontend/hooks/useContextStore.ts` - Context management hook
- `frontend/lib/slashCommands.ts` - Slash command parser

### Vanilla JS Implementation (Already Integrated)
- `static/context-tray.js` - Vanilla JS version for HTML templates
- `static/context-tray.css` - Styles for context tray and citations

## ✅ Already Integrated

The pin/cite UI has been integrated into `templates/chat.html`:

1. **Context Tray** - Added above the chat input
2. **Slash Commands** - `/context`, `/cite`, `/clear` handlers
3. **Citations Footer** - Automatically renders when backend returns `citations` array

## How It Works

### Context Tray
- Click the **"📚 Research (n)"** pill to open the context tray
- View all tracked articles
- Pin/unpin articles (pinned articles appear first)
- Clear all articles

### Slash Commands

#### `/context`
Opens the context tray to view and manage articles.

#### `/cite`
Generates citation markers `[1][2]` for pinned articles and displays them with a sources footer.

#### `/clear`
Clears all articles from the research context (with confirmation).

### Citations Footer
When your backend returns a `citations` array in the chat response, it automatically renders as a numbered sources list:

```json
{
  "say": "Here's the answer...",
  "citations": [
    {
      "title": "Article Title",
      "url": "https://trove.nla.gov.au/...",
      "date": "1923-01-15",
      "source": "The Sydney Morning Herald"
    }
  ]
}
```

## Backend Integration

The backend already exposes the required endpoints in `app/context_api.py`:

- `GET /api/context` - Get all articles for session
- `POST /api/context/track` - Track an article
- `POST /api/context/pin/{trove_id}` - Pin an article
- `POST /api/context/unpin/{trove_id}` - Unpin an article
- `DELETE /api/context` - Clear all articles
- `GET /api/context/pack` - Get packed context for prompt

### Tracking Articles

To track articles when users view them, add this to your article viewing code:

```javascript
// When displaying an article
async function trackArticle(article) {
  try {
    await fetch('/api/context/track', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        trove_id: article.id,
        title: article.title,
        date: article.date,
        source: article.source,
        url: article.url,
        snippet: article.snippet || ''
      })
    });
  } catch (error) {
    console.error('Failed to track article:', error);
  }
}
```

### Using Context in AI Prompts

When sending messages to your AI, include the packed context:

```python
# In your chat endpoint
from app.context_store import pack_for_prompt, sid_from

# Get session ID
sid = sid_from(request.headers, request.client.host, request.headers.get("user-agent"))

# Pack context (pinned articles first, then others)
packed = pack_for_prompt(sid, max_chars=3500)

# Include in your prompt
context_text = packed.get('packed_text', '')
prompt = f"""
Context from recent articles:
{context_text}

User question: {user_message}
"""
```

## Testing

1. **Open 2-3 articles** - They should be automatically tracked (if you implement tracking)
2. **Click "📚 Research (n)"** - Should show the context tray with articles
3. **Pin an article** - Click the 📍 button, it should change to 📌
4. **Type `/context`** - Should open the tray
5. **Type `/cite`** - Should generate citation markers for pinned articles
6. **Ask a question** - Your backend should include pinned articles in the context

## For React/Next.js Users

If you're building a separate React frontend, use the React components in `frontend/`:

```tsx
import { ContextTray } from '@/components/ContextTray';
import { CitationsFooter } from '@/components/CitationsFooter';
import { parseSlashCommand } from '@/lib/slashCommands';

function ChatPage() {
  const sessionId = 'your-session-id';
  
  return (
    <div>
      <ContextTray sessionId={sessionId} />
      {/* Your chat messages */}
      {messages.map(m => (
        <div key={m.id}>
          <div>{m.text}</div>
          {m.citations && <CitationsFooter items={m.citations} />}
        </div>
      ))}
    </div>
  );
}
```

## Customization

### Styling
Edit `static/context-tray.css` to customize the appearance.

### Slash Commands
Add more commands in `static/context-tray.js` or `frontend/lib/slashCommands.ts`.

### Citation Format
Modify `renderCitationsFooter` in `static/context-tray.js` to change citation display format.

## Notes

- Session ID is automatically generated from request headers and IP
- Pinned articles are prioritized in `pack_for_prompt`
- Citations are automatically rendered when backend includes them
- The context tray closes when clicking outside

