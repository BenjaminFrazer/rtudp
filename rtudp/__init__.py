from .base import RtUdpBase
from .socket_impl import RtUdpSocket
from .emulated import RtUdpEmulated
from .factory import create_rtudp, create_rtudp_pair

# Type alias for type hinting - use this in your type annotations
RtUdpType = RtUdpBase

# Alias for compatibility (can be removed if not needed)
RtUdp = RtUdpSocket

__version__ = "0.1.0"
__all__ = [
    'RtUdpBase',
    'RtUdpType',  # Preferred for type hints
    'RtUdpSocket', 
    'RtUdpEmulated',
    'create_rtudp',
    'create_rtudp_pair',
    'RtUdp',  # Compatibility alias
]