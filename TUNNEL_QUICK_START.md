# 🌐 Tunnel Quick Start Guide

## Current Status

You have **3 ngrok tunnels** already running (free plan limit). Here's how to use them:

## Option 1: Use Existing Tunnel (Recommended)

If you already have a tunnel pointing to port 8000, you can use it:

1. **Check existing tunnels:**
   ```bash
   python3 -c "from pyngrok import ngrok; tunnels = ngrok.get_tunnels(); [print(f'{t.public_url} -> {t.config[\"addr\"]}') for t in tunnels]"
   ```

2. **Find tunnel for port 8000:**
   - Look for a tunnel pointing to `localhost:8000` or `http://localhost:8000`
   - Copy the public URL (e.g., `https://abc123.ngrok.io`)

3. **Use in QR modal:**
   - Click "📱 Connect" in the web app header
   - Paste the tunnel URL in the "Web App URL" field
   - Click "Update QR Code"
   - Scan the QR code!

## Option 2: Kill Existing Tunnels & Start New

If you want a fresh tunnel:

```bash
# Kill all ngrok processes
pkill ngrok

# Or kill specific tunnel
ngrok api tunnels delete <tunnel-id>

# Then start fresh
ngrok http 8000
```

Then use the new URL in the QR modal.

## Option 3: Use Local Network (Same WiFi)

If you're on the same WiFi network:

1. **Get your local IP:**
   ```bash
   ip addr show | grep "inet " | grep -v 127.0.0.1
   # Or visit: http://127.0.0.1:8000/api/local-ip
   ```

2. **Use in QR modal:**
   - Click "📱 Connect"
   - Enter: `http://YOUR_LOCAL_IP:8000` (e.g., `http://192.168.1.100:8000`)
   - Click "Update QR Code"
   - Scan!

## Option 4: ngrok Configuration File (Multiple Tunnels)

Create `~/.ngrok2/ngrok.yml`:

```yaml
version: "2"
authtoken: YOUR_AUTH_TOKEN
tunnels:
  webapp:
    addr: 8000
    proto: http
  api:
    addr: 8001
    proto: http
```

Then run:
```bash
ngrok start --all
```

This starts both tunnels in one session (counts as 1 tunnel).

## Quick Access via Web UI

1. **Open web app:** http://127.0.0.1:8000
2. **Click "📱 Connect"** button in header
3. **Click "🌐 Start Public Tunnel"** (if you have tunnel slots)
4. **Or paste existing tunnel URL** in the input field
5. **Scan QR code** with your phone!

## Troubleshooting

### "3 tunnels limit" error
- Free ngrok plan allows 3 simultaneous tunnels
- Kill existing: `pkill ngrok` or use `ngrok api tunnels list` then delete
- Or use configuration file approach (Option 4)

### QR code shows wrong URL
- Click "🔄 Refresh" in the modal
- Manually enter the correct tunnel URL
- Click "Update QR Code"

### Mobile can't connect
- Check tunnel is active: Visit tunnel URL in browser first
- Verify tunnel points to port 8000 (not 8001)
- Try refreshing the QR code

### Tunnel expires
- Free tunnels expire after 2 hours
- Just restart: Click "🌐 Start Public Tunnel" again
- Or run: `ngrok http 8000`

## Pro Tips

1. **Use the web UI** - It automatically detects tunnels and updates QR codes
2. **Local network is faster** - If on same WiFi, use local IP instead of tunnel
3. **Save tunnel URL** - Copy it for easy reuse
4. **Tunnel for API too** - If using mobile app, you may need port 8001 tunnel as well

---

**Quick Command:**
```bash
# Start tunnel manually
ngrok http 8000

# Then visit: http://127.0.0.1:8000
# Click "📱 Connect" → Use the tunnel URL shown
```

