from __future__ import annotations
from io import BytesIO
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import Response, JSONResponse

try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False

router = APIRouter(prefix="/api", tags=["qrcode"])


@router.get("/qrcode")
async def get_qrcode(url: str = Query(None)):
    """Generate QR code for a URL (defaults to current API base or tunnel URL)."""
    if not QRCODE_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={"error": "qrcode library not installed", "message": "Install with: pip install qrcode[pil]"}
        )
    
    if not url:
        # Try to get tunnel URL from tunnel service
        try:
            from ..routers.tunnel import get_tunnel_status
            tunnel_status = await get_tunnel_status()
            if tunnel_status.get("ok") and tunnel_status.get("url"):
                url = tunnel_status["url"]
            else:
                # Fallback to local
                url = "http://127.0.0.1:8000"
        except Exception:
            # Fallback if tunnel service fails
            url = "http://127.0.0.1:8000"
    
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

