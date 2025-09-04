from .rtudp import RtUdp
from typing import Optional, Tuple, Dict, Any

def port_mapper(ip: str, port: int, source_prefix: str, target_prefix: str) -> Tuple[str, int]:
    """Maybe there is a smart way of incorporating the IP address to make a unique mapping from ip+port to localhost+port."""
    assert ip.startswith(source_prefix), f"Expected ip starting with {source_prefix}, got {ip}"
    ip_new = ip.replace(source_prefix, target_prefix, 1)
    return ip_new, port

class RtUdpLh():
    _com: RtUdp

    def __init__(self, local_ip: str, local_port: int, remote_ip: str, remote_port: int, **kwargs):

        _REMOTE_IP_INTERNAL, _REMOTE_PORT_INTERNAL = port_mapper(remote_ip, remote_port, "125", "127")
        _LOCAL_IP_INTERNAL, _LOCAL_PORT_INTERNAL = port_mapper(local_ip, local_port, "125", "127")

        self._com = RtUdp(_LOCAL_IP_INTERNAL, _LOCAL_PORT_INTERNAL, _REMOTE_IP_INTERNAL, _REMOTE_PORT_INTERNAL, **kwargs)

    def send_data(self, data: bytes, timestamp: Optional[int]=None):
        return self._com.send_data(data, timestamp)

    def receive_data(self, timeout_ns: int) -> Tuple[bytes, int]:
        return self._com.receive_data(timeout_ns)

    def init_socket(self) -> None:
        return self._com.init_socket()

    def start(self):
        return self._com.start()

    def stop(self):
        return self._com.stop()

    def get_send_length(self) -> int:
        return self._com.get_send_length()

    def __hash__(self) -> int:
        return self._com.__hash__()

    def __repr__(self) -> str:
        return str(self._com)

    def is_running(self) -> bool:
        return self._com.is_running()

    def get_receive_length(self) -> int:
        return self._com.get_receive_length()

    def get_packet_stats(self) -> Dict[str, Any]:
        return self._com.get_packet_stats()

    def receive_batch(self, n_packets: int, timeout_ns: int) -> Tuple[bytes, int]:
        return self._com.receive_batch(n_packets, timeout_ns)

    def purge(self) -> None:
        return self._com.purge()
