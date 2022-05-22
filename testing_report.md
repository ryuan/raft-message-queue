# Testing Report

At a basic level, the program passed every message_queue.py test, as well as all the election_test.py.

The message queue was rather simple, so aside from the pytest, I just manually tried every possible combination of message from the client to the single server.

For the election test, I tested manually on my own before running the pytest. Starting with 5 running servers, I cut one or more of them out to test tolerance of the system for node failures. The nodes are able to detect offline servers and elect a new leader as long as a majority of the original servers are still up and running. If a previous leader is killed, reactivating it starts it off as a follower again, and adjusts accordingly whether a new leaders was elected while it was gone.

Log replication - completed implementing and can pass manual test. Start multiple servers and PUT topics/messages to the leader. Leader will propagate the new entry to its peers, who will decide what to do with the AppendEntries RPC per rules outlined in `response_server`. If it chooses to append (follower term is not larger than that of the leader, and the logs have the same terms at the new entry's index), the log entry will be appended, attributes such as commit_index updated, and also commit any other entries in its log up to the commit_index. Heartbeats also serve the purpose of catching up the followers.

Manually testing, you can quit a server, then query the newly elected leader to see that it has all the same data in its state machine. Modifying the state machine, and then bringing back the previous leader node will replicate the modified log entries to the recovered node. You can prove this by now killing the newly elected leader node and try to get the original node back as leader (edit the election timer to be fastest among peers) and you can then GET the replicated data in its state machine.