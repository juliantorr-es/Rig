"""Server exposure modes for Rig WebSocket UI server.

This module defines the exposure modes for the WebSocket server,
controlling which clients can connect and what capabilities they have.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Set


class ServerExposureMode(Enum):
    """Exposure modes for the WebSocket UI server."""
    
    # Local-only UI: binds to 127.0.0.1, accepts local connections only
    LOCAL_UI = auto()
    
    # Local API: binds to 127.0.0.1, accepts local connections with API capabilities
    LOCAL_API = auto()
    
    # Private network: binds to specified host (not loopback), accepts connections
    # from the private network
    PRIVATE_NETWORK = auto()


# Capability scopes for clients
CAPABILITY_LOCAL_WINDOW = "local_window"
CAPABILITY_REMOTE_OBSERVER = "remote_observer"
CAPABILITY_REMOTE_OPERATOR = "remote_operator"
CAPABILITY_AUTOMATION_AGENT = "automation_agent"

# All capabilities
ALL_CAPABILITIES = {
    CAPABILITY_LOCAL_WINDOW,
    CAPABILITY_REMOTE_OBSERVER,
    CAPABILITY_REMOTE_OPERATOR,
    CAPABILITY_AUTOMATION_AGENT,
}

# Default capabilities for each mode
DEFAULT_CAPABILITIES_BY_MODE = {
    ServerExposureMode.LOCAL_UI: {CAPABILITY_LOCAL_WINDOW},
    ServerExposureMode.LOCAL_API: {CAPABILITY_LOCAL_WINDOW, CAPABILITY_REMOTE_OBSERVER},
    ServerExposureMode.PRIVATE_NETWORK: {CAPABILITY_REMOTE_OBSERVER, CAPABILITY_REMOTE_OPERATOR},
}


@dataclass(frozen=True)
class ServerConfig:
    """Configuration for the WebSocket UI server."""
    
    exposure_mode: ServerExposureMode
    host: str
    port: int
    session_token: str
    allowed_origins: Optional[Set[str]] = None
    allow_loopback: bool = True
    allow_private_network: bool = False
    allow_remote: bool = False
    
    @classmethod
    def for_local_ui(cls, host: str = "127.0.0.1", port: int = 0, session_token: str = "") -> "ServerConfig":
        """Create a local UI configuration."""
        return cls(
            exposure_mode=ServerExposureMode.LOCAL_UI,
            host=host,
            port=port,
            session_token=session_token,
            allow_loopback=True,
            allow_private_network=False,
            allow_remote=False,
        )
    
    @classmethod
    def for_private_network(cls, host: str, port: int, session_token: str) -> "ServerConfig":
        """Create a private network configuration."""
        return cls(
            exposure_mode=ServerExposureMode.PRIVATE_NETWORK,
            host=host,
            port=port,
            session_token=session_token,
            allow_loopback=True,
            allow_private_network=True,
            allow_remote=False,
        )
    
    def get_default_capabilities(self) -> Set[str]:
        """Get the default capabilities for this server configuration."""
        return DEFAULT_CAPABILITIES_BY_MODE.get(
            self.exposure_mode,
            {CAPABILITY_LOCAL_WINDOW}
        )
    
    def allows_host(self, host: str) -> bool:
        """Check if the given host is allowed by this configuration."""
        if self.exposure_mode == ServerExposureMode.LOCAL_UI:
            # Only allow loopback
            return host in ("127.0.0.1", "::1", "localhost")
        elif self.exposure_mode == ServerExposureMode.LOCAL_API:
            # Only allow loopback
            return host in ("127.0.0.1", "::1", "localhost")
        elif self.exposure_mode == ServerExposureMode.PRIVATE_NETWORK:
            # Allow loopback and RFC 1918 private addresses
            return (
                host in ("127.0.0.1", "::1", "localhost") or
                _is_private_ip(host)
            )
        return False
    
    def allows_origin(self, origin: str) -> bool:
        """Check if the given origin is allowed."""
        if self.allowed_origins is None:
            # Default: allow same-origin and local origins
            return (
                origin.startswith("http://127.0.0.1") or
                origin.startswith("http://localhost") or
                origin.startswith("ws://127.0.0.1") or
                origin.startswith("ws://localhost")
            )
        return origin in self.allowed_origins


def _is_private_ip(host: str) -> bool:
    """Check if the host is a private IP address."""
    # RFC 1918 private address ranges
    # 10.0.0.0/8
    # 172.16.0.0/12
    # 192.168.0.0/16
    # 169.254.0.0/16 (link-local)
    
    # IPv6 loopback
    if host in ("::1", "localhost"):
        return True
    
    # IPv4 loopback
    if host.startswith("127."):
        return True
    
    parts = host.split(".")
    if len(parts) != 4:
        return False
    
    try:
        octets = [int(p) for p in parts]
    except ValueError:
        return False
    
    # 10.0.0.0/8
    if octets[0] == 10:
        return True
    
    # 172.16.0.0/12
    if octets[0] == 172 and 16 <= octets[1] <= 31:
        return True
    
    # 192.168.0.0/16
    if octets[0] == 192 and octets[1] == 168:
        return True
    
    # 169.254.0.0/16 (link-local)
    if octets[0] == 169 and octets[1] == 254:
        return True
    
    return False
