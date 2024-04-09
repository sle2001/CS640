import argparse
import socket
import struct
import math
import time
from typing import Literal
from datetime import datetime

# This class send packets to the requester
class Sender:
    # Initialize function
    def __init__(self, port: int, requester_port: int, rate: int, seq_no: int, length: int) -> None:
        self.listen_port = port # Port on which the sender waits for requests
        self.requester_port = requester_port # Port on which the requester is waiting
        self.requester_address = None # Address of the requester
        self.rate = rate # Number of packets per second
        self.seq_no = seq_no # Sequence number
        self.length = length # Length of payload (in bytes) in the packets
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Create a socket
        self.UDP_IP = socket.gethostbyname(socket.gethostname())
        self.sock.bind((self.UDP_IP, self.listen_port)) # Bind the socket with the port and UDP IP
        self.sock.settimeout(60)
        self.listen_to_request() # Calls function "listen_to_request"

    # This function listens to the request
    def listen_to_request(self) -> None:
        try:
            packet, req_addr = self.sock.recvfrom(8192) # Get the packet and requester address
            self.requester_address = req_addr[0] # Get the requester address
            header = packet[:9] # Get the header
            payload = packet[9:] # Get the payload
            headers = struct.unpack("!cII", header) # Unpack the header
            request_type, file_requested = headers[0].decode(), payload.decode() # Get the request type and the file that is requested
            # Check if the request type is R
            if request_type != "R":
                print(
                    f"[Error] Should get a request with request type 'R', but got {request_type} instead."
                )

            self.send_file(file_requested) # Calls function "send_file" 
        except TimeoutError:
            print("[Error] Waited too long for the request, exiting...")

    # This function sends the file to the requester
    def send_file(self, filename: str) -> None:
        # read in the requested file
        content = b""
        with open(filename, "r") as f:
            content = f.read().encode()

        file_size = len(content) # Get the size of the file

        last_payload_length = 0 # Variable for the very last payload in DATA packet

        headers = [] # For the headers
        seq_nums = [] # For the sequence numbers

        # Check if the file size is smaller than the length
        if file_size <= self.length:
            headers.append(struct.pack("!cII", "D".encode(), socket.htonl(self.seq_no), file_size)) # Append the current header
            seq_nums.append(self.seq_no) # Append the current sequence number
            self.seq_no += file_size # Add the file size to the total sequence number
            last_payload_length = file_size # Get the length of the payload
        else:
            num_packets = math.ceil(file_size / self.length) # Get the number of packets
            last_payload_length = file_size % self.length # Get the length of the last payload
            
            # Loop through all the packets
            for i in range(num_packets):
                # Check if it's the last packet or not
                if i == num_packets - 1:
                    # last packet
                    headers.append(struct.pack("!cII", "D".encode(), socket.htonl(self.seq_no), last_payload_length)) # Append the current header
                    seq_nums.append(self.seq_no) # Append the current sequence number
                    self.seq_no += last_payload_length # Add the length to the total sequence number
                else:
                    headers.append(struct.pack("!cII", "D".encode(), socket.htonl(self.seq_no), self.length)) # Append the current header
                    seq_nums.append(self.seq_no) # Append the current sequence number
                    self.seq_no += self.length # Add the length to the total sequence number

        file_parts = [] # Variable for all the parts of the file

        # Loop through all the headers
        for i in range(len(headers)):
            file_parts.append(content[i * self.length : (i + 1) * self.length]) # Get the parts of the file of each header

        header_and_payload = [header + payload for header, payload in zip(headers, file_parts)] # Combine the header and paylaod

        # send the packets with rate limit, don't need to wait for ACK
        for i in range(len(header_and_payload)):
            self.sock.sendto(header_and_payload[i], (self.requester_address, self.requester_port)) # Send the DATA packet

            # Check if it's the last DATA packet
            if(i != len(header_and_payload) - 1):
                self.log_info("D", seq_nums[i], self.length, file_parts[i]) # Log DATA packet info
            else:
                self.log_info("D", seq_nums[i], (last_payload_length+1), file_parts[i]) # Log DATA packet info

            time.sleep(1 / self.rate)

        # send END packet
        self.sock.sendto(struct.pack("!cII", "E".encode(), socket.htonl(self.seq_no), 0), (self.requester_address, self.requester_port))
        self.log_info("E", self.seq_no, last_payload_length, b"") # Logo info of END packet

    # Logs all the info for all the packets
    def log_info(self, type: Literal["D", "E"], seq: int, length: int, payload: bytes) -> None:
        if type == "D":
            print(f"DATA Packet")
            print(f"send time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
            print(f"requester addr: {self.requester_address}:{self.requester_port}")
            print(f"Sequence num: {seq}")
            print(f"length: {length}")
            print(f"payload: {payload[:4].decode()}")
            print("")
        elif type == "E":
            print(f"send time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
            print(f"requester addr: {self.requester_address}:{self.requester_port}")
            print(f"Sequence num: {seq+1}")
            print(f"length: 0")
            print(f"payload: {payload.decode()}")

# Main function that sets up arguments and call the class "Sender"
def main():
    # Create a parser
    parser = argparse.ArgumentParser(description="Send packets")

    # Add arguments to the parser
    parser.add_argument("-p", type=int, required=True)
    parser.add_argument("-g", type=int, required=True)
    parser.add_argument("-r", type=int, required=True)
    parser.add_argument("-q", type=int, required=True)
    parser.add_argument("-l", type=int, required=True)

    # Get the arguments from parser
    args = parser.parse_args()

    if ((args.p <= 2049) or (args.p >= 65536)) or ((args.g <= 2049) or (args.g >= 65536)):
        print("Port number for both sender and requester should be 2049 < port < 65536")
        exit()
    else:
        # Call class sender to send all the packets
        Sender(args.p, args.g, args.r, args.q, args.l)

# Calls main function
if __name__ == "__main__":
    main()