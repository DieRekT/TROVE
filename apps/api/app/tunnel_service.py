"""
Tunnel Service for External Network Access
Manages ngrok tunnels with proper health checks and status monitoring
"""

import asyncio
import logging
import subprocess
from typing import Any

import requests

logger = logging.getLogger(__name__)

class TunnelService:
    """Manages ngrok tunnel lifecycle with health monitoring."""
    
    def __init__(self):
        self.tunnel_process = None
        self.tunnel_url = None
        self.tunnel_status = "stopped"
        self.port = 8001
        
    async def start_tunnel(self, port: int = 8001) -> dict[str, Any]:
        """Start ngrok tunnel with proper error handling."""
        try:
            # Check if already running
            if self.tunnel_process and self.tunnel_process.poll() is None:
                if self.tunnel_url:
                    logger.info("Tunnel already running")
                    return {
                        "ok": True,
                        "status": "running",
                        "url": self.tunnel_url,
                        "message": "Tunnel already active"
                    }
            
            # Check if ngrok is properly configured
            try:
                result = subprocess.run(
                    ["ngrok", "config", "check"], 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                if result.returncode != 0:
                    logger.warning("ngrok not configured")
                    return {
                        "ok": False,
                        "status": "error",
                        "message": "ngrok requires configuration. Please run 'ngrok config add-authtoken <your-token>' first. Visit https://dashboard.ngrok.com/get-started/your-authtoken"
                    }
            except FileNotFoundError:
                return {
                    "ok": False,
                    "status": "error",
                    "message": "ngrok not installed. Install from: https://ngrok.com/download"
                }
            except Exception as e:
                logger.warning(f"ngrok config check failed: {e}")
                return {
                    "ok": False,
                    "status": "error",
                    "message": f"ngrok configuration error: {str(e)}"
                }
            
            # Stop any existing tunnel
            await self.stop_tunnel()
            
            # Start ngrok tunnel
            self.port = port
            logger.info(f"Starting ngrok tunnel on port {port}...")
            
            cmd = ["ngrok", "http", str(port), "--log=stdout", "--log-level=info"]
            self.tunnel_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for tunnel to start and get URL from ngrok API
            await asyncio.sleep(3)
            tunnel_url = await self._get_tunnel_url_from_api()
            
            # Fallback: try parsing output if API fails
            if not tunnel_url:
                await asyncio.sleep(2)
                tunnel_url = await self._get_tunnel_url_from_api()
            
            if tunnel_url:
                self.tunnel_url = tunnel_url
                self.tunnel_status = "running"
                logger.info(f"✅ Tunnel started: {tunnel_url}")
                return {
                    "ok": True,
                    "status": "running",
                    "url": tunnel_url,
                    "message": "Tunnel started successfully"
                }
            else:
                self.tunnel_status = "error"
                return {
                    "ok": False,
                    "status": "error",
                    "message": "Failed to get tunnel URL. Please check ngrok is running and try again."
                }
                
        except Exception as e:
            logger.error(f"Failed to start tunnel: {e}")
            self.tunnel_status = "error"
            return {
                "ok": False,
                "status": "error",
                "message": f"Failed to start tunnel: {str(e)}"
            }
    
    async def stop_tunnel(self) -> dict[str, Any]:
        """Stop ngrok tunnel."""
        try:
            if self.tunnel_process:
                self.tunnel_process.terminate()
                try:
                    self.tunnel_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.tunnel_process.kill()
                self.tunnel_process = None
            
            self.tunnel_url = None
            self.tunnel_status = "stopped"
            logger.info("Tunnel stopped")
            
            return {
                "ok": True,
                "status": "stopped",
                "message": "Tunnel stopped successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to stop tunnel: {e}")
            return {
                "ok": False,
                "status": "error",
                "message": f"Failed to stop tunnel: {str(e)}"
            }
    
    async def get_tunnel_status(self) -> dict[str, Any]:
        """Get current tunnel status with health check."""
        try:
            # Check if process is still running
            if self.tunnel_process and self.tunnel_process.poll() is None:
                # Try to get URL from API (in case it changed)
                current_url = await self._get_tunnel_url_from_api()
                if current_url:
                    self.tunnel_url = current_url
                
                # Verify tunnel is accessible
                if self.tunnel_url and await self._verify_tunnel():
                    return {
                        "ok": True,
                        "status": "running",
                        "url": self.tunnel_url,
                        "message": "Tunnel is active and accessible"
                    }
                else:
                    # Process running but not accessible
                    return {
                        "ok": False,
                        "status": "error",
                        "url": self.tunnel_url,
                        "message": "Tunnel is running but not accessible"
                    }
            else:
                # Process not running
                self.tunnel_status = "stopped"
                self.tunnel_url = None
                return {
                    "ok": False,
                    "status": "stopped",
                    "url": None,
                    "message": "Tunnel is not running"
                }
                
        except Exception as e:
            logger.error(f"Failed to get tunnel status: {e}")
            return {
                "ok": False,
                "status": "error",
                "message": f"Failed to get tunnel status: {str(e)}"
            }
    
    async def _get_tunnel_url_from_api(self) -> str | None:
        """Get tunnel URL from ngrok local API (port 4040)."""
        try:
            # Try ngrok API endpoint
            response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
            if response.status_code == 200:
                data = response.json()
                tunnels = data.get("tunnels", [])
                # Prefer HTTPS, fallback to HTTP
                for tunnel in tunnels:
                    proto = tunnel.get("proto", "")
                    if proto == "https":
                        return tunnel.get("public_url")
                # If no HTTPS, get HTTP
                for tunnel in tunnels:
                    if tunnel.get("proto") == "http":
                        return tunnel.get("public_url")
            return None
            
        except Exception as e:
            logger.debug(f"Failed to get tunnel URL from API: {e}")
            return None
    
    async def _verify_tunnel(self) -> bool:
        """Verify tunnel is accessible by checking health endpoint."""
        try:
            if not self.tunnel_url:
                return False
            
            # Try to access the tunnel URL
            response = requests.get(f"{self.tunnel_url}/api/ping", timeout=10)
            return response.status_code == 200
            
        except Exception as e:
            logger.debug(f"Tunnel verification failed: {e}")
            return False

# Global tunnel service instance
_tunnel_service = TunnelService()

async def start_tunnel(port: int = 8001) -> dict[str, Any]:
    """Start tunnel service."""
    return await _tunnel_service.start_tunnel(port)

async def stop_tunnel() -> dict[str, Any]:
    """Stop tunnel service."""
    return await _tunnel_service.stop_tunnel()

async def get_tunnel_status() -> dict[str, Any]:
    """Get tunnel status."""
    return await _tunnel_service.get_tunnel_status()

