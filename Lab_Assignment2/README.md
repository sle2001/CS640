# Overview
In this project you will implement a network emulator and add reliable transfer to your distributed file transfer in the previous assignment. As with the first programming assignment, you can work in teams and write your code in Python. Please read on carefully.

## Network Emulator
For this programming assignment you will create a network emulator, which delivers packets between sender(s) and requester(s) you created for the first programming assignment. Your senders and requesters will have additional requirements to support the network emulator.

The network emulator will receive a packet, decide where it is to be forwarded, and, based on the packet priority level, queue it for sending. Upon sending, you will delay the packet to simulate link bandwidth, and randomly drop packets to simulate a lossy link.

We also ask you to implement packet priority queues, a common feature of many packet queueing algorithms. There will be three packet priority levels, and there will be a separate sending queue for each priority level. Each queue will have a fixed size. If the outbound queue for a particular priority level is full, the packet will be dropped. Higher priority packets are always forwarded before lower priority packets.

## Reliable Transfer
To achieve the reliable transfer, the requester will advertise a window size (see the requester specification of this write up for more info) to the sender with the request packet. The sender will send a full "window" of packets and wait for ACKs of each packet before sending more packets. After a certain timeout, the sender will retransmit the packets that it has not received an ack for.

