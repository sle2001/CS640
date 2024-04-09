import argparse
import socket
import struct

def trace(port, sourceHostName, sourcePort, destinationHostName, destinationPort, debugOption):
    hostIP = socket.gethostbyname(socket.gethostname()) # Get ip address of host
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # create socket object
    sock.bind((hostIP, int(port))) # Bind socket

    sourceIP = socket.gethostbyname(sourceHostName) # Get source ip
    destIP = socket.gethostbyname(destinationHostName) # Get destination ip
    liveTTL = 0

    # Start printing
    print(f"Hop#        IP,       Port")
    while True:
        # Construct packet
        returnPacket = struct.pack("!cLLHLH", b'T', liveTTL, struct.unpack("!L", socket.inet_aton(hostIP))[0], int(port), struct.unpack("!L", socket.inet_aton(destIP))[0], int(destinationPort))

        # Send packet
        sock.sendto(returnPacket, (sourceIP, int(sourcePort)))

        # Print debug
        if debugOption == "1":
            print(f"[SENT] TTL = {liveTTL}, Source = {hostIP}:{port}, Destination = {destIP}:{destinationPort}")

        # Wait for packet to return
        fullPacket, _ = sock.recvfrom(1024)

        # Get the return packet
        returnPacket = struct.unpack("!cLLHLH", fullPacket)

        # Get info from the return packet
        ttlIn = returnPacket[1] # Get TTL
        returnSourceIPNum = returnPacket[2] # Get Source IP
        returnSourcePort = returnPacket[3] # Get Source Port
        returnDestIPNum = returnPacket[4] # Get Destination IP
        returnDestPort = returnPacket[5] # Get Destination Port

        # Set source and destination IPs
        returnSourceIP = socket.inet_ntoa(struct.pack("!L", returnSourceIPNum))
        returnDestIP = socket.inet_ntoa(struct.pack("!L", returnDestIPNum))

        # Print debug info
        if debugOption == "1":
            print(f"[RECIEVED] TTL = {ttlIn}, Source = {returnSourceIP}:{returnSourcePort}, Destination = {returnDestIP}:{returnDestPort}")
        
        print(f" {liveTTL+1}    {returnSourceIP}, {returnSourcePort}") # Print info

        liveTTL += 1 # Increment TTL

        # Check if TTL is bigger than 30 or if source and destination IP and ports are the same
        if (liveTTL > 30) or ((returnSourceIP == returnDestIP) and (returnSourcePort == returnDestPort)):
            break

def main():

    parser = argparse.ArgumentParser() # Create parser

    # Add arguments to parser
    parser.add_argument('-a', metavar='routetracePort') # Get routetrace port
    parser.add_argument('-b', metavar='sourceHostname') # Get source host name
    parser.add_argument('-c', metavar='sourcePort') # Get source port
    parser.add_argument('-d', metavar='destinationHostname') # Get destination hostname
    parser.add_argument('-e', metavar='destinationPort') # Get destination port
    parser.add_argument('-f', metavar='debugOption') # Get debug option

    args = parser.parse_args() # Parse all arguments

    # Call trace function
    trace(args.a, args.b, args.c, args.d, args.e, args.f)

if __name__ == "__main__":
    main()