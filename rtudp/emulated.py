import time
import threading
import queue
import heapq
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass, field
from collections import defaultdict
from .base import RtUdpBase


@dataclass(order=True)
class TimedPacket:
    """Packet with scheduled send time for priority queue."""
    timestamp_ns: int
    data: bytes = field(compare=False)
    
    
class GlobalQueueRegistry:
    """Global registry mapping (ip, port) endpoints to queues."""
    _registry: Dict[Tuple[str, int], queue.Queue] = {}
    _lock = threading.Lock()
    
    @classmethod
    def get_or_create_queue(cls, ip: str, port: int, capacity: int = 1024) -> queue.Queue:
        """Get existing queue or create new one for endpoint."""
        endpoint = (ip, port)
        with cls._lock:
            if endpoint not in cls._registry:
                cls._registry[endpoint] = queue.Queue(maxsize=capacity)
            return cls._registry[endpoint]
    
    @classmethod
    def remove_queue(cls, ip: str, port: int):
        """Remove queue from registry."""
        endpoint = (ip, port)
        with cls._lock:
            cls._registry.pop(endpoint, None)


class RtUdpEmulated(RtUdpBase):
    """Emulated UDP implementation using Python queues and threads."""
    
    def __init__(self, local_ip: str, local_port: int, 
                 remote_ip: str, remote_port: int, **kwargs):
        """Initialize the emulated UDP instance.
        
        Args:
            local_ip: Local IP address (used as queue identifier)
            local_port: Local port (used as queue identifier)
            remote_ip: Remote IP address (target queue identifier)
            remote_port: Remote port (target queue identifier)
            **kwargs: Additional parameters:
                - capacity: Queue capacity (default: 1024)
                - direction: 0=send, 1=receive, 2=full duplex (default: 0)
                - cpu: Ignored for emulated version
                - timeout: Default timeout in nanoseconds (default: 10s)
        """
        self.local_ip = local_ip
        self.local_port = local_port
        self.remote_ip = remote_ip
        self.remote_port = remote_port
        
        # Parse kwargs with defaults
        self.capacity = kwargs.get('capacity', 1024)
        self.direction = kwargs.get('direction', 0)
        self.timeout_ns = kwargs.get('timeout', 10_000_000_000)
        
        # Internal state
        self._running = False
        self._socket_initialized = False
        self._send_thread = None
        self._receive_thread = None
        
        # Queues for communication
        self._send_queue = []  # Priority queue for scheduled sends
        self._send_lock = threading.Lock()
        self._send_event = threading.Event()
        
        # Get or create receive queue from global registry
        self._receive_queue = None
        self._remote_queue = None
        
        # Statistics
        self._stats = {
            'n_packets_req': 0,
            'n_packets_sent': 0,
            'n_packets_rec': 0,
            'n_rx_packets_dropped': 0,
            'n_tx_packets_dropped': 0,
            'max_latency_ns': 0,
            'min_latency_ns': float('inf'),
            'total_latency_ns': 0,
            'n_send_ticks': 0,
            'n_rec_ticks': 0,
            'n_immediate_packets': 0,
        }
        
    def init_socket(self) -> None:
        """Initialize the communication channels."""
        if self._socket_initialized:
            raise OSError("Socket already initialized")
        
        # Get queues from global registry
        self._receive_queue = GlobalQueueRegistry.get_or_create_queue(
            self.local_ip, self.local_port, self.capacity)
        self._remote_queue = GlobalQueueRegistry.get_or_create_queue(
            self.remote_ip, self.remote_port, self.capacity)
        
        self._socket_initialized = True
    
    def close_socket(self) -> None:
        """Close the communication channels."""
        if not self._socket_initialized:
            return
        
        self._socket_initialized = False
        # Note: We don't remove queues from registry as other endpoints might use them
    
    def start(self) -> None:
        """Start worker threads."""
        if self._running:
            raise ValueError("Already running")
        
        if not self._socket_initialized:
            raise OSError("Socket not initialized")
        
        self._running = True
        
        # Start send thread if needed
        if self.direction in [0, 2]:  # Send or full duplex
            self._send_thread = threading.Thread(target=self._send_worker, daemon=True)
            self._send_thread.start()
        
        # Start receive thread if needed
        if self.direction in [1, 2]:  # Receive or full duplex
            self._receive_thread = threading.Thread(target=self._receive_worker, daemon=True)
            self._receive_thread.start()
    
    def stop(self) -> None:
        """Stop worker threads."""
        self._running = False
        self._send_event.set()  # Wake up send thread
        
        # Wait for threads to finish
        if self._send_thread:
            self._send_thread.join(timeout=1.0)
        if self._receive_thread:
            self._receive_thread.join(timeout=1.0)
    
    def send_data(self, data: bytes, timestamp: Optional[int] = None) -> None:
        """Send data with optional timestamp."""
        if not self._socket_initialized:
            raise OSError("Socket not initialized")
        
        if timestamp is None:
            timestamp = time.monotonic_ns()
        
        self._stats['n_packets_req'] += 1
        
        # Add to priority queue
        with self._send_lock:
            heapq.heappush(self._send_queue, TimedPacket(timestamp, data))
        
        # Wake up send thread
        self._send_event.set()
    
    def receive_data(self, timeout_ns: int) -> Tuple[bytes, int]:
        """Receive data with timeout."""
        if not self._socket_initialized:
            raise OSError("Socket not initialized")
        
        timeout_s = timeout_ns / 1_000_000_000
        
        try:
            data, timestamp = self._receive_queue.get(timeout=timeout_s)
            self._stats['n_packets_rec'] += 1
            return data, timestamp
        except queue.Empty:
            raise TimeoutError("Receive timed out")
    
    def receive_batch(self, n_packets: int, timeout_ns: int) -> List[Tuple[bytes, int]]:
        """Receive multiple packets."""
        if not self._socket_initialized:
            raise OSError("Socket not initialized")
        
        packets = []
        timeout_s = timeout_ns / 1_000_000_000
        end_time = time.monotonic() + timeout_s
        
        for _ in range(n_packets):
            remaining = end_time - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Timed out waiting for data")
            
            try:
                data, timestamp = self._receive_queue.get(timeout=remaining)
                packets.append((data, timestamp))
                self._stats['n_packets_rec'] += 1
            except queue.Empty:
                raise TimeoutError("Timed out waiting for data")
        
        return packets
    
    def get_packet_stats(self) -> Dict[str, Any]:
        """Get packet statistics."""
        stats = self._stats.copy()
        
        # Calculate average latency
        if stats['n_packets_sent'] > 0:
            stats['avg_latency_ns'] = stats['total_latency_ns'] // stats['n_packets_sent']
        else:
            stats['avg_latency_ns'] = 0
        
        # Fix min latency for display
        if stats['min_latency_ns'] == float('inf'):
            stats['min_latency_ns'] = 0
        
        return stats
    
    def get_send_length(self) -> int:
        """Get number of packets in send queue."""
        with self._send_lock:
            return len(self._send_queue)
    
    def get_receive_length(self) -> int:
        """Get number of packets in receive queue."""
        if self._receive_queue:
            return self._receive_queue.qsize()
        return 0
    
    def is_running(self) -> bool:
        """Check if worker threads are running."""
        return self._running
    
    def purge(self) -> None:
        """Clear all buffers."""
        # Clear send queue
        with self._send_lock:
            self._send_queue.clear()
        
        # Clear receive queue
        if self._receive_queue:
            try:
                while True:
                    self._receive_queue.get_nowait()
            except queue.Empty:
                pass
    
    def __hash__(self) -> int:
        """Return hash of the instance."""
        return hash((self.local_ip, self.local_port, self.remote_ip, self.remote_port))
    
    def __repr__(self) -> str:
        """Return string representation."""
        direction_str = {0: "send", 1: "recv", 2: "full"}[self.direction]
        return f"RtUdpEmulated[{direction_str}]({self.local_ip}:{self.local_port})"
    
    def _send_worker(self):
        """Worker thread for sending packets."""
        while self._running:
            self._stats['n_send_ticks'] += 1
            
            # Wait for packets or timeout
            self._send_event.wait(timeout=0.001)  # 1ms poll
            self._send_event.clear()
            
            now = time.monotonic_ns()
            
            # Process all packets ready to send
            with self._send_lock:
                while self._send_queue and self._send_queue[0].timestamp_ns <= now:
                    packet = heapq.heappop(self._send_queue)
                    
                    # Check if packet was scheduled for future
                    if packet.timestamp_ns < now:
                        self._stats['n_immediate_packets'] += 1
                    
                    # Send to remote queue
                    try:
                        self._remote_queue.put_nowait((packet.data, now))
                        self._stats['n_packets_sent'] += 1
                        
                        # Update latency stats
                        latency = now - packet.timestamp_ns
                        self._stats['max_latency_ns'] = max(self._stats['max_latency_ns'], latency)
                        self._stats['min_latency_ns'] = min(self._stats['min_latency_ns'], latency)
                        self._stats['total_latency_ns'] += latency
                        
                    except queue.Full:
                        self._stats['n_tx_packets_dropped'] += 1
            
            # Sleep until next packet is ready
            with self._send_lock:
                if self._send_queue:
                    next_packet_time = self._send_queue[0].timestamp_ns
                    sleep_time_ns = next_packet_time - time.monotonic_ns()
                    if sleep_time_ns > 0:
                        time.sleep(sleep_time_ns / 1_000_000_000)
                        self._send_event.set()  # Wake ourselves up
    
    def _receive_worker(self):
        """Worker thread for receiving packets (not used in basic implementation)."""
        # In the emulated version, receiving is handled directly from the queue
        # This thread could be used for statistics or packet processing if needed
        while self._running:
            self._stats['n_rec_ticks'] += 1
            time.sleep(0.001)  # 1ms poll