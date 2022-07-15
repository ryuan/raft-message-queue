# Technical Report

## Part 1: Message Queue

Implementation was done by setting up a simple ZMQ REQ/RES sockets for all the operations. Since I didn't use the ROUTER approach, I risked greater difficulties/complications once communication between servers are implemented in future steps.

I created a `LogManager` class to store the log and state machine/data for each node. Each node will initiate and manage its own log/state machine.

Upon starting a node, a new thread is created dedicated to listening to client requests via the `c_listen` method. Handling of the different client commands is done in the `respond_client` function, which gets passed the socket from `c_listen` and the specific client request message.

There are 3 client requests that impact the log/state machine: the 2 PUT commands (to add new topics and messages) and 1 GET command to pop a message. Checking whether an update is possible can be done by directly accessing the current data stored in the `LogManager`. If an update is possible, the `respond_client` process makes the update to the node's `LogManager` object, then returns the result to the client using the server's REP socket.

## Part 2: Leadership Election

A new thread is created upon node initialization via the `s_listen` method for listening to server intercommunication messages. Therefore, now there's a thread for listening to client calls and another thread dedicated to listening for server calls. The `respond_server` function handles each server request, which will contain logic for leadership election, log replication, and updates to the state machine.

For the election algorithm, I implemented the requirements according to the Raft paper. All nodes start as a follower with a `ResettableTimer` object that counts down towards an election. When a countdown reaches 0, the node begins the `start_election` process, which increments its `current_term` attribute (stored in the node's `LogManager`), resets the `votes_collected` attribute, which is its past vote record stored in its `LogManager`, and calls the `candidate` method to perform the new role's duties.

Upon becoming a candidate, the node resets the election countdown, votes for itself, and calls the `process_vote` method to records its own vote and verify if a majority of votes collected has voted for itself (i.e. at this stage, this can only happen if the swarm consists only of this node itself).

Finally, the `candidate` process calls a RequestVote RPC by leveraging the `broadcast` function. This asks all other nodes (detected upon startup by reading `config.json`) for a vote. `RequestVote` is implemented as a Python dataclass.

This is a good time to mention what intra-server messages look like, since they are implemented with the same format regardless of whether the message deals with votes, log entries, or state machine commitments. Essentially, they share a similar format to client API calls: they are Python dictionaries with `type`, `method`, and `message` keys. The `type` key can have values `vote`, `append` or `commit`, while the `method` key can be either `REQ` (requests) or `RES` (response). The `message` key contains all the data to satisfy the arguments and returned results as defined by the Raft paper. 

Whether a follower grants a vote is determined by the parameters passed via the RPC - each peer compares the arguments to its own relevant attributes. The vote response from each follower is directly communicated to the candidate using the `send_message` function, which initiates a context and REQ socket with the leader's IP and internal port. Each node can only vote once (stored in the `voted_for` attribute in its `LogManager`), and the candidate will tally up the votes using the `process_vote` method for the current term and becomes leader if there's a majority.

Once a candidate becomes a leader, the `leader` method is called, converting its role, stopping the election countdown, and calling the `heartbeat` method to inform the swarm that it won the election.

The `heartbeat` method assigns a `ResettableTimer` object to the node's `heartbeat_downdown` attribute. The timer calls the method itself when the countdown reaches 0. The process broadcasts AppendEntries RPC with an empty entry, along with other arguments and attributes of the node as required by Raft. The RPC is implemented as an `AppendEntries` dataclass sent to peers using the `broadcast` function.

This not only helps to reset election timers of the followers so that they remain as followers, but also helps to regularly update outdated logs of any followers (ex., downed servers) since the RPC contains information on the leader's latest index and its term. Even when no client requests are coming in, a recovered servered can get heartbeats, allowing it to compare it's log's latest index and term to make sure it's matching that of the leader.

Ultimately, the followers take the RPC arguments and determines whether they acknowledge the sender's leadership, and sends its decision/acknowledgement using the `send_message` function. The leader in turn takes the response message and checks if it should maintain leadership based on the term of the follower returned alongside the response message.

The fault tolerance of the system is robust: since each node maintains a list of peers in the swarm, the `broadcast` method will continuously send messages to downed servers. Any recovered server will begin as a follower and is guaranteed to receive a heartbeat from the leader before its election countdown reaches 0 (the heartbeat timers are half of the lower bound, randomly-generated number of any election countdown).

Once a leader is down, the remaining followers will campaign in elections with increasing term number via the `start_election` method until their election terms are greater than the term last known to the followers (updated and maintained each time they receive empty AppendEntries RPC from the previous leader's hearbeats).

This part also saw me update the `respond_client` method to refuse any client requests to a non-leader server.

## Part 3: Log Replication

I approached the implementation of log replication by thinking through the life cycle of the ideal scenario of a client request. The plan is to handle the ideal situation first, then, using that as the foundation, extend it by adding in different fault tolerance measures. This means that the initial log replication code assumes the swarm is stable and leader is always up once elected. Given this simplified context, once a client sends a command to the swarm, how does the message become a log entry at each node's log and eventually committed to its state machine?

First, the `repond_client` method was updated since the program now cannot directly edit the node's data directly. However, only the handling of 3 client requests need to be updated: PUT topic, PUT message, and GET message (since it pops from the state machine database). These three scenarios necessitate the calling of the `update_logs` method, which converts the client request into a log entry using the `LogManager`'s `make_entry` method. Each log entry is just the message/operation along with the leader's term (note: recall that only the leader can handle client requests after Part 2).

The process appends the log entry to the leader's own log using `append_to_log`, increments the `last_log_index` attribute (which keeps track of the highest index in the node's log), then broadcasts the log entry to the swarm for replication using the AppendEntries RPC. The `update_logs` process will then go into a holding loop until the current entry is committed (or the leader fails in this endeavor). It does this by storing the current entry in the node's `current_entry` instance variable and flagging the `current_entry_committed` attribute to `False`.

The other nodes receive the request from the leader and checks the RPC parameters against its relevant attributes to determine what to do with it. If it determines that it can go forward with appending the entry (recall that the initial implementation assumes no fault tolerance is needed, so leader is always alive and right), it appends the entry and updates its `commit_index` to minimum of the latest entry or the `leader_commit`. It then directly sends a message to the leader informing that the RPC was successful.

Eventually, when the fault tolerance measures are implemented, the node may determine that it cannot append the entry because its log is out of sync with that of the leader. In this case, it will send the minimum index of the term that mismatched at the attempted index requested by the leader's RPCs and that mismatched term (`min_index_of_term` and `term_at_req_index`, respectively).

This allows the system to avoid going back and forth many times, since the leader can just check if it has any entry with the follower's term, then return the maximum index of the entry with that term. In fact, this is an optimization recommended by the Raft paper, though it notes that this may be unnecessary for systems that rarely have server outages.

The other scenario is if, instead of a mismatched term at the requested index, no entry exists at all at the requested index (i.e., follower has a shorter log than the leader). Fortunately, our algorithm's `term_at_index` method will just take the `last_log_term` and provide the minimum index number where that term appears in the log as `min_index_of_term`. The leader would then call the `max_index_of_term` method to check if that term appears in its log and, if so, identify the maximum index. If not, it would attempt another AppendEntries RPC with an index 1 lower.

The above procedure guarantees that the next attempted index is the maximum possible match, since the property of Raft is that any two logs with the same term at the same index is equivalent up to that point.

When the leader sends the new AppendEntries RPC, it will send all the entries at once between that matched term index up to the log entry of the current client request, and the follower would replicate every entry sent by appending or overriding everything from that index onward with the new entries.

The leader maintains a tally of each follower that has appended the requested entry, and writes to the state machine once a majority has successfully replicated the log. This implies also that those followers have updated their `commit_index` as far as the leader and that they have the new entry in their logs. The leader can therefore now also commit any previous entries in its log prior to the most recent client operation/entry via the `catch_up` process.

Important thing to notice here: the leader does not commit anything in its log to its state machine until a new client request is received and the new log entry is replicated. Up until this point, its `commit_index` remains the same as it was when it was newly elected (either 0 or the inherited `commit_index` from an older term). This is because until it can coerce a majority of followers to replicate its log, there is a chance that the server will fail, causing potential issues related to overrides of its log entries by a new leader. Successfully appending a new entry to a majority of followers' logs implies that the bulk of nodes in the swarm now has the same log and a failure would lead to one of them taking over as the leader with the same log.

Upon each new heartbeat or response from the leader's commit, the followers can now commit to their logs to their state machines since those who have replicated the leader's log would have the same `commit_index` as the leader. Those nodes that were down during the AppendEntries RPC broadcast and recovered later would be guaranteed to not have been in touch with the leader and would therefore have a lower `commit_index`. These recovered servers would have to go through the process of catching up its log and incrementing its `commit_index` before writing to the state machine, which would by then guarantee that it's in the same state as the leader.