import argparse
import socket
import struct
import time
import os
import copy

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Create socket
hostIP = socket.gethostbyname(socket.gethostname()) # Get host IP

def readtopology(topologyFile):
    routeTopology = {} # Topology of all routes

    currentLine = topologyFile.readline() # Get current line

    # Parse through topology.txt
    while len(currentLine) != 0:
        neighborParts = currentLine.split(" ") # Split each part by space
        routeTopology[neighborParts[0]] = []

        # For each part in the line
        for part in neighborParts[1:]:
            stripPart = part.strip() # Strip each part of the route
            routeTopology[neighborParts[0]].append(stripPart) # Append each port 

        currentLine = topologyFile.readline() # Get next line

    return routeTopology # Return the topology

def printTopology(routeTopology):
    print("Topology: \n")

    # For each route
    for host, neighbors in routeTopology.items():
        print(host, end=" ")
        
        # For each neighbor
        for neighbor in neighbors:
            print(neighbor, end=" ")
        
        print("")
    
    print("")

def printFowardTable(fowardTable):
    print("Fowarding Table: \n")

    # For each item in the foward table
    for host, info in fowardTable.items():
        # Check if there is any info left
        if (info[0] != 0):
            print(host, end=" ")
            print(info[1])
    
    print("")

def createroutes(routeTopology, fowardTable, thisPort):
    # Get the neighbors of the current emulator
    neighbors = routeTopology[f"{hostIP},{thisPort}"]

    latestTimeStamp = {}
    # Get the time stamps for each neighbor
    for neighbor in neighbors:
        latestTimeStamp[neighbor] = time.time()

    largestSeqNum = {}

    # Same as sock.settimeout(0.0), socket is set to non-blocking
    sock.setblocking(False)

    # Set message time and timeout
    helloMsgTime = time.time()
    helloMsgTimeout = 0.05

    lsmTime = time.time()
    lsmTimeout = 0.2

    # Timeout for death of a node
    nodeDeathTimeout = 2

    nextSeqNum = 1
    while True:
        # recieve packet
        try:
            fullPacket, (senderIP, senderPort) = sock.recvfrom(1024)
        except Exception:
            fullPacket = None

        if fullPacket:
            # If it is a helloMessage
            if fullPacket[0] == ord('H'):
                # Unpack header, IP, and Port
                header = struct.unpack("!BLH", fullPacket)
                sourcePort = header[2]
                sourceIP = socket.inet_ntoa(struct.pack("!L", header[1]))
                
                # Update the latest timestamp for receiving the helloMessage from the specific neighbor
                latestTimeStamp[f"{sourceIP},{sourcePort}"] = time.time()

                # Check the route topology stored in this emulator
                if not f"{sourceIP},{sourcePort}" in routeTopology or not f"{sourceIP},{sourcePort}" in routeTopology[f"{hostIP},{thisPort}"]:
                    # Update route topology
                    routeTopology = changeTopologyAdd(routeTopology, hostIP, thisPort, sourceIP, sourcePort)

                    # Make new fowarding table
                    fowardTable = buildForwardTable(routeTopology, f"{hostIP},{thisPort}")

                    # Print topology and foward table
                    printTopology(routeTopology)
                    printFowardTable(fowardTable)

                    # Send new message to neighbors
                    linkStateGenMsg = struct.pack("!cLHLL", b'L', struct.unpack("!L", socket.inet_aton(hostIP))[0], int(thisPort), nextSeqNum, 20)
                    
                    nextSeqNum += 1
                    
                    # Updated neighbors
                    for neighbor in routeTopology[f"{hostIP},{thisPort}"]:
                        neighborIP = struct.unpack("!L", socket.inet_aton(neighbor.split(",")[0]))[0]
                        neighborPort = int(neighbor.split(",")[1])
                        linkStateGenMsg += struct.pack("!LHL", neighborIP, neighborPort, 1)
                    
                    # Foward packet
                    forwardpacket(routeTopology, fowardTable, linkStateGenMsg, None, None, thisPort)

            elif fullPacket[0] == ord('L'): # If it is a LinkStateMessage
                # Unpack packet and get base IP, port, and sequence number
                headerNoNeighbor = struct.unpack("!LHLL", fullPacket[1:15])
                basePort = headerNoNeighbor[1]
                seqNum = headerNoNeighbor[2]
                baseIP = socket.inet_ntoa(struct.pack("!L", headerNoNeighbor[0]))

                neighbors = []
                numNeighbors = (len(fullPacket) - 15) // 10

                # For each neighbor
                for i in range(numNeighbors):
                    neighborStruct = fullPacket[(10*i+15):(10*i+25)] # Get struct of neighbor
                    neighborInfo = struct.unpack("!LHL", neighborStruct) # Get info of neighbor
                    neighbors.append(f"{socket.inet_ntoa(struct.pack('!L', neighborInfo[0]))},{neighborInfo[1]}") # Append the packet of neighbor

                # Check the largest sequence number of the sender node
                baseID = f"{baseIP},{basePort}"
                if not (baseID in largestSeqNum and seqNum <= largestSeqNum[baseID]):
                    largestSeqNum[baseID] = seqNum

                    # Check if topology has changed and update it
                    routeTopology, hasChanged = checkAndUpdateTopology(routeTopology, baseID, neighbors, f"{hostIP},{thisPort}")

                    # If the topology has changed
                    if hasChanged:
                        # Make new fowarding table
                        fowardTable = buildForwardTable(routeTopology, f"{hostIP},{thisPort}")

                        # Print topology and foward table
                        printTopology(routeTopology)
                        printFowardTable(fowardTable)

                    # Foward packets to its neighbors
                    forwardpacket(routeTopology, fowardTable, fullPacket, senderIP, senderPort, thisPort)

            # If it is a DataPacket / EndPacket / RequestPacket, forward it to the nexthop
            elif fullPacket[0] == ord('T') or fullPacket[0] == ord('R') or fullPacket[0] == ord('D') or fullPacket[0] == ord('E'):
                forwardpacket(routeTopology, fowardTable, fullPacket, None, None, thisPort)
        
        # Check if message timeout
        if (time.time() - helloMsgTime >= helloMsgTimeout):
            neighbors = routeTopology[f"{hostIP},{thisPort}"] # Get neighbors

            # Send hello message to all neighbors
            for neighbor in neighbors:
                neighborInfo = neighbor.split(",")
                hello_msg_packet = struct.pack("!cLH", b'H', struct.unpack("!L", socket.inet_aton(hostIP))[0], int(thisPort))
                sock.sendto(hello_msg_packet, (neighborInfo[0], int(neighborInfo[1])))
            
            # Reset timer
            helloMsgTime = time.time()

        # Check each neighbor
        keys = list(latestTimeStamp.keys()).copy()
        for key in keys:
            # Check if neighbor timeout
            if time.time() - latestTimeStamp[key] >= nodeDeathTimeout:
                # Remove neighbor
                routeTopology = removeNeighbor(routeTopology, key, f"{hostIP},{thisPort}", f"{hostIP},{thisPort}")
                del latestTimeStamp[key] # remove from timestamp tracking since we removed dead neighbor


                # Build new fowarding table
                fowardTable = buildForwardTable(routeTopology, f"{hostIP},{thisPort}")

                # Print topology and fowardd table
                printTopology(routeTopology)
                printFowardTable(fowardTable)

                # Update message to neighbor
                linkStateGenMsg = struct.pack("!cLHLL", b'L', struct.unpack("!L", socket.inet_aton(hostIP))[0], int(thisPort), nextSeqNum, 20)
                nextSeqNum += 1

                # Update neighbor IP and port in topology
                for neighbor in routeTopology[f"{hostIP},{thisPort}"]:
                    neighborIP = struct.unpack("!L", socket.inet_aton(neighbor.split(",")[0]))[0]
                    neighborPort = int(neighbor.split(",")[1])
                    linkStateGenMsg += struct.pack("!LHL", neighborIP, neighborPort, 1)

                # Foward packets to neighbors
                forwardpacket(routeTopology, fowardTable, linkStateGenMsg, None, None, thisPort)
        
        # Check if interval has passed
        if (time.time() - lsmTime >= lsmTimeout):
            # Updated message
            linkStateGenMsg = struct.pack("!cLHLL", b'L', struct.unpack("!L", socket.inet_aton(hostIP))[0], int(thisPort), nextSeqNum, 20)
            nextSeqNum += 1

            # Update IP and port for each neighbor in topology
            for neighbor in routeTopology[f"{hostIP},{thisPort}"]:
                neighborIP = struct.unpack("!L", socket.inet_aton(neighbor.split(",")[0]))[0]
                neighborPort = int(neighbor.split(",")[1])
                linkStateGenMsg += struct.pack("!LHL", neighborIP, neighborPort, 1)
            
            # Foward packet to neighbors
            forwardpacket(routeTopology, fowardTable, linkStateGenMsg, None, None, thisPort)
            
            lsmTime = time.time() # Update time

