# Mobile App Features Checklist

## ✅ Implemented Features

### SearchScreen
- ✅ Search input field
- ✅ Search button (just added)
- ✅ QR/Tunnel button (top right - blue button with "🔗 QR")
- ✅ Sensitive Research Mode toggle
- ✅ Sensitive Mode banner (shows when enabled)
- ✅ Loading indicator
- ✅ Query used display
- ✅ Results list (FlatList)
- ✅ Result items (clickable)

### ArticleScreen
- ✅ Back button
- ✅ Article title/heading
- ✅ Article metadata (date, page)
- ✅ Summarize button
- ✅ Read Aloud button (TTS)
- ✅ Print/Export button (PDF)
- ✅ Summary display area
- ✅ Full article text

### Components
- ✅ TunnelQRModal - QR code display for API connection
- ✅ TermModeBanner - Warning banner for sensitive mode
- ✅ ResultItem - Individual search result display

### API Integration
- ✅ Search endpoint
- ✅ Article fetch endpoint
- ✅ Summarize endpoint
- ✅ Tunnel management endpoints
- ✅ QR code generation endpoint

## 🎨 UI Elements You Should See

1. **Top Bar**: "Archive Detective" title + blue "🔗 QR" button (top right)
2. **Search Area**: Text input + "Search" button
3. **Sensitive Mode**: Toggle switch + warning banner (when enabled)
4. **Results**: List of clickable articles
5. **QR Modal**: Opens when you tap "🔗 QR" button

## 🔍 Troubleshooting

If QR button not visible:
- Check if app is running (restart Expo)
- Button is blue with white text "🔗 QR" in top right
- Try tapping the top-right area even if button looks small

If search not working:
- Make sure API is running on port 8001
- Check EXPO_PUBLIC_API_BASE environment variable
- Check console for errors

