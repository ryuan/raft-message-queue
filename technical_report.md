# Technical Report

## Part 1: Message Queue

Implementation was done by setting up a simple ZMQ REQ/RES sockets for all the operations. At this stage, there was only one thread that contains the listening process for the server to receive client operation calls.

Since I didn't use the ROUTER method, the risk of my approach was that there would be greater difficulties once communication between servers are implemented in the next step.

I created a LogManager object to store the log and state machine/data for each node.

Passed all the message queue tests.

## Part 2: Leadership Election

My implementation passed all 6 tests.

The setup is with 2 separate threads - 1 for listening to client calls and another dedicated for server calls.

I basically went through and implemented the requirements per Raft paper. All nodes start as a follower with a ResettableTimer object that counts down towards an election.

There's a broadcast method with RequestVote RPC to ask other nodes (detected upon startup by reading the config.json) for a vote. Whether a node gets a vote is determined by the parameters passed via the RPC - each node compares the arguments to its own relevant attributes. Each node can only vote once (this is recorded as an attribute), and the candidate will tally up the recorded during his running term and becomes leader if there's a majority.

The vote response from the follower nodes is communicated to the candidate via a direct message `send` process. 