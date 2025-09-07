from typing import Literal, Union
from .base import RtUdpBase
from .socket_impl import RtUdpSocket
from .emulated import RtUdpEmulated


def create_rtudp(
    implementation: Literal["socket", "emulated"],
    local_ip: str,
    local_port: int,
    remote_ip: str,
    remote_port: int,
    **kwargs
) -> RtUdpBase:
    """Factory function to create RtUDP instances.
    
    Args:
        implementation: Type of implementation to use:
            - "socket": Real UDP socket implementation
            - "emulated": Queue-based emulated implementation
        local_ip: Local IP address
        local_port: Local port
        remote_ip: Remote IP address
        remote_port: Remote port
        **kwargs: Additional implementation-specific parameters
        
    Returns:
        RtUdpBase instance of the requested implementation
        
    Raises:
        ValueError: If implementation type is unknown
    """
    if implementation == "socket":
        return RtUdpSocket(local_ip, local_port, remote_ip, remote_port, **kwargs)
    elif implementation == "emulated":
        return RtUdpEmulated(local_ip, local_port, remote_ip, remote_port, **kwargs)
    else:
        raise ValueError(f"Unknown implementation: {implementation}")


def create_rtudp_pair(
    implementation: Literal["socket", "emulated"],
    ip1: str,
    port1: int,
    ip2: str,
    port2: int,
    **kwargs
) -> tuple[RtUdpBase, RtUdpBase]:
    """Create a pair of connected RtUDP instances.
    
    Useful for testing and creating bidirectional communication channels.
    
    Args:
        implementation: Type of implementation to use
        ip1: First endpoint IP
        port1: First endpoint port
        ip2: Second endpoint IP
        port2: Second endpoint port
        **kwargs: Additional parameters (applied to both instances)
        
    Returns:
        Tuple of (endpoint1, endpoint2) RtUdpBase instances
    """
    # Create sender (endpoint1 -> endpoint2)
    kwargs1 = kwargs.copy()
    kwargs1.setdefault('direction', 0)  # Send
    endpoint1 = create_rtudp(implementation, ip1, port1, ip2, port2, **kwargs1)
    
    # Create receiver (endpoint2 -> endpoint1)
    kwargs2 = kwargs.copy()
    kwargs2.setdefault('direction', 1)  # Receive
    endpoint2 = create_rtudp(implementation, ip2, port2, ip1, port1, **kwargs2)
    
    return endpoint1, endpoint2