import time
import os
import pprint
import faulthandler
faulthandler.enable()
from udpcom import UdpCom

REC_CAPACITY = 4000;

if __name__ == "__main__":

    pid = os.getpid()
    os.sched_setaffinity(pid, {0})
    sender = UdpCom("127.0.64.5", 3043,  "127.0.128.133", 8974, cpu=3, capacity=1000000, direction=0)
    reciever = UdpCom("127.0.128.133", 8974, "127.0.64.5", 3043, cpu=2, capacity=REC_CAPACITY, direction=1)
    print(hash(sender))
    print(hash(reciever))
    sender.init_socket()
    reciever.init_socket()
    print("starting sender")
    sender.start()
    print("starting reciever")
    reciever.start()
    time.sleep(0.1)

    n_packets = 10000#00
    t_delta_ns = 20000
    margin = 1_000_000_0#00
    prev_id=0
    #init_socket("127.0.64.5", 3043,  "127.0.128.133", 8974)
    t_start = time.monotonic_ns() + margin
    next = t_start
    for i in range(n_packets):
        next = next + t_delta_ns
        #print(i)
        sender.send_data(i.to_bytes(8, "little"), next)
    print(f"[sender]{sender.get_packet_stats()}", )
    packet_id = 0
    n_stored_packets = 0
    try:
        while True:
            data, ts = reciever.receive_data(int(100000))
            n_stored_packets = n_stored_packets + 1
            packet_id = int.from_bytes(data, "little")
    except TimeoutError:
        print("[reciever]timed out.")

    time.sleep(0.2)
    t_end = time.monotonic_ns()
    duration_s = (t_end - t_start)/1e9
    n_packets_send = sender.get_packet_stats()['n_packets_sent']
    n_packets_ps = float(n_packets_send)/duration_s
    time.sleep(0.1)

    print("\n====================Sender===================")
    pprint.pp(sender.get_packet_stats())
    print("\n====================Reciever===================")
    pprint.pp(reciever.get_packet_stats())
    print(f"N packets/s={n_packets_ps}")
    print(f"N stored_packets={n_stored_packets}")

    print("stopping")
    sender.stop()
    print("closing")
    sender.close_socket() 
    print("closed")
    reciever.stop()

