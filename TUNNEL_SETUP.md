# 🌐 Tunnel Setup for Mobile Connection

Connect your iPhone from anywhere (mobile network, different WiFi, etc.) using ngrok tunnels.

## Quick Start

### 1. Start the Servers

**Terminal 1 - Main Web App (port 8000):**
```bash
cd /home/lucifer/Projects/trove
bash run.sh
```

**Terminal 2 - Mobile API Server (port 8001):**
```bash
cd /home/lucifer/Projects/trove/apps/api
bash run.sh
```

### 2. Start a Tunnel (Two Options)

#### Option A: From Web UI (Easiest)
1. Open http://127.0.0.1:8000 in your browser
2. Click **"📱 Connect"** button in the header
3. Click **"🌐 Start Public Tunnel"** button
4. Wait for confirmation - the QR code will update automatically!

#### Option B: From Mobile API Server
```bash
# Make sure ngrok is installed
pip install pyngrok

# Or use the API endpoint
curl -X POST http://127.0.0.1:8001/api/tunnel/start
```

### 3. Scan QR Code

1. The QR code in the modal will show the public tunnel URL (e.g., `https://abc123.ngrok.io`)
2. Scan with your iPhone camera or QR scanner
3. Your mobile app will connect from anywhere! 📱

## How It Works

- **Local Network**: Use your PC's IP (e.g., `http://192.168.20.10:8001`) - only works on same WiFi
- **Public Tunnel**: Use ngrok URL (e.g., `https://abc123.ngrok.io`) - works from anywhere!

The QR code automatically switches to the tunnel URL when available.

## Troubleshooting

### Tunnel Won't Start
- Make sure `pyngrok` is installed: `pip install pyngrok`
- Check if ngrok is configured (may need auth token)
- The mobile API server must be running on port 8001

### Mobile App Can't Connect
- Check tunnel status in the QR modal
- Make sure the tunnel URL is correct
- Try refreshing the tunnel status

### expo-asset Error
```bash
cd /home/lucifer/Projects/trove/apps/mobile
npm install expo-asset
```

## Notes

- Free ngrok tunnels expire after 2 hours
- For permanent tunnels, use ngrok paid plan or self-hosted ngrok
- Tunnel URLs change each time you restart ngrok

