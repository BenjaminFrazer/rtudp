#!/usr/bin/env python3
"""Simple test for emulated implementation."""

import time
from rtudp import RtUdpEmulated

# Create sender and receiver
sender = RtUdpEmulated("127.0.0.1", 5000, "127.0.0.2", 5001, direction=0)
receiver = RtUdpEmulated("127.0.0.2", 5001, "127.0.0.1", 5000, direction=1)

print(f"Sender: {sender}")
print(f"Receiver: {receiver}")

# Initialize
sender.init_socket()
receiver.init_socket()

# Start workers
sender.start()
receiver.start()

# Wait a bit
time.sleep(0.1)

# Send some data
print("\nSending data...")
for i in range(5):
    data = f"Message {i}".encode()
    sender.send_data(data, time.monotonic_ns())
    print(f"  Sent: {data}")

# Wait for messages to propagate
time.sleep(0.1)

# Receive data
print("\nReceiving data...")
for i in range(5):
    try:
        data, ts = receiver.receive_data(1_000_000_000)  # 1 second timeout
        print(f"  Received: {data}")
    except TimeoutError:
        print("  Timeout!")
        break

# Check stats
print(f"\nSender stats: {sender.get_packet_stats()}")
print(f"Receiver stats: {receiver.get_packet_stats()}")

# Cleanup
sender.stop()
receiver.stop()
sender.close_socket()
receiver.close_socket()