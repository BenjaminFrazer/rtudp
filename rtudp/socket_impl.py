from typing import Optional, Tuple, Dict, Any, List
from .base import RtUdpBase
from .rtudp import _RtUdpSocket


class RtUdpSocket(RtUdpBase):
    """Real UDP socket implementation using the C extension."""
    
    def __init__(self, local_ip: str, local_port: int, 
                 remote_ip: str, remote_port: int, **kwargs):
        """Initialize the UDP socket.
        
        Args:
            local_ip: Local IP address to bind to
            local_port: Local port to bind to
            remote_ip: Remote IP address to send to
            remote_port: Remote port to send to
            **kwargs: Additional parameters:
                - bind: Whether to bind the socket (default: True)
                - connect: Whether to connect the socket (default: False)
                - capacity: Ring buffer capacity (default: 1024)
                - name: Name for debugging (default: "RtUdp")
                - direction: 0=send, 1=receive, 2=full duplex (default: 0)
                - cpu: CPU core to pin threads to (default: -1 for no affinity)
                - timeout: Default timeout in nanoseconds (default: 10s)
        """
        self._socket = _RtUdpSocket(local_ip, local_port, remote_ip, remote_port, **kwargs)
    
    def send_data(self, data: bytes, timestamp: Optional[int] = None) -> None:
        """Send data with optional timestamp."""
        return self._socket.send_data(data, timestamp)
    
    def receive_data(self, timeout_ns: int) -> Tuple[bytes, int]:
        """Receive data with timeout."""
        return self._socket.receive_data(timeout_ns)
    
    def receive_batch(self, n_packets: int, timeout_ns: int) -> List[Tuple[bytes, int]]:
        """Receive multiple packets."""
        return self._socket.receive_batch(n_packets, timeout_ns)
    
    def init_socket(self) -> None:
        """Initialize the UDP socket."""
        return self._socket.init_socket()
    
    def close_socket(self) -> None:
        """Close the UDP socket."""
        return self._socket.close_socket()
    
    def start(self) -> None:
        """Start worker threads."""
        return self._socket.start()
    
    def stop(self) -> None:
        """Stop worker threads."""
        return self._socket.stop()
    
    def get_packet_stats(self) -> Dict[str, Any]:
        """Get packet statistics."""
        return self._socket.get_packet_stats()
    
    def get_send_length(self) -> int:
        """Get number of packets in send queue."""
        return self._socket.get_send_length()
    
    def get_receive_length(self) -> int:
        """Get number of packets in receive queue."""
        return self._socket.get_receive_length()
    
    def is_running(self) -> bool:
        """Check if worker threads are running."""
        return self._socket.is_running()
    
    def purge(self) -> None:
        """Clear all buffers."""
        return self._socket.purge()
    
    def __hash__(self) -> int:
        """Return hash of the instance."""
        return hash(self._socket)
    
    def __repr__(self) -> str:
        """Return string representation."""
        return str(self._socket)