def forwardpacket(routeTopology, fowardTable, packet, originalIP, originalPort, thisPort):
    # Make original ID
    if(originalIP and originalPort):
        originalID = f"{originalIP},{originalPort}"
    
    # Check if packet is "L"
    if packet[0] == ord('L'):
        # Unpack portion of packet
        miniStruct = struct.unpack("!L", packet[11:15])
        ttl = miniStruct[0]
        packet = packet[0:11] + struct.pack("!L", ttl-1) + packet[15:]

        # If TTL is greater than 1
        if ttl > 1:
            neighbors = copy.deepcopy(routeTopology[f"{hostIP},{thisPort}"])
            if(originalIP and originalPort and originalID in neighbors):
                neighbors.remove(originalID)
            
            # Send packet to neighbors
            for neighbor in neighbors:
                neighborIP = neighbor.split(",")[0]
                neighborPort = int(neighbor.split(",")[1])
                sock.sendto(packet, (neighborIP, neighborPort))

    elif packet[0] == ord('T'): # Check if packet is "T"
        # Unpack return packet and get the ports, IPs, and TTL
        returnPacket = struct.unpack("!cLLHLH", packet)
        ttlIn = returnPacket[1]
        returnSourcePort = returnPacket[3]
        returnDestPort = returnPacket[5]
        returnSourceIP = socket.inet_ntoa(struct.pack("!L", returnPacket[2]))
        returnDestIP = socket.inet_ntoa(struct.pack("!L", returnPacket[4]))
        
        # Check if TTL is greater than 0
        if ttlIn > 0:
            # Make destiniation ID
            destID = f"{returnDestIP},{returnDestPort}"
            
            # Try to hop foward
            try:
                nextHop = fowardTable[destID][1]
                nextIP = nextHop.split(",")[0]
                nextPort = int(nextHop.split(",")[1])

                # Make new packet with a decrement TTL
                packet = packet[:1] + struct.pack("!L", ttlIn-1) + packet[5:]

                # Snet packet to the next port
                sock.sendto(packet, (nextIP, nextPort))
            except Exception:
                print(f"Cannot forward packet to {destID}")
        else:
            returnIP = returnSourceIP
            returnPort = returnSourcePort

            # Change source IP and port in packet
            packet = packet[0:5] + struct.pack("!L", struct.unpack("!L", socket.inet_aton(hostIP))[0]) + struct.pack("!H", int(thisPort)) + packet[11:]
            
            # Send new packet to the return port
            sock.sendto(packet, (returnIP, returnPort))

