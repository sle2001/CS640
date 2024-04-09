import argparse
import socket
import struct
import math
import time
from typing import Literal
from datetime import datetime
STRUCT_FORMAT = "!cIHIHI"

class Sender:
    def __init__(
        self, port: int, req_port: int, rate: int, seq_no: int, length: int,  \
            host_name: str, host_port: int, priority: str, timeout:int 
    ) -> None:
        self. total_packet_sent = 0
        self.total_retransmit = 0
        self.listen_port = port
        self.requester_port = req_port
        self.requester_address = None
        self.rate = rate
        self.sequence_no = 1
        self.length = length
        self.UDP_IP = socket.gethostbyname(socket.gethostname())
        self.priority = priority
        self.host_name = host_name
        self.host_port = host_port
        self.timeout = float(timeout)/1000
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.UDP_IP, self.listen_port))
        self.listen_to_request()

    def listen_to_request(self) -> None:
        packet, req_addr = self.sock.recvfrom(8192)
        self.requester_address = req_addr[0]
        outterHeader = packet[:17]
        outterPayload = packet[17:]
        header = outterPayload[:9]
        payload = outterPayload[9:]
        headers = struct.unpack("!cII", header)
        outterHeaders = struct.unpack(STRUCT_FORMAT, outterHeader)
        _, src_addr, src_port, dest_addr, dest_port,_ = outterHeaders
        src_addr = socket.inet_ntoa(src_addr.to_bytes(4, byteorder='big'))
        dest_addr = socket.inet_ntoa(dest_addr.to_bytes(4, byteorder='big'))
        request_type, file_requested, window_size = headers[0].decode(), payload.decode(),headers[2]
        if request_type != "R":
            print(
                f"[Error] Should get a request with request type 'R', but got {request_type} instead."
            )
        self.send_file(file_requested, src_addr, src_port, dest_addr, dest_port, window_size)


    def send_file(self, filename: str, src_addr: int, src_port: int, \
        dest_addr: int, dest_port: int, window_size:int) -> None:
        # read in the requested file
        content = b""
        with open(filename, "r") as f:
            content = f.read().encode()
        filesize = len(content)

        headers = []
        sequence_nos = []
        innerheaders = []
        send_addr = int.from_bytes(socket.inet_aton(dest_addr), byteorder='big')
        recv_addr = int.from_bytes(socket.inet_aton(src_addr), byteorder='big')
        self.priority = str(self.priority)
        if filesize <= self.length:
            innerheader = struct.pack(
                    "!cII", "D".encode(), socket.htonl(self.sequence_no), filesize)
            # not sure if it's the correct way to pack outter header
            headers.append(
                    struct.pack(STRUCT_FORMAT, self.priority.encode(),send_addr, dest_port, \
                        recv_addr,src_port, len(innerheader)+filesize)
            )
            sequence_nos.append(self.sequence_no)
            innerheaders.append(innerheader)
            self.sequence_no += 1
        else:
            num_packets = math.ceil(filesize / self.length)
            last_payload_length = filesize % self.length
            for i in range(num_packets):
                if i == num_packets - 1:
                    # last packet
                    if last_payload_length == 0:
                        last_payload_length = 10
                    innerheader = struct.pack(
                            "!cII", "D".encode(), socket.htonl(self.sequence_no), last_payload_length)
                    headers.append(
                        struct.pack(STRUCT_FORMAT, self.priority.encode(),send_addr, dest_port, \
                            recv_addr,src_port, len(innerheader)+last_payload_length)
                    )
                    sequence_nos.append(self.sequence_no)
                    self.sequence_no += 1
                    innerheaders.append(innerheader)
                else:
                    innerheader = struct.pack(
                            "!cII", "D".encode(), socket.htonl(self.sequence_no), self.length)
                    headers.append(
                        struct.pack(STRUCT_FORMAT, self.priority.encode(),send_addr, dest_port, \
                            recv_addr,src_port, len(innerheader)+self.length)
                    )
                    sequence_nos.append(self.sequence_no)
                    self.sequence_no += 1
                    innerheaders.append(innerheader)

        file_parts = []
        for i in range(len(headers)):
            file_parts.append(content[i * self.length : (i + 1) * self.length])
        
        # add End packet 
        finalInner = struct.pack("!cII", "E".encode(), socket.htonl(self.sequence_no), 0)
        finalHeader = struct.pack(STRUCT_FORMAT, self.priority.encode(),send_addr, dest_port, \
                            recv_addr,src_port, len(innerheader))
        header_and_payload = [
            header + innerheader + payload for header, innerheader, payload in zip(headers, innerheaders,file_parts)
        ]
        
        index = 0
        window_num = 0
        # send the packets with rate limit
        dest = socket.gethostbyname(self.host_name)
        while index < len(header_and_payload):
            # send a full window or remaining packets
            window = min(window_size, len(header_and_payload) - window_size * window_num)
            #print("index ",index, "length: ",len(header_and_payload), "window: ", window, window_num,window_size)
            if window <0:
                raise RuntimeError()
            for i in range(window):
                outterHeader = header_and_payload[index][:17]
                outterPayload = header_and_payload[index][17:]
                header = outterPayload[:9]
                payload = outterPayload[9:]
                headers = struct.unpack("!cII", header)
                outterHeaders = struct.unpack(STRUCT_FORMAT, outterHeader)
                pri, src_addr, src_port, dest_addr, dest_port,leng = outterHeaders
                src_addr = socket.inet_ntoa(src_addr.to_bytes(4, byteorder='big'))
                dest_addr = socket.inet_ntoa(dest_addr.to_bytes(4, byteorder='big'))
                request_type, sq_n, window_size1 = headers
                payload = payload.decode()
                self.sock.sendto(
                    #requester and emulator should all use same address, it should work for this project?
                    header_and_payload[index], (socket.gethostbyname(self.host_name), self.host_port) 
                )
                index += 1
                self.total_packet_sent += 1
                time.sleep(1 / self.rate)
            
            window_num += 1
            # try to receive all returning ack packets
            received_ack = []
            for i in range(window):
                try:
                    self.sock.settimeout(self.timeout)
                    packet, _ = self.sock.recvfrom(8192)
                    self.sock.settimeout(None)
                    outterPayload = packet[17:]
                    header = outterPayload[:9]
                    headers = struct.unpack("!cII", header)
                    request_type, seq_no,_ = headers
                    request_type = request_type.decode()
                    seq_no = socket.htonl(seq_no)
                    #get all ack packets seq_no
                    if request_type == "A":
                        received_ack.append(seq_no -1)
                except TimeoutError:
                    print("Timeout for one of the packet.")
            # if there are missing packets, try to resend all missing packets
            if len(received_ack) != window:
                missing =  [i for i in range(index-window,index) if i not in received_ack]
                for i in missing:
                    trial = 1
                    self.sock.sendto(
                        header_and_payload[i], (socket.gethostbyname(self.host_name), self.host_port)
                    )
                    self.total_retransmit +=1
                    self.total_packet_sent +=1
                    ack = False
                    while trial <=5 and ack == False:
                        try:
                            self.sock.settimeout(self.timeout)
                            packet, _ = self.sock.recvfrom(8192)
                            self.sock.settimeout(None)
                            outterPayload = packet[17:]
                            header = outterPayload[:9]
                            headers = struct.unpack("!cII", header)
                            request_type, seq_no,_ = headers
                            request_type = request_type.decode()
                            seq_no = socket.htonl(seq_no)
                            if request_type != "A":
                                print(
                                    f"[Error] Should get a ack packet with request type 'A', but got {request_type} instead."
                                    )
                            elif seq_no != i+1:
                                print(
                                    f"[Error] Wrong sequnence number in ack packet, should be {i+1}, but got {seq_no} instead."
                                    )
                            else:
                                ack = True
                        except TimeoutError:
                            if trial < 5:
                                self.sock.sendto(
                                    header_and_payload[i], (socket.gethostbyname(self.host_name), self.host_port)
                                )
                                time.sleep(1 / self.rate)
                                self.total_retransmit +=1
                                self.total_packet_sent +=1
                                trial +=1
                            else:
                                trial += 1
                    
                    if(trial > 5 and ack == False):
                        print(f"Gave up on packet {i+1}, moving on to next packet")

        # send END packet
        self.sock.sendto(
                    #requester and emulator should all use same address, it should work for this project?
                    finalHeader+finalInner, (socket.gethostbyname(self.host_name), self.host_port) 
                )
        
        print(f"Loss Rate: {self.total_retransmit/self.total_packet_sent * 100}%")

    def log_info(self, type: Literal["D", "E"], seq: int, length: int, payload: bytes) -> None:
        if type == "D":
            print(f"-----DATA Packet-----")
            print(f"Send Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
            print(f"Requester Address: {self.requester_address}: {self.requester_port}")
            print(f"Sequence number: {seq}")
            print(f"Length: {length}")
            print(f"Payload: {payload[:4].decode()}")
            print(f"---------------------")
        elif type == "E":
            print(f"-----END Packet------")
            print(f"send time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
            print(f"requester addr: {self.requester_address}: {self.requester_port}")
            print(f"Sequence num: {seq}")
            print(f"payload: {payload.decode()}")
            print(f"total packet sent: {self.total_packet_sent}")
            print(f"total retransmit: {self.total_retransmit}")
            print(f"loss rate:{self.total_retransmit/self.total_packet_sent * 100} %")
            print(f"---------------------")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send packets")
    # use argparse to parse arguments
    parser.add_argument(
        "-p",
        help="The port on which the sender waits for requests",
        type=int,
        required=True,
    )
    parser.add_argument(
        "-g", help="The port on which the requester is waiting", type=int, required=True
    )
    parser.add_argument(
        "-r",
        help="The number of packets to be sent per second",
        type=int,
        required=True,
    )
    parser.add_argument(
        "-q",
        help="The initial sequence of the packet exchange",
        type=int,
        required=True,
    )
    parser.add_argument(
        "-l",
        help="The length of the payload (in bytes) in the packets",
        type=int,
        required=True,
    )
    parser.add_argument(
        "-f",
        help="The host name of the emulator",
        type=str,
        required=True,
    )
    parser.add_argument(
        "-e",
        help="The port of the emulator",
        type=int,
        required=True,
    )
    parser.add_argument(
        "-i",
        help="The priority of the sent packets",
        type=int,
        required=True,
    )
    parser.add_argument(
        "-t",
        help="The timeout for retransmission for lost packets in the unit of milliseconds",
        type=int,
        required=True,
    )
    args = parser.parse_args()

    if ((args.p <= 2049) or (args.p >= 65536)) or ((args.g <= 2049) or (args.g >= 65536)):
        print("Port number for both sender and requester should be 2049 < port < 65536")
        exit()

    sender = Sender(args.p, args.g, args.r, args.q, args.l, args.f, args.e, args.i, args.t)