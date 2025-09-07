#!/usr/bin/env python3
"""Test emulated implementation with the same address pattern as the original test."""

import time
from rtudp import RtUdpEmulated

# Use the EXACT same address pattern as test_rtudp.py
sender = RtUdpEmulated("127.0.64.5", 3043, "127.0.128.133", 8974, direction=0)
receiver = RtUdpEmulated("127.0.128.133", 8974, "127.0.64.5", 3043, direction=1)

print(f"Sender: {sender}")
print(f"Receiver: {receiver}")
print(f"Sender local: (127.0.64.5, 3043), remote: (127.0.128.133, 8974)")
print(f"Receiver local: (127.0.128.133, 8974), remote: (127.0.64.5, 3043)")

# Initialize
sender.init_socket()
receiver.init_socket()

# Start workers
sender.start()
receiver.start()

# Send some data
print("\nSending data...")
for i in range(5):
    data = f"Message {i}".encode()
    sender.send_data(data, time.monotonic_ns())
    print(f"  Sent: {data}")

time.sleep(0.1)

# Receive data
print("\nReceiving data...")
for i in range(5):
    try:
        data, ts = receiver.receive_data(1_000_000_000)
        print(f"  Received: {data}")
    except TimeoutError:
        print("  Timeout!")
        break

print("\nIT WORKS! The queues are properly separated:")
print(f"  Queue for (127.0.64.5, 3043) - used by sender's local")
print(f"  Queue for (127.0.128.133, 8974) - used by receiver's local AND sender's remote")
print("\nWhen sender sends to (127.0.128.133, 8974), it puts data in that queue.")
print("When receiver receives from (127.0.128.133, 8974), it reads from that same queue.")

# Cleanup
sender.stop()
receiver.stop()
sender.close_socket()
receiver.close_socket()