def buildForwardTable(routeTopology, rootNode):
    confirmedList = {}

    # Add root node
    confirmedList[rootNode] =  (0, -1)

    # Get all the neighbors
    rootNeighbors = routeTopology[rootNode]

    tentativeList = []
    # Add neighbor into list of neighbors
    for neighbor in rootNeighbors:
        tentativeList.append((neighbor, 1, neighbor))

    # Go through all neighbors
    while (len(tentativeList) > 0):
        nextNode = tentativeList.pop(0)
        nextNeighbors = routeTopology[nextNode[0]]

        # Check if each neighbor is in the list
        for neighbor in nextNeighbors:
            if not (neighbor in confirmedList or neighbor in [x[0] for x in tentativeList]):
                tentativeList.append((neighbor, nextNode[1] + 1, nextNode[2]))

        confirmedList[nextNode[0]] = (nextNode[1], nextNode[2])

    return confirmedList


def link_nodes(routeTopology, id1, id2):
    # Check if first ID is in the topology
    if id1 in routeTopology:
        if not id2 in routeTopology[id1]:
            routeTopology[id1].append(id2)
    else:
        routeTopology[id1] = [id2]

    # Check if second ID is in topology
    if id2 in routeTopology:
        if not id1 in routeTopology[id2]:
            routeTopology[id2].append(id1)
    else:
        routeTopology[id2] = [id1]

    return routeTopology
    

