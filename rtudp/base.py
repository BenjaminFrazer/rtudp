from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any, List


class RtUdpBase(ABC):
    """Abstract base class for RtUDP implementations.
    
    Defines the interface that all RtUDP implementations must follow,
    whether they use real UDP sockets or emulated communication.
    """
    
    @abstractmethod
    def __init__(self, local_ip: str, local_port: int, 
                 remote_ip: str, remote_port: int, **kwargs):
        """Initialize the RtUDP instance.
        
        Args:
            local_ip: Local IP address to bind to
            local_port: Local port to bind to
            remote_ip: Remote IP address to send to
            remote_port: Remote port to send to
            **kwargs: Implementation-specific parameters like:
                - capacity: Ring buffer capacity
                - cpu: CPU core affinity
                - direction: 0=send, 1=receive, 2=full duplex
                - timeout: Default timeout in nanoseconds
        """
        pass
    
    @abstractmethod
    def send_data(self, data: bytes, timestamp: Optional[int] = None) -> None:
        """Send data with optional timestamp.
        
        Args:
            data: Bytes to send
            timestamp: Optional monotonic timestamp in nanoseconds for scheduled send
        """
        pass
    
    @abstractmethod
    def receive_data(self, timeout_ns: int) -> Tuple[bytes, int]:
        """Receive data with timeout.
        
        Args:
            timeout_ns: Timeout in nanoseconds
            
        Returns:
            Tuple of (data, timestamp_ns)
            
        Raises:
            TimeoutError: If no data received within timeout
        """
        pass
    
    @abstractmethod
    def receive_batch(self, n_packets: int, timeout_ns: int) -> List[Tuple[bytes, int]]:
        """Receive multiple packets.
        
        Args:
            n_packets: Number of packets to receive
            timeout_ns: Timeout in nanoseconds
            
        Returns:
            List of (data, timestamp_ns) tuples
            
        Raises:
            TimeoutError: If timeout reached before all packets received
            ValueError: If packets were dropped
        """
        pass
    
    @abstractmethod
    def init_socket(self) -> None:
        """Initialize the communication channel (socket/queue)."""
        pass
    
    @abstractmethod
    def close_socket(self) -> None:
        """Close the communication channel."""
        pass
    
    @abstractmethod
    def start(self) -> None:
        """Start worker threads for send/receive operations."""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop worker threads."""
        pass
    
    @abstractmethod
    def get_packet_stats(self) -> Dict[str, Any]:
        """Get packet statistics.
        
        Returns:
            Dictionary with statistics like:
                - n_packets_sent
                - n_packets_rec
                - n_rx_packets_dropped
                - n_tx_packets_dropped
                - max_latency_ns
                - min_latency_ns
                - total_latency_ns
        """
        pass
    
    @abstractmethod
    def get_send_length(self) -> int:
        """Get number of packets in send queue."""
        pass
    
    @abstractmethod
    def get_receive_length(self) -> int:
        """Get number of packets in receive queue."""
        pass
    
    @abstractmethod
    def is_running(self) -> bool:
        """Check if worker threads are running."""
        pass
    
    @abstractmethod
    def purge(self) -> None:
        """Clear all buffers."""
        pass
    
    @abstractmethod
    def __hash__(self) -> int:
        """Return hash of the instance."""
        pass
    
    @abstractmethod
    def __repr__(self) -> str:
        """Return string representation."""
        pass