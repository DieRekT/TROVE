# 📁 File Sharing API - Trove Folder Access

The trove folder is now accessible through a tunnel with **read-write permissions** for agent file editing.

## 🌐 Tunnel URL

**Public URL:** `https://autographic-jacob-unsalably.ngrok-free.dev`

The tunnel is active and the app is running on port 8000.

## 📋 API Endpoints

All endpoints are available at: `https://autographic-jacob-unsalably.ngrok-free.dev/api/files/...`

### 1. List Directory Contents
**GET** `/api/files/directory?path=<directory_path>`

List files and directories in the specified path (relative to trove root).

**Example:**
```bash
curl "https://autographic-jacob-unsalably.ngrok-free.dev/api/files/directory?path=app"
```

**Response:**
```json
{
  "ok": true,
  "path": "app",
  "items": [
    {
      "name": "main.py",
      "path": "app/main.py",
      "type": "file",
      "size": 123456,
      "modified": 1234567890.123
    },
    {
      "name": "config.py",
      "path": "app/config.py",
      "type": "file",
      "size": 5432,
      "modified": 1234567890.123
    }
  ]
}
```

### 2. Read File
**GET** `/api/files/read?path=<file_path>`

Read a file. Returns text for text files, base64 for binary files.

**Example:**
```bash
curl "https://autographic-jacob-unsalably.ngrok-free.dev/api/files/read?path=README.md"
```

**Response (text file):**
```json
{
  "ok": true,
  "path": "README.md",
  "content": "# Trove Project\n...",
  "encoding": "utf-8",
  "type": "text"
}
```

**Response (binary file):**
```json
{
  "ok": true,
  "path": "image.png",
  "content": "iVBORw0KGgoAAAANSUhEUgAA...",
  "encoding": "base64",
  "type": "binary"
}
```

### 3. Write/Edit File
**PUT** `/api/files/write?path=<file_path>`

Write or update a file. Supports both text and binary (base64) content.

**Example (text file):**
```bash
curl -X PUT "https://autographic-jacob-unsalably.ngrok-free.dev/api/files/write?path=test.txt" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Hello, World!",
    "encoding": "utf-8",
    "create_dirs": true
  }'
```

**Example (binary file):**
```bash
curl -X PUT "https://autographic-jacob-unsalably.ngrok-free.dev/api/files/write?path=image.png" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "iVBORw0KGgoAAAANSUhEUgAA...",
    "encoding": "base64",
    "create_dirs": true
  }'
```

**Response:**
```json
{
  "ok": true,
  "path": "test.txt",
  "message": "File written successfully"
}
```

### 4. Create Directory
**POST** `/api/files/mkdir?path=<directory_path>`

Create a directory (and parent directories if needed).

**Example:**
```bash
curl -X POST "https://autographic-jacob-unsalably.ngrok-free.dev/api/files/mkdir?path=new_folder/subfolder" \
  -H "Content-Type: application/json" \
  -d '{"parents": true}'
```

**Response:**
```json
{
  "ok": true,
  "path": "new_folder/subfolder",
  "message": "Directory created successfully"
}
```

### 5. Delete File or Directory
**DELETE** `/api/files/delete?path=<path>&recursive=<true|false>`

Delete a file or directory.

**Example:**
```bash
# Delete a file
curl -X DELETE "https://autographic-jacob-unsalably.ngrok-free.dev/api/files/delete?path=test.txt"

# Delete a directory (recursive)
curl -X DELETE "https://autographic-jacob-unsalably.ngrok-free.dev/api/files/delete?path=old_folder&recursive=true"
```

**Response:**
```json
{
  "ok": true,
  "path": "test.txt",
  "message": "Deleted successfully"
}
```

## 🔒 Security

- All paths are validated to ensure they stay within the trove directory
- Directory traversal attacks are prevented
- Paths are relative to the trove root directory

## 📝 Notes

- The app is running and will auto-reload on code changes
- The tunnel URL may change if ngrok restarts (free tunnels expire after 2 hours)
- To get the current tunnel URL, check: `http://127.0.0.1:8000/api/tunnel/public-url`
- Text files are automatically detected by extension
- Binary files are encoded/decoded using base64

## 🚀 Quick Test

Test the API with:
```bash
# List root directory
curl "https://autographic-jacob-unsalably.ngrok-free.dev/api/files/directory?path="

# Read a file
curl "https://autographic-jacob-unsalably.ngrok-free.dev/api/files/read?path=README.md"

# Write a test file
curl -X PUT "https://autographic-jacob-unsalably.ngrok-free.dev/api/files/write?path=test_agent.txt" \
  -H "Content-Type: application/json" \
  -d '{"content": "This file was created by an agent!", "encoding": "utf-8"}'
```

## 📱 For Agents

Agents can use these endpoints to:
- Browse the codebase structure
- Read source files
- Edit files (create, update, delete)
- Create new directories
- Work with both text and binary files

All operations are scoped to the `/home/lucifer/Projects/trove` directory for security.

