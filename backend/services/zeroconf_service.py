"""
Zeroconf/mDNS Service for Home Assistant Discovery
Broadcasts Laro on the local network so Home Assistant can auto-discover it.
"""
import asyncio
import logging
import socket
from typing import Optional

logger = logging.getLogger(__name__)

_zeroconf = None
_service_info = None


def get_local_ip() -> str:
    """Get the local IP address."""
    try:
        # Create a socket to determine the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


async def start_zeroconf_service(port: int = 8001, name: str = "Laro") -> bool:
    """Start broadcasting Laro via Zeroconf/mDNS."""
    global _zeroconf, _service_info

    try:
        from zeroconf.asyncio import AsyncZeroconf
        from zeroconf import ServiceInfo
    except ImportError:
        logger.warning("zeroconf package not installed. HA auto-discovery disabled.")
        logger.warning("Install with: pip install zeroconf")
        return False

    try:
        ip_address = get_local_ip()
        hostname = socket.gethostname()

        # Create service info
        _service_info = ServiceInfo(
            "_mise._tcp.local.",
            f"{name}._mise._tcp.local.",
            addresses=[socket.inet_aton(ip_address)],
            port=port,
            properties={
                "version": "1.0",
                "path": "/api",
                "name": name,
            },
            server=f"{hostname}.local.",
        )

        # Create and start Zeroconf
        _zeroconf = AsyncZeroconf()
        await _zeroconf.async_register_service(_service_info)

        logger.info(f"Zeroconf service registered: {name} at {ip_address}:{port}")
        logger.info("Home Assistant can now auto-discover this Laro instance")
        return True

    except Exception as e:
        logger.error(f"Failed to start Zeroconf service: {e}")
        return False


async def stop_zeroconf_service():
    """Stop the Zeroconf service."""
    global _zeroconf, _service_info

    if _zeroconf and _service_info:
        try:
            await _zeroconf.async_unregister_service(_service_info)
            await _zeroconf.async_close()
            logger.info("Zeroconf service stopped")
        except Exception as e:
            logger.error(f"Error stopping Zeroconf service: {e}")

    _zeroconf = None
    _service_info = None
