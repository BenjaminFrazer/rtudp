# RtUDP

A high-performance, deterministic UDP packet transmission framework with real-time capabilities and hardware timestamping support.

## Overview

RtUDP (Real-Time UDP) is a Python extension module written in C that provides low-latency, deterministic UDP communication with features designed for real-time networking applications. It uses ring buffers, pthread workers, and CPU affinity to achieve predictable packet transmission timing.

## Features

- **Deterministic packet scheduling**: Send packets at precise timestamps using monotonic clock
- **Multi-threaded architecture**: Separate send/receive worker threads with lock-free ring buffers
- **CPU affinity support**: Pin threads to specific CPU cores for reduced jitter
- **Real-time scheduling**: SCHED_FIFO support with configurable priority
- **Performance monitoring**: Built-in packet statistics including latency histograms
- **Half/full duplex modes**: Configurable for send-only, receive-only, or bidirectional communication
- **Large buffer capacity**: Configurable ring buffer sizes to handle burst traffic

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

```python
from rtudp import RtUdp

# Create sender and receiver instances
sender = RtUdp("127.0.64.5", 3043, "127.0.128.133", 8974, 
               cpu=3, capacity=1000000, direction=0)
receiver = RtUdp("127.0.128.133", 8974, "127.0.64.5", 3043, 
                 cpu=2, capacity=4000, direction=1)

# Initialize sockets
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

## Architecture

The framework uses:
- **Ring buffers** for lock-free communication between application and worker threads
- **pthread workers** for dedicated send/receive operations
- **Poll-based I/O** for efficient packet reception
- **Nanosecond precision timing** with clock_nanosleep for packet scheduling

## Performance

Designed for:
- Sub-millisecond packet transmission jitter
- Millions of packets per second throughput
- Predictable latency with real-time scheduling
- Minimal CPU overhead with efficient polling

## Requirements

- Linux with real-time kernel support (for best performance)
- Python 3.x with development headers
- GCC or Clang compiler
- pthread support

## License

See LICENSE file for details.