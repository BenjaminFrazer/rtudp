#!/usr/bin/env python3
"""Test both RtUDP implementations (socket and emulated)."""

import time
import os
import sys
import pprint
import argparse
from rtudp import create_rtudp, create_rtudp_pair, RtUdpSocket, RtUdpEmulated


def test_implementation(implementation="socket", n_packets=10000, verbose=False):
    """Test a specific RtUDP implementation.
    
    Args:
        implementation: "socket" or "emulated"
        n_packets: Number of packets to send
        verbose: Print detailed stats
    """
    print(f"\n{'='*60}")
    print(f"Testing {implementation.upper()} implementation")
    print(f"{'='*60}")
    
    # Set CPU affinity for main thread
    if implementation == "socket":
        pid = os.getpid()
        os.sched_setaffinity(pid, {0})
    
    # Create sender and receiver
    sender = create_rtudp(
        implementation,
        "127.0.64.5", 3043,
        "127.0.128.133", 8974,
        cpu=3, capacity=1000000, direction=0
    )
    
    receiver = create_rtudp(
        implementation,
        "127.0.128.133", 8974,
        "127.0.64.5", 3043,
        cpu=2, capacity=4000, direction=1
    )
    
    print(f"Sender: {sender}")
    print(f"Receiver: {receiver}")
    print(f"Sender hash: {hash(sender)}")
    print(f"Receiver hash: {hash(receiver)}")
    
    # Initialize and start
    sender.init_socket()
    receiver.init_socket()
    
    print("Starting sender...")
    sender.start()
    print("Starting receiver...")
    receiver.start()
    
    time.sleep(0.1)
    
    # Send packets
    t_delta_ns = 20000  # 20 microseconds between packets
    margin = 10_000_000  # 10ms margin
    
    t_start = time.monotonic_ns() + margin
    next_time = t_start
    
    print(f"Sending {n_packets} packets...")
    for i in range(n_packets):
        next_time = next_time + t_delta_ns
        sender.send_data(i.to_bytes(8, "little"), next_time)
    
    # Receive packets
    n_received = 0
    last_packet_id = -1
    
    print("Receiving packets...")
    try:
        while True:
            data, ts = receiver.receive_data(100000)  # 100us timeout
            n_received += 1
            packet_id = int.from_bytes(data, "little")
            
            # Check for dropped packets
            if packet_id != last_packet_id + 1 and last_packet_id != -1:
                print(f"  Warning: Packet drop detected! Expected {last_packet_id + 1}, got {packet_id}")
            last_packet_id = packet_id
            
    except TimeoutError:
        pass
    
    # Wait for any remaining packets
    time.sleep(0.2)
    
    # Calculate statistics
    t_end = time.monotonic_ns()
    duration_s = (t_end - t_start) / 1e9
    
    sender_stats = sender.get_packet_stats()
    receiver_stats = receiver.get_packet_stats()
    
    n_packets_sent = sender_stats['n_packets_sent']
    packets_per_sec = float(n_packets_sent) / duration_s if duration_s > 0 else 0
    
    # Print summary
    print(f"\n{'-'*40}")
    print(f"Summary for {implementation} implementation:")
    print(f"  Packets requested: {n_packets}")
    print(f"  Packets sent: {n_packets_sent}")
    print(f"  Packets received: {n_received}")
    print(f"  Packets/second: {packets_per_sec:.0f}")
    print(f"  Duration: {duration_s:.3f}s")
    
    if n_packets_sent > 0:
        print(f"  Max latency: {sender_stats['max_latency_ns']/1000:.1f} us")
        print(f"  Min latency: {sender_stats['min_latency_ns']/1000:.1f} us")
        avg_latency = sender_stats.get('avg_latency_ns', 
                                      sender_stats['total_latency_ns'] // n_packets_sent)
        print(f"  Avg latency: {avg_latency/1000:.1f} us")
    
    if verbose:
        print(f"\n{'='*20} Sender Stats {'='*20}")
        pprint.pprint(sender_stats)
        print(f"\n{'='*20} Receiver Stats {'='*20}")
        pprint.pprint(receiver_stats)
    
    # Cleanup
    print("\nStopping...")
    sender.stop()
    receiver.stop()
    sender.close_socket()
    receiver.close_socket()
    
    return {
        'implementation': implementation,
        'packets_sent': n_packets_sent,
        'packets_received': n_received,
        'packets_per_sec': packets_per_sec,
        'duration_s': duration_s,
    }


def test_emulated_bidirectional():
    """Test bidirectional communication with emulated implementation."""
    print(f"\n{'='*60}")
    print("Testing BIDIRECTIONAL emulated communication")
    print(f"{'='*60}")
    
    # Create a pair of endpoints
    endpoint1, endpoint2 = create_rtudp_pair(
        "emulated",
        "192.168.1.1", 5000,
        "192.168.1.2", 5001,
        capacity=1000
    )
    
    # Override directions for full duplex
    endpoint1.direction = 2  # Full duplex
    endpoint2.direction = 2  # Full duplex
    
    print(f"Endpoint 1: {endpoint1}")
    print(f"Endpoint 2: {endpoint2}")
    
    # Initialize and start
    endpoint1.init_socket()
    endpoint2.init_socket()
    endpoint1.start()
    endpoint2.start()
    
    # Send messages both ways
    print("\nSending messages...")
    
    # EP1 -> EP2
    for i in range(5):
        msg = f"Hello from EP1: {i}".encode()
        endpoint1.send_data(msg, time.monotonic_ns())
    
    # EP2 -> EP1
    for i in range(5):
        msg = f"Hello from EP2: {i}".encode()
        endpoint2.send_data(msg, time.monotonic_ns())
    
    time.sleep(0.1)  # Let messages propagate
    
    # Receive messages
    print("\nEndpoint 2 receiving:")
    for _ in range(5):
        try:
            data, ts = endpoint2.receive_data(1_000_000_000)
            print(f"  Received: {data.decode()}")
        except TimeoutError:
            break
    
    print("\nEndpoint 1 receiving:")
    for _ in range(5):
        try:
            data, ts = endpoint1.receive_data(1_000_000_000)
            print(f"  Received: {data.decode()}")
        except TimeoutError:
            break
    
    # Cleanup
    endpoint1.stop()
    endpoint2.stop()
    endpoint1.close_socket()
    endpoint2.close_socket()


def main():
    parser = argparse.ArgumentParser(description='Test RtUDP implementations')
    parser.add_argument('--implementation', choices=['socket', 'emulated', 'both'],
                       default='both', help='Which implementation to test')
    parser.add_argument('--packets', type=int, default=10000,
                       help='Number of packets to send')
    parser.add_argument('--verbose', action='store_true',
                       help='Print detailed statistics')
    parser.add_argument('--bidirectional', action='store_true',
                       help='Test bidirectional communication (emulated only)')
    
    args = parser.parse_args()
    
    results = []
    
    if args.implementation in ['socket', 'both']:
        try:
            result = test_implementation('socket', args.packets, args.verbose)
            results.append(result)
        except Exception as e:
            print(f"Error testing socket implementation: {e}")
            import traceback
            traceback.print_exc()
    
    if args.implementation in ['emulated', 'both']:
        try:
            result = test_implementation('emulated', args.packets, args.verbose)
            results.append(result)
        except Exception as e:
            print(f"Error testing emulated implementation: {e}")
            import traceback
            traceback.print_exc()
    
    if args.bidirectional:
        test_emulated_bidirectional()
    
    # Compare results
    if len(results) == 2:
        print(f"\n{'='*60}")
        print("COMPARISON")
        print(f"{'='*60}")
        
        socket_result = results[0]
        emulated_result = results[1]
        
        print(f"{'Metric':<20} {'Socket':>15} {'Emulated':>15}")
        print(f"{'-'*50}")
        print(f"{'Packets sent':<20} {socket_result['packets_sent']:>15,} {emulated_result['packets_sent']:>15,}")
        print(f"{'Packets received':<20} {socket_result['packets_received']:>15,} {emulated_result['packets_received']:>15,}")
        print(f"{'Packets/sec':<20} {socket_result['packets_per_sec']:>15,.0f} {emulated_result['packets_per_sec']:>15,.0f}")
        print(f"{'Duration (s)':<20} {socket_result['duration_s']:>15.3f} {emulated_result['duration_s']:>15.3f}")


if __name__ == "__main__":
    main()