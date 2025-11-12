# �� Agent File Editing Runbook - Trove Files API

**Copy-paste ready commands** to verify, back up, and edit any file in the trove folder via the tunneled Files API.

## 🌐 Base Configuration

# Set the tunnel URL (update if tunnel changes)
URL="https://autographic-jacob-unsalably.ngrok-free.dev"

# Optional: If Files API requires authentication (currently not required)
# KEY="$(grep -E '^FILE_API_KEY=' ~/Projects/trove/.env 2>/dev/null | cut -d= -f2)"
KEY=""

# Helper function to add auth header if KEY is set
H() { [ -n "$KEY" ] && printf ' -H X-File-API-Key:\ %s' "$KEY"; }**Note:** Currently, the Files API does **not** require authentication. The `KEY` mechanism is included for future use if auth is added.

---

## 0️⃣ Quick Setup
sh
# Set variables
URL="https://autographic-jacob-unsalably.ngrok-free.dev"
H() { [ -n "$KEY" ] && printf ' -H X-File-API-Key:\ %s' "$KEY"; }---

## 1️⃣ Explore (Confirm Structure)

List the root directory to understand the project layout:
h
curl -fsS "$URL/api/files/directory?path=" | jq '.items[0:30]'**Drill into subdirectories:**sh
# Explore app directory
curl -fsS "$URL/api/files/directory?path=app" | jq '.items[] | {name, type, path}'

# Explore templates
curl -fsS "$URL/api/files/directory?path=templates" | jq '.items[] | .name'**Use the `path` values from responses to navigate deeper.**

---

## 2️⃣ Read a File (Sanity Check)

Read any file to verify access and see current content:

TARGET="README.md"   # Change to any relative path you want to edit

# Read and display first 40 lines
curl -fsS "$URL/api/files/read?path=${TARGET}" | jq -r '.content' | head -40

# Or get full JSON response
curl -fsS "$URL/api/files/read?path=${TARGET}" | jq '.'**Response format:**
- **Text files:** `content` field contains the file text directly
- **Binary files:** `content` field contains base64-encoded data, `type: "binary"`

**Stick to text files for editing** (`.py`, `.md`, `.json`, `.yaml`, `.html`, `.sh`, etc.)

---

## 3️⃣ Back Up (Server-Side Copy)

Create a timestamped backup before editing:

TARGET="app/main.py"  # File to back up
TS="$(date -u +%Y%m%dT%H%M%SZ)"

# Read original and create backup
curl -fsS "$URL/api/files/read?path=${TARGET}" | \
  jq -r '.content' | \
  curl -fsS -X PUT "$URL/api/files/write?path=${TARGET}.${TS}.bak"$(H) \
    -H 'Content-Type: application/json' \
    -d "{\"content\": $(jq -Rs .), \"encoding\": \"utf-8\", \"create_dirs\": true}" | jq
**Simpler backup (if you have the file content):**
# Read current file to variable
CURRENT=$(curl -fsS "$URL/api/files/read?path=${TARGET}" | jq -r '.content')

# Write backup
curl -fsS -X PUT "$URL/api/files/write?path=${TARGET}.${TS}.bak"$(H) \
  -H 'Content-Type: application/json' \
  -d "{\"content\": $(echo "$CURRENT" | jq -Rs .), \"encoding\": \"utf-8\"}" | jq---

## 4️⃣ Edit a File

### Method A: Simple Append/Modify

TARGET="README.md"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

# Read current content
TMP="$(mktemp)"
curl -fsS "$URL/api/files/read?path=${TARGET}" | jq -r '.content' > "$TMP"

# Modify (example: append diagnostic footer)
printf "\n\n---\nEdited via Files API on %s\n" "$TS" >> "$TMP"

# Write back
curl -fsS -X PUT "$URL/api/files/write?path=${TARGET}"$(H) \
  -H 'Content-Type: application/json' \
  -d "{\"content\": $(jq -Rs . "$TMP"), \"encoding\": \"utf-8\", \"create_dirs\": true}" | jq

