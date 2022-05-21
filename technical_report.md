# Technical Report

## Part 1: Message Queue

Implementation was done by setting up a simple ZMQ REQ/RES sockets for all the operations. At this stage, there was only one thread that contains the listening process for the server to receive client operation calls.

Since I didn't use the ROUTER method, the risk of my approach was that there would be greater difficulties once communication between servers are implemented in the next step.

I created a LogManager object to store the log and state machine/data for each node.

Passed all the message queue tests.

## Part 2: Leadership Election

My implementation passed all 6 tests.

The setup is with 2 separate threads - one for listening to client calls and another dedicated for server calls.

I basically went through and implemented the requirements per Raft paper. All nodes start as a follower with a ResettableTimer object that counts down towards an election.

There's a `broadcast` method with RequestVote RPC to ask other nodes (detected upon startup by reading the config.json) for a vote. Whether a node gets a vote is determined by the parameters passed via the RPC - each node compares the arguments to its own relevant attributes. Each node can only vote once (this is recorded as an attribute), and the candidate will tally up the recorded during his running term and becomes leader if there's a majority.

The vote response from the follower nodes is communicated to the candidate via a direct message `send` process.

Once a candidate becomes a leader, a different ResettableTimer object is setup for the heartbeat. Heartbeats broadcast AppendEntries RPC with an empty entry along with other attributes required by Raft. The followers take the arguments, compares them to its own, and then confirms whether they acknowledge it by way of a successful append entry response.

The heartbeat also serves the purpose of catching up downed servers up. Even when no client requests are coming in, a recovered servered can get heartbeats, allowing it to compare it's log's latest index and term to make sure it's matching that of the leader.

## Part 3: Log Replication

This was difficult, and I had to do some large overhauls to my code from part 2. Instead of making direct access to the state machine, I now had server's state machine-altering calls pass through a `update_logs` process. This process broadcasts the request as a log entry (include term to the requested operation) and performs an AppenEntries RPC to the other nodes. This process will than go into a holding loop until the current entry is committed (or the leader fails to do so).

The other nodes received the request from the leader and checks the RPC parameters against its relevant attributes to determine what to do with it. If it determines that it can go forward with appending the entry, it appends the entry and updates its commit_index to minimum of the latest entry or the leader's commit_index. It then directly sends a message to the leader informing that the RPC was successful.

If the node cannot append the entry because its log is out of sync with that of the leaders, it will send the minimum index of the term that mismatched at the attempted index requested by the leader's RPC. This allows the system to avoid going back and forth many times, since the leader can just check if it has any entry with the follower's term, then return the maximum index of the entry with that term. Otherwise, attempt another AppendEntries RPC with an index 1 lower. This guarantees that the next attempted index is the maximum match (since the property of Raft is that any two logs with the same term at the same index is equivalent up to that point) or the greatest unknown/possible match.

The leader maintains a tally of each follower that has committed, and writes to the state machine once a majority replicated the log entry. This implies also that those followers have updated their commit_index as far as the leader and that they have the new entry in their logs. The leader can therefore now also commit any previous entries in its log prior to the most recent client operation/entry via the `catch_up` process.

Upon each new heartbeat, the updated commit_index from the leader can indicate to followers who have matching logs a the same indix with same terms that they can also commit the log entries to their state machines.