# 📚 Archive Detective - Complete Features & Functions List

## 🌐 Web Pages & Routes

### Main Pages
- **`/`** - Main search page with advanced filters
- **`/chat`** - Archive Detective chat interface
- **`/reporter`** - Report preview and PDF generation page
- **`/status`** - Status page showing all generated files
- **`/health`** - Health check endpoint

## 🔍 Search Features

### Trove Search
- **Search Categories**: newspaper, magazine, book, image, research, diary, music, list, people, all
- **Advanced Filters**:
  - Date range slider (1800-2024)
  - Format filter (e.g., Photograph, Map, Thesis)
  - Art Type filter (for images)
  - Place filter (e.g., Australia/New South Wales)
  - Sort by: Relevance, Date (Oldest/Newest First)
  - Results per page (10-100)
- **Image Display**: Toggle image thumbnails on/off
- **Pagination**: Navigate through search results
- **Active Filters**: Visual chips showing active filters with remove buttons

## 🤖 Archive Detective Chat Commands

### Search Commands
- **`/search <query>`** - Search Trove archives directly
  - Example: `/search gold locations NSW`
  - Natural language: "search for gold", "find articles about Grafton"
- **Smart Search Detection**: Automatically detects search intent from natural language

### Article Management
- **`/read <article_id>`** - Read full text of a Trove article
  - Example: `/read 12345678`
  - Natural language: "read article 12345678"
- **`/summarize <article_id>` or `/summarize <text>`** - Create AI summaries
  - Uses OpenAI if available, fallback to extractive summarization
  - Natural language: "summarize this article"

### Image Saving
- **`/save-image <url>`** or **`/fetch-image <url>`** - Download and save images from State Library NSW
  - Example: `/save-image https://digital.sl.nsw.gov.au/delivery/DeliveryManagerServlet?dps_pid=IE1863657`
  - Saves to `outputs/images/` directory
  - Accessible via `/files/images/filename.jpg`

### Report Building
- **`/add-to-report <article_id>`** - Add article to report with summary
  - Natural language: "add to report", "add this to report"
- **`/report-view`** - View current report items
  - Natural language: "show report", "view report"
- **`/report-pdf`** - Generate PDF report
  - Natural language: "generate PDF", "create PDF report"
- **Report Features**:
  - Multiple articles per report
  - Auto-generated summaries
  - PDF export with ReportLab
  - Print-friendly format

### Research Tools
- **`/generate-queries`** - Generate Trove CSV queries for property research
  - Creates CSV file with search queries
  - Natural language: "generate queries for 12A Clarence St"
- **`/make-brief`** - Create PDF brief template
  - Generates professional brief template
- **`/harvest-stub`** - Create owner timeline CSV
  - Timeline management for property research
- **`/report`** - Generate placeholder report

### Help
- **`/help`** - Show all available commands and features

## 📄 Article Features

### Read Aloud (Text-to-Speech)
- **Browser-based TTS** using `speechSynthesis` API
- **Features**:
  - Strips HTML tags automatically
  - Waits for voices to load
  - Quality voice selection (prefers Google/Enhanced voices)
  - Error handling and user feedback
  - Button state management (Loading → Reading → Done)

### Article Summarization
- **LLM-based**: Uses OpenAI GPT models if available
- **Fallback**: Extractive summarization (sentence scoring)
- **Output**: Bullet-point summaries

### Article Actions (from Search Results)
- **🔊 Read Aloud** - Text-to-speech
- **📝 Summarize** - Create summary
- **➕ Add to Report** - Add to report with summary

## 📊 Report System

### Report Builder
- **Add Items**: Articles with titles, dates, URLs, text, summaries
- **View Report**: Preview all items in report
- **Clear Report**: Remove all items
- **PDF Generation**: Professional PDF reports with ReportLab
- **Print Support**: Print-friendly formatting

### Report Storage
- **Location**: `outputs/report.json`
- **Web Access**: `/files/outputs/report.pdf`

## 🖼️ Image Management

### State Library NSW Integration
- **Extract Images**: Parses State Library NSW viewer URLs
- **Download**: Fetches images from SLNSW servers
- **Save**: Stores to `outputs/images/` directory
- **Web Access**: Accessible via `/files/images/`
- **Format Detection**: Auto-detects JPG, PNG, GIF, WebP

## 📱 Mobile Features

### QR Code Connection
- **QR Code Generator**: Creates QR codes for mobile connection
- **Tunnel Support**: Works with ngrok tunnels
- **Local Network**: Falls back to local IP
- **Mobile App**: Connect via QR code scan

### Mobile UI
- **Modern Chat Interface**: WhatsApp/iMessage-style bubbles
- **Responsive Design**: Optimized for mobile screens
- **Sticky Elements**: Header and input bar stay visible
- **Touch-Friendly**: Large touch targets