rm -f "$TMP"### Method B: Using jq for JSON Manipulation

TARGET="app/config.py"

# Read, modify, write in one pipeline
curl -fsS "$URL/api/files/read?path=${TARGET}" | \
  jq --arg addition "\n# Added via API\nNEW_CONFIG=value" \
     '.content += $addition' | \
  curl -fsS -X PUT "$URL/api/files/write?path=${TARGET}"$(H) \
    -H 'Content-Type: application/json' \
    -d "{\"content\": $(jq -r '.content' | jq -Rs .), \"encoding\": \"utf-8\"}" | jq### Method C: Direct Content Replacement

TARGET="test.txt"
NEW_CONTENT="This is the new file content
With multiple lines
And proper formatting"

curl -fsS -X PUT "$URL/api/files/write?path=${TARGET}"$(H) \
  -H 'Content-Type: application/json' \
  -d "{\"content\": $(echo "$NEW_CONTENT" | jq -Rs .), \"encoding\": \"utf-8\", \"create_dirs\": true}" | jq---

## 5️⃣ Verify Changes
h
TARGET="README.md"

# Check last 5 lines
curl -fsS "$URL/api/files/read?path=${TARGET}" | jq -r '.content' | tail -5

# Or view full file
curl -fsS "$URL/api/files/read?path=${TARGET}" | jq -r '.content'---

## 6️⃣ Roll Back (Restore from Backup)

TARGET="README.md"
TS="20250111T120000Z"  # Use the timestamp from your backup

# Read backup
BACKUP_CONTENT=$(curl -fsS "$URL/api/files/read?path=${TARGET}.${TS}.bak" | jq -r '.content')

# Restore original
curl -fsS -X PUT "$URL/api/files/write?path=${TARGET}"$(H) \
  -H 'Content-Type: application/json' \
  -d "{\"content\": $(echo "$BACKUP_CONTENT" | jq -Rs .), \"encoding\": \"utf-8\"}" | jq---

## 7️⃣ Create New Files
ash
NEW_FILE="scripts/new_script.sh"
CONTENT='#!/bin/bash
echo "Hello from new script"
'

curl -fsS -X PUT "$URL/api/files/write?path=${NEW_FILE}"$(H) \
  -H 'Content-Type: application/json' \
  -d "{\"content\": $(echo "$CONTENT" | jq -Rs .), \"encoding\": \"utf-8\", \"create_dirs\": true}" | jq---

## 8️⃣ Create Directories
sh
NEW_DIR="new_module/submodule"

curl -fsS -X POST "$URL/api/files/mkdir?path=${NEW_DIR}"$(H) \
  -H 'Content-Type: application/json' \
  -d '{"parents": true}' | jq
---

## 9️⃣ Delete Files/Directories

# Delete a file
TARGET="old_file.txt"
curl -fsS -X DELETE "$URL/api/files/delete?path=${TARGET}"$(H) | jq

# Delete a directory (recursive)
TARGET_DIR="old_folder"
curl -fsS -X DELETE "$URL/api/files/delete?path=${TARGET_DIR}&recursive=true"$(H) | jq---

## 📋 Complete Workflow Example

**Task:** Add a comment to `app/main.py` and verify

# Setup
URL="https://autographic-jacob-unsalably.ngrok-free.dev"
TARGET="app/main.py"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

# 1. Explore
curl -fsS "$URL/api/files/directory?path=app" | jq '.items[] | select(.name == "main.py")'

# 2. Read
curl -fsS "$URL/api/files/read?path=${TARGET}" | jq -r '.content' | head -20

# 3. Backup
CURRENT=$(curl -fsS "$URL/api/files/read?path=${TARGET}" | jq -r '.content')
curl -fsS -X PUT "$URL/api/files/write?path=${TARGET}.${TS}.bak" \
  -H 'Content-Type: application/json' \
  -d "{\"content\": $(echo "$CURRENT" | jq -Rs .), \"encoding\": \"utf-8\"}" | jq

