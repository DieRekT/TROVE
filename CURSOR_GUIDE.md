# 🎯 Cursor AI Assistant Guide

## How I Can Help You in Cursor

While I can't directly control Cursor, I can provide you with exact instructions and code that you can use in Cursor's AI assistant (Cmd+K) or Composer.

## 🚀 Using Cursor's AI Features

### 1. Cmd+K (Inline AI)

**What it does**: Provides AI assistance for the current file/context

**How to use**:
1. Open a file in Cursor
2. Select code or place cursor where you want changes
3. Press `Cmd+K` (Mac) or `Ctrl+K` (Windows/Linux)
4. Type your request or paste my instructions
5. Review and accept changes

**Example**:
```
Open app/context_api.py and go to line 83
Then use Cmd+K and paste:
"Add a new endpoint DELETE /api/context/tracked that clears only non-pinned articles"
```

### 2. Composer (Multi-file AI)

**What it does**: Helps with changes across multiple files

**How to use**:
1. Press `Cmd+I` (Mac) or `Ctrl+I` (Windows/Linux)
2. Describe what you want to do
3. Cursor will suggest changes across files
4. Review and accept changes

**Example**:
```
Use Composer (Cmd+I) and paste:
"Implement full text scraping for articles. Add trafilatura and readability-lxml as fallbacks when Trove API returns only snippets. Update app/archive_detective/article_io.py to use scraping when text < 500 chars."
```

### 3. Chat (Sidebar AI)

**What it does**: General AI assistance and questions

**How to use**:
1. Open Chat sidebar (Cmd+L or click Chat icon)
2. Ask questions or request help
3. Get code suggestions and explanations

**Example**:
```
In Chat, ask:
"How do I implement article scraping with trafilatura in Python?"
```

## 📋 Common Workflows

### Making Code Changes

1. **I provide instructions** → You copy-paste into Cursor
2. **Cursor suggests changes** → You review and accept
3. **I verify the changes** → You test and commit

### Example Workflow

**Me**: "Add a new function to clear tracked articles"

**You**:
1. Open `app/context_store.py`
2. Use Cmd+K at the end of the file
3. Paste: "Add function clear_tracked_only(sid: str) that deletes only non-pinned articles"
4. Accept the changes
5. Tell me when done

**Me**: ✅ Verifies the implementation

### Debugging Issues

**Me**: "The reader view is showing truncated text"

**You**:
1. Open `templates/reader.html`
2. Use Cmd+K on the text content section
3. Paste: "Check why article text is being truncated. Look for CSS max-height or text overflow issues"
4. Review suggestions
5. Apply fixes

**Me**: ✅ Helps verify the fix

## 🎨 Cursor-Specific Features

### 1. Codebase Context

Cursor can use your entire codebase as context. When you ask questions, it understands:
- Your project structure
- Existing code patterns
- Dependencies and imports
- File relationships

### 2. Multi-file Editing

Cursor can make changes across multiple files simultaneously:
- Update a function and all its callers
- Refactor code across the codebase
- Add features that span multiple files

### 3. Code Generation

Cursor can generate:
- New functions based on existing patterns
- Tests for your code
- Documentation
- Configuration files

## 📝 Best Practices

### 1. Be Specific

**Good**: "Add a DELETE endpoint at /api/context/tracked that clears only non-pinned articles"

**Bad**: "Fix the context API"

### 2. Provide Context

**Good**: "In app/context_api.py, add a new endpoint after the clear endpoint (around line 50)"

**Bad**: "Add an endpoint"

### 3. Review Changes

Always review Cursor's suggestions before accepting:
- Check for syntax errors
- Verify logic is correct
- Ensure it matches your code style
- Test the changes

### 4. Iterate

If Cursor's first suggestion isn't quite right:
- Provide feedback
- Ask for clarification
- Request alternatives
- Refine the request

## 🔄 Working Together

### My Role

1. **Analyze** your codebase and requirements
2. **Provide** exact instructions and code
3. **Verify** changes after you implement them
4. **Debug** issues you encounter
5. **Suggest** improvements and best practices

### Your Role

1. **Execute** instructions in Cursor
2. **Review** suggested changes
3. **Test** the implementation
4. **Provide** feedback on results
5. **Ask** questions when needed

## 💡 Tips for Effective Collaboration

### 1. Share Context

When asking for help, include:
- File paths
- Line numbers
- Error messages
- Expected behavior
- Actual behavior

### 2. Use Git

Commit changes frequently:
```bash
git add .
git commit -m "Add tracked articles clearing feature"
```

This allows us to:
- Track progress
- Roll back if needed
- See what changed
- Test specific versions

### 3. Test Incrementally

After each change:
- Test the feature
- Check for errors
- Verify expected behavior
- Report issues immediately

### 4. Ask Questions

Don't hesitate to ask:
- "Why did you suggest this approach?"
- "How does this work?"
- "What if I want to change X?"
- "Is there a better way?"

## 🎯 Example: Implementing a Feature

### Step 1: I Provide Instructions

**Me**: "Add a function to export tracked articles as CSV"

### Step 2: You Implement in Cursor

**You**:
1. Open `app/context_api.py`
2. Use Cmd+K at the end of the file
3. Paste my instructions
4. Accept changes

### Step 3: I Verify

**Me**: ✅ Checks the implementation, suggests improvements

### Step 4: You Test

**You**: Test the endpoint, report results

### Step 5: Iterate

**Me**: Fix any issues, optimize code

**You**: Apply fixes, test again

### Step 6: Complete

**Me**: ✅ Feature is complete and working

**You**: Commit changes to git

## 🆘 Getting Help

If you're stuck:

1. **Ask me**: "I'm getting an error when..."
2. **Share code**: Paste the relevant code
3. **Describe issue**: What you expected vs what happened
4. **Provide context**: File, line number, error message

## 📚 Additional Resources

- [Cursor Documentation](https://cursor.sh/docs)
- [Cursor Keyboard Shortcuts](https://cursor.sh/docs/shortcuts)
- [Cursor AI Features](https://cursor.sh/docs/features)

## 🎉 Ready to Start

Now you can:
1. ✅ Use Cursor's AI features with my guidance
2. ✅ Implement changes efficiently
3. ✅ Debug issues quickly
4. ✅ Build features collaboratively

Let's build something great! 🚀