## 🔧 Technical Features

### API Endpoints

#### Search & Articles
- **`GET /`** - Main search page
- **`GET /api/trove/item_text?id=...`** - Fetch article full text
- **`POST /api/summarize`** - Summarize text
- **`POST /api/chat`** - Chat endpoint (all commands)

#### Reports
- **`POST /api/report/add`** - Add item to report
- **`GET /api/report`** - Get current report
- **`POST /api/report/clear`** - Clear report
- **`GET /api/report/pdf`** - Generate PDF

#### Images
- **`GET /files/images/<filename>`** - Access saved images

#### System
- **`GET /health`** - Health check
- **`GET /api/local-ip`** - Get local network IP
- **`GET /api/qrcode`** - Generate QR code
- **`GET /api/tunnel/status`** - Check tunnel status
- **`POST /api/tunnel/start`** - Start ngrok tunnel

### File Management

#### Generated Files
- **Queries**: `queries/trove_queries.csv`
- **Briefs**: `docs/brief_*.pdf`
- **Reports**: `outputs/report.json`, `outputs/report_*.pdf`
- **Timelines**: `outputs/owner_timeline.csv`
- **Images**: `outputs/images/*.jpg|png|gif|webp`

#### File Access
- **Static Files**: `/static/` - CSS, JS, assets
- **Generated Files**: `/files/` - Reports, images, CSVs
  - `/files/queries/` - CSV queries
  - `/files/docs/` - PDF briefs
  - `/files/outputs/` - Reports and timelines
  - `/files/images/` - Saved images

## 🎨 UI Features

### Search Page
- **Sticky Search Form**: Stays at top when scrolling
- **Collapsible Filters**: Hidden by default, toggle to show
- **Compact Mode**: Reduces size on scroll
- **Quick Search Bar**: Always visible search input
- **Active Filter Chips**: Visual representation of filters
- **Results Grid**: Responsive card layout
- **Sticky Pagination**: Always accessible at bottom

### Chat Interface
- **Modern Message Bubbles**: 
  - User messages: Blue gradient, right-aligned
  - Bot messages: Dark, left-aligned
- **Typing Indicator**: Animated dots while processing
- **Quick Actions**: Buttons for common commands
- **Help Modal**: Command reference
- **Timeline Editor**: Inline CSV editor

### Mobile Optimizations
- **Full-Screen Chat**: Optimized mobile layout
- **Touch Targets**: Large, easy-to-tap buttons
- **Responsive Grid**: Adapts to screen size
- **Smooth Scrolling**: Better mobile experience

## 🤖 AI Features

### OpenAI Integration
- **Chat Routing**: Natural language to command conversion
- **Summarization**: LLM-based article summaries
- **Action-Oriented**: Executes commands immediately
- **Context Awareness**: Understands user intent

### Fallback Systems
- **Extractive Summarization**: Works without OpenAI
- **Smart Search Detection**: Keyword-based fallback
- **Error Handling**: Graceful degradation

## 🔐 Security & Configuration

### Environment Variables
- **`TROVE_API_KEY`** - Trove API key (required)
- **`OPENAI_API_KEY`** - OpenAI API key (optional)
- **`ARCHIVE_DETECTIVE_ENABLED`** - Enable/disable Archive Detective
- **`MOBILE_API_BASE`** - Mobile API server URL

### Error Handling
- **Configuration Errors**: Clear messages for missing keys
- **Network Errors**: Graceful handling of API failures
- **Validation**: Input validation and sanitization

## 📈 Performance Features

### Optimizations
- **Lazy Loading**: Images load on demand
- **Async Operations**: Non-blocking API calls
- **Caching**: File system caching for generated content
- **Pagination**: Efficient result handling

### Code Quality
- **Type Safety**: Full type hints
- **Linting**: ruff, black, mypy
- **Testing**: pytest smoke tests
- **CI/CD**: GitHub Actions (optional)

## 🚀 Deployment Features

### Mobile Connection
- **QR Code**: Easy mobile connection
- **Tunnel Support**: ngrok integration
- **Local Network**: Works on same WiFi
- **Public Access**: Via tunnel URLs

### Development Tools
- **Hot Reload**: Auto-reload on code changes
- **Health Checks**: System status monitoring
- **Logging**: Comprehensive logging system

---

## 📝 Summary

**Total Features**: 50+
**Main Categories**: 
- Search (10+ features)
- Chat Commands (15+ commands)
- Article Management (5+ features)
- Report Building (5+ features)
- Image Management (3+ features)
- Mobile Support (5+ features)
- UI/UX (10+ features)

**Key Strengths**:
- ✅ Action-oriented AI chat
- ✅ Comprehensive Trove search
- ✅ Professional report generation
- ✅ Mobile-first design
- ✅ Modern UI/UX
- ✅ Flexible image handling