# 4. Edit (prepend comment)
NEW_CONTENT="# Edited via Files API on $TS
$CURRENT"
curl -fsS -X PUT "$URL/api/files/write?path=${TARGET}" \
  -H 'Content-Type: application/json' \
  -d "{\"content\": $(echo "$NEW_CONTENT" | jq -Rs .), \"encoding\": \"utf-8\"}" | jq

# 5. Verify
curl -fsS "$URL/api/files/read?path=${TARGET}" | jq -r '.content' | head -5
---

## 🎯 One-Liner Examples

**Append to file:**
TARGET="README.md"; curl -fsS "$URL/api/files/read?path=${TARGET}" | jq -r '.content' | sed '$a\New line' | curl -fsS -X PUT "$URL/api/files/write?path=${TARGET}" -H 'Content-Type: application/json' -d "{\"content\": $(jq -Rs .), \"encoding\": \"utf-8\"}" | jq**Replace string in file:**
TARGET="config.py"; curl -fsS "$URL/api/files/read?path=${TARGET}" | jq -r '.content' | sed 's/old_value/new_value/g' | curl -fsS -X PUT "$URL/api/files/write?path=${TARGET}" -H 'Content-Type: application/json' -d "{\"content\": $(jq -Rs .), \"encoding\": \"utf-8\"}" | jq**Add line after pattern:**
TARGET="app/main.py"; curl -fsS "$URL/api/files/read?path=${TARGET}" | jq -r '.content' | sed '/pattern/a\new line here' | curl -fsS -X PUT "$URL/api/files/write?path=${TARGET}" -H 'Content-Type: application/json' -d "{\"content\": $(jq -Rs .), \"encoding\": \"utf-8\"}" | jq---

## ⚠️ Important Notes

1. **Paths are relative to trove root:**
   - ✅ Correct: `app/main.py`, `templates/base.html`
   - ❌ Wrong: `/app/main.py`, `../app/main.py`, absolute paths

2. **File encoding:**
   - Text files: Use `"encoding": "utf-8"` (default)
   - Binary files: Use `"encoding": "base64"` (not recommended for editing)

3. **Error codes:**
   - `404`: File/directory not found
   - `400`: Invalid request
   - `403`: Path outside trove directory (security)
   - `500`: Server error

4. **Auto-reload:**
   - App runs with `--reload` flag
   - Python file changes trigger automatic server restart
   - No manual restart needed

5. **Tunnel URL:**
   - Current: `https://autographic-jacob-unsalably.ngrok-free.dev`
   - Free tunnels expire after 2 hours
   - Get current URL: `curl http://127.0.0.1:8000/api/tunnel/public-url`

---

## 📚 API Endpoints Summary

| Action | Method | Endpoint | Auth Required |
|--------|--------|----------|---------------|
| List directory | GET | `/api/files/directory?path=` | No |
| Read file | GET | `/api/files/read?path=` | No |
| Write/Edit file | PUT | `/api/files/write?path=` | No |
| Create directory | POST | `/api/files/mkdir?path=` | No |
| Delete file/dir | DELETE | `/api/files/delete?path=` | No |

**All endpoints:** `https://autographic-jacob-unsalably.ngrok-free.dev/api/files/...`

---

## 🚀 Quick Reference Card

# Setup
URL="https://autographic-jacob-unsalably.ngrok-free.dev"

# List
curl -fsS "$URL/api/files/directory?path=" | jq

# Read
curl -fsS "$URL/api/files/read?path=FILE" | jq -r '.content'

# Write
curl -fsS -X PUT "$URL/api/files/write?path=FILE" \
  -H 'Content-Type: application/json' \
  -d '{"content": "TEXT", "encoding": "utf-8"}'

# Delete
curl -fsS -X DELETE "$URL/api/files/delete?path=FILE"
---

**Ready to edit?** Tell me the **exact path + edit** you want (e.g., "append config flag to `app/main.py`"), and I'll return a one-liner that performs that exact change.
