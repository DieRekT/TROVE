"""Fetch and save images from State Library NSW and other sources."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

logger = logging.getLogger(__name__)

# Output directory for saved images
IMAGES_DIR = Path("outputs/images")
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


async def extract_slnsw_image_url(url: str) -> str | None:
    """
    Extract the actual image URL from a State Library NSW viewer URL.
    
    Args:
        url: State Library NSW viewer URL (e.g., DeliveryManagerServlet with dps_pid)
        
    Returns:
        Direct image URL or None if extraction fails
    """
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        # Extract dps_pid (document ID)
        dps_pid = params.get("dps_pid", [None])[0]
        if not dps_pid:
            # Try to extract from URL if not in params
            match = re.search(r"dps_pid=([^&]+)", url)
            if match:
                dps_pid = match.group(1)
            else:
                logger.warning(f"Could not extract dps_pid from URL: {url}")
                return None
        
        # State Library NSW image API pattern
        # Try different possible image URL formats
        image_urls = [
            f"https://digital.sl.nsw.gov.au/delivery/DeliveryManagerServlet?dps_pid={dps_pid}&dps_func=stream&dps_pid_type=IE",
            f"https://digital.sl.nsw.gov.au/delivery/DeliveryManagerServlet?dps_pid={dps_pid}&dps_func=stream",
            f"https://digital.sl.nsw.gov.au/delivery/DeliveryManagerServlet?dps_pid={dps_pid}&dps_func=stream&dps_pid_type=IE&dps_thumbnail=true",
        ]
        
        # Try to get the actual image URL by checking the viewer page
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }) as client:
                # First, try to get the viewer page to find image URLs
                response = await client.get(url)
                if response.status_code == 200:
                    html = response.text
                    # Look for image URLs in the HTML
                    # Common patterns in State Library NSW viewer
                    patterns = [
                        r'<img[^>]+src=["\']([^"\']*DeliveryManagerServlet[^"\']*stream[^"\']*)["\']',
                        r'imageUrl["\']?\s*[:=]\s*["\']([^"\']+)["\']',
                        r'data-src=["\']([^"\']*DeliveryManagerServlet[^"\']*stream[^"\']*)["\']',
                        r'https://digital\.sl\.nsw\.gov\.au/delivery/DeliveryManagerServlet[^"\'>\s]+stream[^"\'>\s]*',
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, html, re.IGNORECASE)
                        if matches:
                            # Use the first match that looks like a stream URL
                            for match in matches:
                                if "stream" in match.lower():
                                    return match if match.startswith("http") else f"https://digital.sl.nsw.gov.au{match}"
                
                # Fallback: try the direct stream URLs
                for img_url in image_urls:
                    try:
                        test_response = await client.head(img_url, timeout=5.0)
                        if test_response.status_code == 200:
                            content_type = test_response.headers.get("content-type", "")
                            if "image" in content_type.lower():
                                return img_url
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"Error fetching viewer page: {e}")
        
        # Return the most likely URL format
        return image_urls[0]
        
    except Exception as e:
        logger.error(f"Error extracting image URL: {e}")
        return None


async def download_image(image_url: str, filename: str | None = None) -> Path | None:
    """
    Download an image from a URL and save it locally.
    
    Args:
        image_url: URL of the image to download
        filename: Optional custom filename (without extension)
        
    Returns:
        Path to saved image file, or None on error
    """
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(image_url)
            response.raise_for_status()
            
            # Determine filename
            if not filename:
                # Extract from URL or use timestamp
                parsed = urlparse(image_url)
                # Try to get filename from URL
                url_filename = Path(parsed.path).name
                if url_filename and "." in url_filename:
                    filename = url_filename.rsplit(".", 1)[0]
                else:
                    # Extract from query params (State Library NSW)
                    params = parse_qs(parsed.query)
                    dps_pid = params.get("dps_pid", [None])[0]
                    if dps_pid:
                        filename = dps_pid.replace("/", "_")
                    else:
                        from datetime import datetime
                        filename = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Determine file extension from content type or URL
            content_type = response.headers.get("content-type", "")
            if "jpeg" in content_type or "jpg" in content_type:
                ext = ".jpg"
            elif "png" in content_type:
                ext = ".png"
            elif "gif" in content_type:
                ext = ".gif"
            elif "webp" in content_type:
                ext = ".webp"
            else:
                # Try to get from URL
                parsed = urlparse(image_url)
                url_ext = Path(parsed.path).suffix.lower()
                ext = url_ext if url_ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"] else ".jpg"
            
            # Sanitize filename
            filename = re.sub(r'[^\w\-_\.]', '_', filename)
            filepath = IMAGES_DIR / f"{filename}{ext}"
            
            # Save the image
            filepath.write_bytes(response.content)
            logger.info(f"Saved image: {filepath}")
            
            return filepath
            
    except Exception as e:
        logger.error(f"Error downloading image from {image_url}: {e}")
        return None


async def fetch_and_save_slnsw_image(viewer_url: str, filename: str | None = None) -> dict[str, Any]:
    """
    Extract image URL from State Library NSW viewer and download it.
    
    Args:
        viewer_url: State Library NSW viewer URL
        filename: Optional custom filename
        
    Returns:
        Dictionary with status, file path, and image URL
    """
    try:
        # Extract the actual image URL
        image_url = await extract_slnsw_image_url(viewer_url)
        
        if not image_url:
            return {
                "ok": False,
                "error": "Could not extract image URL from State Library NSW viewer",
            }
        
        # Download and save
        filepath = await download_image(image_url, filename)
        
        if not filepath:
            return {
                "ok": False,
                "error": "Failed to download image",
            }
        
        return {
            "ok": True,
            "filepath": str(filepath),
            "filename": filepath.name,
            "image_url": image_url,
            "viewer_url": viewer_url,
            "web_path": f"/files/images/{filepath.name}",
        }
        
    except Exception as e:
        logger.exception(f"Error in fetch_and_save_slnsw_image: {e}")
        return {
            "ok": False,
            "error": str(e),
        }

