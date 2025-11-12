from __future__ import annotations
import os
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/tunnel", tags=["tunnel"])
logger = logging.getLogger(__name__)


@router.get("/status", response_class=JSONResponse)
async def get_tunnel_status():
    """Check if ngrok tunnel is active for this server."""
    # Try pyngrok (most reliable if installed)
    try:
        from pyngrok import ngrok
        tunnels = ngrok.get_tunnels()
        if tunnels:
            # Find tunnel pointing to our port (8000)
            port = int(os.getenv("PORT", "8000"))
            for tunnel in tunnels:
                addr = tunnel.config.get("addr", "")
                if f":{port}" in addr or f"localhost:{port}" in addr:
                    return {"ok": True, "url": tunnel.public_url}
            # Fallback: return first tunnel
            if tunnels:
                return {"ok": True, "url": tunnels[0].public_url}
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"pyngrok check failed: {e}")
    
    # Fallback: check ngrok local API
    try:
        import httpx
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get("http://127.0.0.1:4040/api/tunnels")
            if response.status_code == 200:
                data = response.json()
                tunnels = data.get("tunnels", [])
                port = int(os.getenv("PORT", "8000"))
                for tunnel in tunnels:
                    addr = tunnel.get("config", {}).get("addr", "")
                    if f":{port}" in addr or f"localhost:{port}" in addr:
                        return {"ok": True, "url": tunnel.get("public_url")}
                if tunnels:
                    return {"ok": True, "url": tunnels[0].get("public_url")}
    except Exception:
        pass
    
    return {"ok": False, "url": None, "message": "No tunnel active. Click 'Start Tunnel' to create one."}


@router.post("/start", response_class=JSONResponse)
async def start_tunnel():
    """Start (or restart) an ngrok tunnel for this server."""
    try:
        from pyngrok import conf, exception, ngrok
    except ImportError:
        return JSONResponse(
            status_code=503,
            content={
                "ok": False,
                "error": "pyngrok not installed",
                "message": (
                    "Install pyngrok: pip install pyngrok\n"
                    "Or run ngrok manually: ngrok http 8000"
                ),
            }
        )
    
    port = int(os.getenv("PORT", "8000"))
    
    # Get authtoken from env or config file
    authtoken = (
        os.getenv("NGROK_AUTHTOKEN")
        or os.getenv("NGROK_TOKEN")
        or os.getenv("NGROK_AUTH_TOKEN")
    )
    region = os.getenv("NGROK_REGION")
    
    try:
        if authtoken:
            conf.get_default().auth_token = authtoken
        elif not Path.home().joinpath(".ngrok2", "ngrok.yml").exists():
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": "ngrok authtoken missing",
                    "message": (
                        "ngrok authtoken is required. "
                        "Set NGROK_AUTHTOKEN environment variable or run "
                        "'ngrok config add-authtoken <your-token>'."
                    ),
                }
            )
    except Exception:
        logger.exception("Failed to configure ngrok authtoken")
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "message": "Failed to configure ngrok authtoken.",
            }
        )
    
    # Check if tunnel already exists for this port
    try:
        existing_tunnels = ngrok.get_tunnels()
        for tunnel in existing_tunnels:
            addr = tunnel.config.get("addr", "")
            if f":{port}" in addr or f"localhost:{port}" in addr:
                # Tunnel already exists, return it
                return JSONResponse(
                    content={
                        "ok": True,
                        "url": tunnel.public_url,
                        "message": "Tunnel already active",
                    }
                )
        
        # Disconnect any existing tunnels bound to this port
        for tunnel in existing_tunnels:
            addr = tunnel.config.get("addr", "")
            if f":{port}" in addr or f"localhost:{port}" in addr:
                try:
                    ngrok.disconnect(tunnel.public_url)
                except exception.PyngrokNgrokError:
                    # Ignore disconnect errors and continue
                    pass
    except Exception as e:
        logger.debug(f"Error checking existing tunnels: {e}")
    
    # Start new tunnel
    try:
        connect_kwargs = {"proto": "http"}
        if region:
            connect_kwargs["options"] = {"region": region}
        
        tunnel = ngrok.connect(port, **connect_kwargs)
        
        return JSONResponse(
            content={
                "ok": True,
                "url": tunnel.public_url,
                "message": "Tunnel started successfully",
            }
        )
    except exception.PyngrokNgrokError as pyngrok_error:
        logger.exception("pyngrok error while starting tunnel")
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": str(pyngrok_error),
                "message": (
                    "Failed to start tunnel via ngrok. "
                    "Check tunnel limits or run 'pkill ngrok' to clear stale sessions."
                ),
            }
        )
    except Exception as e:
        logger.exception("Failed to start tunnel")
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "message": "Failed to start tunnel. Make sure ngrok is installed and configured.",
            }
        )


@router.post("/stop", response_class=JSONResponse)
async def stop_tunnel():
    """Stop ngrok tunnel."""
    try:
        from pyngrok import ngrok
        ngrok.kill()
        return JSONResponse(content={"ok": True, "message": "Tunnel stopped"})
    except ImportError:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": "pyngrok not installed"}
        )
    except Exception as e:
        logger.exception("Failed to stop tunnel")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "message": f"Failed to stop tunnel: {e}"}
        )

