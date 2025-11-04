import json
import os
from io import BytesIO

import qrcode
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from starlette.exceptions import HTTPException as StarletteHTTPException

from .models import SearchQuery, SummaryRequest
from .trove import parse_article_id, trove_article, trove_search

app = FastAPI(title="Archive Detective API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle 404 errors by redirecting to root landing page"""
    if exc.status_code == 404:
        # Redirect to root for better UX when scanning QR codes
        return RedirectResponse(url="/", status_code=302)
    # For other HTTP errors, return JSON response
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


LEXICON = None
def load_lexicon():
    global LEXICON
    if LEXICON: return LEXICON
    path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "..","..","packages","lexicon","historical_terms.json"
    )
    path = os.path.abspath(path)
    try:
        with open(path, encoding="utf-8") as f:
            LEXICON = json.load(f)
    except FileNotFoundError:
        LEXICON = {"entries": []}
    return LEXICON


def expand_query(q: str, sensitive: bool) -> str:
    if not sensitive: return q
    lex = load_lexicon()
    expansions = []
    L = q.lower()
    for entry in lex.get("entries", []):
        if any(k in L for k in entry.get("triggers", [])):
            expansions += entry.get("include_terms", [])
    if expansions:
        # boolean OR expansion
        exp = " OR ".join(sorted(set([f'"{t}"' if " " in t else t for t in expansions])))
        return f"({q}) OR ({exp})"
    return q


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    """Root endpoint - landing page for mobile API connection."""
    base_url = f"{request.url.scheme}://{request.url.hostname}"
    if request.url.port:
        base_url += f":{request.url.port}"
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Archive Detective Mobile API</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            .container {{
                background: white;
                border-radius: 20px;
                padding: 40px;
                max-width: 500px;
                width: 100%;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                text-align: center;
            }}
            h1 {{
                color: #333;
                margin-bottom: 10px;
                font-size: 28px;
            }}
            .status {{
                display: inline-block;
                background: #10b981;
                color: white;
                padding: 6px 16px;
                border-radius: 20px;
                font-size: 14px;
                font-weight: 600;
                margin-bottom: 30px;
            }}
            .url-box {{
                background: #f3f4f6;
                border: 2px solid #e5e7eb;
                border-radius: 12px;
                padding: 20px;
                margin: 30px 0;
                word-break: break-all;
                font-family: 'Courier New', monospace;
                font-size: 16px;
                color: #1f2937;
                font-weight: 600;
            }}
            .instructions {{
                text-align: left;
                background: #eff6ff;
                border-left: 4px solid #3b82f6;
                padding: 20px;
                border-radius: 8px;
                margin: 20px 0;
            }}
            .instructions h3 {{
                color: #1e40af;
                margin-bottom: 12px;
                font-size: 18px;
            }}
            .instructions ol {{
                margin-left: 20px;
                color: #374151;
                line-height: 1.8;
            }}
            .instructions li {{
                margin-bottom: 8px;
            }}
            .code {{
                background: #1f2937;
                color: #10b981;
                padding: 4px 8px;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 14px;
            }}
            .copy-btn {{
                background: #3b82f6;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                margin-top: 10px;
                width: 100%;
                transition: background 0.2s;
            }}
            .copy-btn:hover {{
                background: #2563eb;
            }}
            .copy-btn:active {{
                transform: scale(0.98);
            }}
            .success {{
                display: none;
                background: #10b981;
                color: white;
                padding: 12px;
                border-radius: 8px;
                margin-top: 10px;
                font-weight: 600;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📱 Archive Detective API</h1>
            <div class="status">✅ Online</div>
            
            <div class="url-box" id="apiUrl">{base_url}</div>
            
            <button class="copy-btn" onclick="copyUrl()">📋 Copy URL</button>
            <div class="success" id="successMsg">✅ Copied to clipboard!</div>
            
            <div class="instructions">
                <h3>🔧 How to Connect Your Mobile App:</h3>
                <ol>
                    <li>Copy the API URL above</li>
                    <li>In your Expo app, set: <span class="code">EXPO_PUBLIC_API_BASE</span></li>
                    <li>Or use: <span class="code">export EXPO_PUBLIC_API_BASE="{base_url}"</span></li>
                    <li>Restart your Expo app</li>
                </ol>
            </div>
        </div>
        
        <script>
            function copyUrl() {{
                const url = document.getElementById('apiUrl').textContent;
                navigator.clipboard.writeText(url).then(() => {{
                    const msg = document.getElementById('successMsg');
                    msg.style.display = 'block';
                    setTimeout(() => {{
                        msg.style.display = 'none';
                    }}, 2000);
                }});
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/api", response_class=JSONResponse)
def api_root():
    """API root endpoint - returns JSON info."""
    return {
        "name": "Archive Detective Mobile API",
        "version": "1.0.0",
        "status": "online",
        "message": "Mobile API is running. Use this URL as EXPO_PUBLIC_API_BASE in your mobile app.",
        "endpoints": {
            "ping": "/api/ping",
            "search": "/api/trove/search",
            "article": "/api/trove/article",
            "summarize": "/api/summarize",
            "tunnel_status": "/api/tunnel/status",
            "tunnel_start": "/api/tunnel/start",
        },
        "instructions": "In your Expo app, set EXPO_PUBLIC_API_BASE to this URL (including http:// or https://)"
    }


@app.get("/api/ping")
def ping():
    return {"ok": True}


@app.post("/api/trove/search")
def api_search(body: SearchQuery):
    try:
        q2 = expand_query(body.q, body.sensitive_mode)
        items = trove_search(q2, n=body.n,
                             date_from=body.date_from,
                             date_to=body.date_to,
                             state=body.state)
        return {"ok": True, "query_used": q2, "items": items}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/trove/article")
def api_article(id_or_url: str = Query(...), pdf: bool = False):
    try:
        aid = parse_article_id(id_or_url)
        art = trove_article(aid)
        if not pdf:
            return {"ok": True, "article": art}
        # quick PDF (printable)
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        width, height = A4
        y = height - 50
        title = (art.get("heading") or art.get("title") or f"Trove article {aid}")[:120]
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width/2, y, title); y -= 20
        meta = f"{art.get('date','')}  |  Page {art.get('page','')}  |  {art.get('troveUrl','')}"
        c.setFont("Helvetica", 9); c.drawCentredString(width/2, y, meta); y -= 20
        c.setFont("Times-Roman", 11)
        for line in art.get("text","").splitlines():
            for chunk in [line[i:i+100] for i in range(0,len(line),100)]:
                if y < 50: c.showPage(); y=height-50; c.setFont("Times-Roman", 11)
                c.drawString(50, y, chunk); y -= 14
        c.showPage(); c.save(); buf.seek(0)
        return StreamingResponse(buf, media_type="application/pdf",
                                 headers={"Content-Disposition": f'inline; filename="trove_{aid}.pdf"'})
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/summarize")
def api_summarize(body: SummaryRequest):
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise HTTPException(503, "Summaries disabled: OPENAI_API_KEY missing.")
    # minimal, model-agnostic call using responses endpoint style (pseudo)
    import requests
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
          "model": "gpt-4o-mini",
          "messages": [
            {"role": "system", "content": "Summarize faithfully with neutral tone. Include 2-4 bullet key points."},
            {"role": "user", "content": body.text[:12000]}
          ],
          "max_tokens": 400
        },
        timeout=60
    )
    resp.raise_for_status()
    out = resp.json()["choices"][0]["message"]["content"]
    return {"ok": True, "summary": out}


# Tunnel management - using improved tunnel service
from .tunnel_service import get_tunnel_status, start_tunnel, stop_tunnel


@app.post("/api/tunnel/start")
async def api_start_tunnel():
    """Start ngrok tunnel and return public URL."""
    port = int(os.getenv("API_PORT", "8001"))
    result = await start_tunnel(port)
    return result

@app.get("/api/tunnel/status")
async def api_tunnel_status():
    """Get current tunnel status with health check."""
    result = await get_tunnel_status()
    return result

@app.post("/api/tunnel/stop")
async def api_stop_tunnel():
    """Stop ngrok tunnel."""
    result = await stop_tunnel()
    return result


@app.get("/api/qrcode")
async def get_qrcode(url: str = Query(None)):
    """Generate QR code for a URL (defaults to current API base or tunnel URL)"""
    if not url:
        # Try to get tunnel URL from tunnel service
        try:
            tunnel_status = await get_tunnel_status()
            if tunnel_status.get("ok") and tunnel_status.get("url"):
                url = tunnel_status["url"]
            else:
                # Fallback to local
                url = "http://127.0.0.1:8001"
        except Exception:
            # Fallback if tunnel service fails
            url = "http://127.0.0.1:8001"
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to bytes
    img_bytes = BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    
    return Response(content=img_bytes.read(), media_type="image/png")

