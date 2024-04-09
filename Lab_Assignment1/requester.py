import argparse
import socket
from collections import defaultdict
from typing import DefaultDict, Tuple, List
import struct
from typing import Literal
from datetime import datetime
import time
import os.path


class Requester:
    # Initialize function
    def __init__(self, port: int, file_option: str) -> None:
        self.receive_port = port # The receiving port
        self.UDP_IP = socket.gethostbyname(socket.gethostname())
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Socket Creation
        self.sock.bind((self.UDP_IP, self.receive_port)) # Bind the socket
        self.file_option = file_option # Set the file option
        self.tracker_info = self.read_tracker() # Tracks the info
        self.sender_ports = [] # All the ports

        self.send_request() # Calls send_request

    # Function is to read tracker.txt
    def read_tracker(self) -> DefaultDict[str, List[Tuple[int, str, int]]]:
        info = defaultdict(list) # Info as a dictionary

        # Open the tracker file
        with open("tracker.txt", "r") as f:
            # For loop
            for line in f:
                # Read each line
                line = line.replace("\n", "").split(" ")
                # Put the info for each line in the dictionary
                info[line[0]].append((int(line[1]), socket.gethostbyname(line[2]), int(line[3])))

        # format: {file_option: [(ID, hostname, port), (ID, hostname, port)]} sorted by ID
        for s in info.values():
            s.sort(key=lambda x: x[0])

        return info

    # Function to send datagrams to UDP socket
    def send_request(self) -> None:
        # Create header
        header = struct.pack("!cII", "R".encode(), 0, 0)

        # Loop through all the information in tracker.txt
        for dest in self.tracker_info[self.file_option]:
            # Send the datagrams to the destination with sender's address and port
            self.sock.sendto(header + self.file_option.encode(), (dest[1], dest[2]))
            self.receive_file(dest[1], dest[2]) # Calls recieve file with address and port 

    # This function opens the file and write the packets into a text file and logs all the info
    def receive_file(self, sender_address, sender_port) -> None:
        start_time = time.time() # Start the time
        num_data_packets = 0 # Set variable for number of data packets
        total_byte = 0 # Set variable for total bytes
        packet, req_addr = self.sock.recvfrom(8192) # Get the packet and requester address from socket
        
        # Open the file
        with open(self.file_option, "a") as file:
            self.sender_ports.append(req_addr[0]) # Get the address of client socket or requester address
            header = packet[:9] # Get the header
            payload = packet[9:] # Get the payload
            headers = struct.unpack("!cII", header) # Unpack the header
            # Get the type of request, sequence, length, and the contents of the file
            request_type, sequence, length, file_content = (headers[0].decode(), socket.htonl(headers[1]), headers[2],payload)
            path = './' + self.file_option # Get path of the file
            file_size = os.stat(path).st_size # Get the size of the file

            # Check if the file exissts and if there is content inside
            if(os.path.isfile(path) and file_size != 0):
                file.write("\n") # Make a new line

            # Check if the type is D or not
            if request_type != "D":
                print(f"[Error] first packet recived should be a request with request type 'D', but got {request_type} instead.")
            
            # While the type isn't the end packet
            while request_type != "E":
                file.write(file_content.decode()) # Write the contents inside the file
                num_data_packets += 1 # Increment the number of data packets
                total_byte += length # Increase the total bytes with the length
                packet, req_addr = self.sock.recvfrom(8192) # Get the packet and requester address from socket
                self.sender_ports.append(req_addr[0]) # Get the address
                header = packet[:9] # Get header
                payload = packet[9:] # Get payload
                headers = struct.unpack("!cII", header) # Unpack the header
                if(headers[0].decode() == "E"):
                    self.log_info(sender_address, sender_port, "D", sequence, length + 1, file_content) # Log the info of the DATA packet
                else:
                    self.log_info(sender_address, sender_port, "D", sequence, length, file_content) # Log the info of the DATA packet
                # Get the request type, sequence, length, and contents of file
                request_type, sequence, length, file_content = (headers[0].decode(), socket.htonl(headers[1]), headers[2], payload,)
        
        self.log_info(sender_address, sender_port, "E", sequence, len(payload), b"") # Logo the info of the END packet
        duration = int((time.time() - start_time) * 1000) # Get the time it took to complete all the packets
        avg_time_per_packet = round(num_data_packets / (duration / 1000)) # Get the average time for each packet
        
        self.log_Summary(sender_address, sender_port, num_data_packets, total_byte, duration, avg_time_per_packet) # Log the summary

    # Function that logs the info
    def log_info(self, sender_address: str, sender_port: str, type: Literal["D", "E"], seq: int, length: int, payload: bytes) -> None:
        # Check if it's a DATA packet ("D") or END packet ("E") and print the info
        if type == "D":
            print(f"DATA Packet")
            print(f"recv time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
            print(f"sender addr: {sender_address}:{sender_port}")
            print(f"Sequence num: {seq}")
            print(f"length: {length}")
            print(f"payload: {payload[:4].decode()}")
            print(f"")
        elif type == "E":
            print(f"END Packet")
            print(f"recv time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
            print(f"sender addr: {sender_address}:{sender_port}")
            print(f"Sequence num: {seq+1}")
            print(f"length: {length}")
            print(f"payload: 0")
            print(f"")

    # This function logs the summary
    def log_Summary(self, sender_address: str, sender_port: str, num_data_packets: int, total_byte: int, duration: int, avg_time_per_packet: int,) -> None:
        print("Summary")
        print(f"sender addr: {sender_address}:{sender_port}")
        print(f"Total Data packets: {num_data_packets}")
        print(f"total Data bytes: {total_byte + 1}")
        print(f"Average packets/second: {avg_time_per_packet}")
        print(f"Duration of the test: {duration}ms")
        print("")

# Main function
def main():
    # Make a parser to parse arguments
    parser = argparse.ArgumentParser(description="Request packets")

    # Add arguments
    parser.add_argument("-p", type=int, required=True) # Add port argument
    parser.add_argument("-o", type=str, required=True) # Add output file argument

    # Parse the arguments
    args = parser.parse_args()

    if (args.p <= 2049) or (args.p >= 65536):
        print("Port number for both sender and requester should be 2049 < port < 65536")
        exit()
    else:
        # Call class Requester to request for the packets
        Requester(args.p, args.o)


# Calls the main function
if __name__ == "__main__":
    main()