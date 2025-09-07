# RtUDP

A high-performance, deterministic UDP packet transmission framework with real-time capabilities and hardware timestamping support.

## Overview

RtUDP (Real-Time UDP) is a Python extension module written in C that provides low-latency, deterministic UDP communication with features designed for real-time networking applications. It uses ring buffers, pthread workers, and CPU affinity to achieve predictable packet transmission timing.

## Features

- **Deterministic packet scheduling**: Send packets at precise timestamps using monotonic clock
- **Multi-threaded architecture**: Separate send/receive worker threads with lock-free ring buffers
- **CPU affinity support**: Pin threads to specific CPU cores for reduced jitter (socket implementation)
- **Real-time scheduling**: SCHED_FIFO support with configurable priority (socket implementation)
- **Performance monitoring**: Built-in packet statistics including latency histograms
- **Half/full duplex modes**: Configurable for send-only, receive-only, or bidirectional communication
- **Large buffer capacity**: Configurable ring buffer sizes to handle burst traffic
- **Emulation layer**: Test networking code without actual UDP sockets
- **Unified interface**: Switch between implementations with a single parameter

## Installation

### From Source (Recommended)

#### Standard Installation
Install the package in your Python environment:
```bash
pip install .
```

#### Development/Editable Installation
For development, use an editable install that allows you to modify the code without reinstalling:
```bash
pip install -e .
```

#### Build from Source (Manual)
If you prefer to build manually:
```bash
make
# or
python setup.py build_ext --inplace
```

### From PyPI (Coming Soon)
Once published to PyPI, you'll be able to install directly:
```bash
pip install rtudp
```

## Usage

### Using the Factory Function (Recommended)

```python
from rtudp import create_rtudp
import time

# Create sender and receiver using factory function
# implementation can be "socket" (real UDP) or "emulated" (for testing)
sender = create_rtudp(
    "socket",  # or "emulated" for testing without network
    "127.0.64.5", 3043, "127.0.128.133", 8974,
    cpu=3, capacity=1000000, direction=0
)
receiver = create_rtudp(
    "socket",
    "127.0.128.133", 8974, "127.0.64.5", 3043,
    cpu=2, capacity=4000, direction=1
)

# Initialize communication channels
sender.init_socket()
receiver.init_socket()

# Start worker threads
sender.start()
receiver.start()

# Send data with precise timing
timestamp_ns = time.monotonic_ns() + 1000000  # 1ms in future
sender.send_data(b"Hello World", timestamp_ns)

# Receive data with timeout
data, timestamp = receiver.receive_data(timeout_ns=100000)

# Get performance statistics
stats = sender.get_packet_stats()
print(f"Packets sent: {stats['n_packets_sent']}")
print(f"Max latency: {stats['max_latency_ns']} ns")

# Cleanup
sender.stop()
receiver.stop()
sender.close_socket()
receiver.close_socket()
```

### Direct Class Usage

```python
from rtudp import RtUdpSocket, RtUdpEmulated

# For real UDP communication
sender = RtUdpSocket("127.0.64.5", 3043, "127.0.128.133", 8974, 
                     cpu=3, capacity=1000000, direction=0)

# For emulated communication (testing/development)
sender_emu = RtUdpEmulated("127.0.64.5", 3043, "127.0.128.133", 8974,
                           capacity=1000000, direction=0)
```

### Creating Connected Pairs

```python
from rtudp import create_rtudp_pair

# Create a connected sender/receiver pair
sender, receiver = create_rtudp_pair(
    "emulated",  # or "socket"
    "127.0.64.5", 3043,
    "127.0.128.133", 8974,
    capacity=1000
)
```

### Type Hinting

For type annotations, use `RtUdpBase` or the `RtUdpType` alias:

```python
from rtudp import RtUdpBase, RtUdpType, create_rtudp
from typing import List

# Both of these are correct:
def process_packets(connection: RtUdpBase) -> None:
    """Process packets from any RtUDP implementation."""
    data, timestamp = connection.receive_data(timeout_ns=1000000)
    # ...

def create_connections(count: int) -> List[RtUdpType]:
    """Create multiple connections (using the type alias)."""
    return [
        create_rtudp("socket", "127.0.0.1", 5000+i, "127.0.0.2", 6000+i)
        for i in range(count)
    ]

# The factory returns the base type
conn: RtUdpBase = create_rtudp("emulated", "127.0.0.1", 5000, "127.0.0.2", 5001)
```

## Architecture

### Dual Implementation Design

RtUDP provides two implementations of the same interface:

1. **RtUdpSocket**: High-performance C extension using real UDP sockets
   - Hardware timestamping support
   - Real-time thread scheduling (SCHED_FIFO)
   - CPU affinity for reduced jitter
   - Lock-free ring buffers

2. **RtUdpEmulated**: Pure Python implementation for testing/development
   - No network configuration required
   - Thread-based packet scheduling
   - Queue-based communication between endpoints
   - Identical API to socket implementation

### Core Components

- **Abstract Base Class (`RtUdpBase`)**: Defines the common interface
- **Factory Functions**: `create_rtudp()` and `create_rtudp_pair()` for easy instantiation
- **Ring buffers** (Socket): Lock-free communication between application and worker threads
- **Global Queue Registry** (Emulated): Maps (IP, port) endpoints to Python queues
- **pthread workers** (Socket): Dedicated send/receive operations with real-time priority
- **Thread workers** (Emulated): Python threads simulating send/receive operations
- **Poll-based I/O** (Socket): Efficient packet reception using system poll
- **Nanosecond precision timing**: Both implementations support precise packet scheduling

## Choosing an Implementation

### Use RtUdpSocket (socket) when:
- You need maximum performance and lowest latency
- You're running on Linux with real-time kernel support
- You're doing production networking or performance testing
- You need hardware timestamping or CPU affinity

### Use RtUdpEmulated (emulated) when:
- You're developing and testing application logic
- You want to run tests without network configuration
- You're debugging protocol implementations
- You need reproducible testing without network variability
- You're running on non-Linux platforms (for development only)

## Performance

### RtUdpSocket Performance
- Sub-millisecond packet transmission jitter
- Millions of packets per second throughput
- Predictable latency with real-time scheduling
- Minimal CPU overhead with efficient polling

### RtUdpEmulated Performance
- Millisecond-level timing precision
- Hundreds of thousands of packets per second
- Good for functional testing, not performance benchmarking
- Pure Python overhead, but identical API behavior

## Testing

The library includes test scripts that work with both implementations:

```python
# test_rtudp.py - Run with socket implementation (default)
python3 test_rtudp.py

# Run with emulated implementation
python3 test_rtudp.py emulated

# test_both_implementations.py - Compare both implementations
python3 test_both_implementations.py --packets 10000
```

Example test code that works with both:
```python
from rtudp import create_rtudp

# Switch implementation easily
USE_EMULATED = False  # or True for testing

implementation = "emulated" if USE_EMULATED else "socket"
sender = create_rtudp(implementation, "127.0.0.1", 5000, "127.0.0.2", 5001)
```

## Requirements

### For RtUdpSocket (C extension)
- Linux with real-time kernel support (for best performance)
- Python 3.x with development headers
- GCC or Clang compiler
- pthread support

### For RtUdpEmulated
- Python 3.x (any platform)
- No additional requirements

## License

See LICENSE file for details.