def changeTopologyAdd(routeTopology, baseIP, basePort, new_ip, new_port):
    # Create base and new IDs
    baseID = f"{baseIP},{basePort}"
    newID = f"{new_ip},{new_port}"
    
    # Make new topology
    routeTopology = link_nodes(routeTopology, baseID, newID)

    return routeTopology

def cleanRouteTopology(routeTopology, old_routeTopology, itemToAdd):
    routeTopology[itemToAdd] = old_routeTopology[itemToAdd]
    for item in routeTopology[itemToAdd]:
        if not item in routeTopology:
            routeTopology = cleanRouteTopology(routeTopology, old_routeTopology, item)
    return routeTopology

def removeNeighbor(routeTopology, id1, id2, thisID):
    # Check if first ID is in topology
    if id1 in routeTopology:
        # Check if second ID is in first ID's topology
        if id2 in routeTopology[id1]:
            routeTopology[id1].remove(id2) # Remove second ID

    # Check if second ID is in topology        
    if id2 in routeTopology:
        # Check if first ID is in second ID topology
        if id1 in routeTopology[id2]:
            routeTopology[id2].remove(id1) # Remove first ID

    # Print topology
    printTopology(routeTopology)

    # Clean up the topology
    routeTopology = cleanRouteTopology({}, routeTopology, thisID)

    return routeTopology

def checkAndUpdateTopology(routeTopology, baseID, neighbors, thisID):
    hasChanged = False

    # Check if base ID is in topology
    if baseID in routeTopology:
        if not sorted(neighbors) == sorted(routeTopology[baseID]):
            routeTopology[baseID] = neighbors
            for neighbor in neighbors:
                link_nodes(routeTopology, neighbor, baseID)
            hasChanged = True
            routeTopology = cleanRouteTopology({}, routeTopology, thisID)
    else:
        routeTopology[baseID] = neighbors
        for neighbor in neighbors:
            link_nodes(routeTopology, neighbor, baseID)
        hasChanged = True
        routeTopology = cleanRouteTopology({}, routeTopology, thisID)

    return (routeTopology, hasChanged)

def emulator(port, filename):
    # Bind socket
    try:
        sock.bind((hostIP, int(port)))
    except:
        print("A socket error has occured.")
        return 1

    # Open topology file
    try:
        trackerFile = open(os.path.dirname(__file__) + "/" + str(filename), "r")
    except:
        print("A file error has occurred.")
        return 1
    
    # Make topology route
    routeTopology = readtopology(trackerFile)
    printTopology(routeTopology) # Print topology

    # Build foward table
    fowardTable = buildForwardTable(routeTopology, rootNode=f"{hostIP},{port}")
    printFowardTable(fowardTable)

    # Create the routes
    createroutes(routeTopology, fowardTable, port)


def main():
    # Create parser
    parser = argparse.ArgumentParser()

    # Add arguments
    parser.add_argument('-p', metavar='port') # Get port
    parser.add_argument('-f', metavar='filename') # Get file name

    # Parse arguments
    args = parser.parse_args()

    emulator(args.p, args.f)

if __name__ == "__main__":
    main()