# Testing Report


## Part 1: Message Queue Test
### All tests from message_queue_test.py passed (consistently)
At a basic level, the program passed every message_queue.py test, as well as all the election_test.py.

The message queue was rather simple, so aside from the pytest, I just manually tried every possible combination of message from the client to the single server.

In order to support manualy testing and refining of the code for the message queue, as well as in preparation of future testing of leadership election and log replication, I created a client.py file to send and receive messages. 

## Part 2: Leader Election Test
### All tests from election_test.py passed (6 fails occasionally due to `zmq.error.ZMQError: Resource temporarily unavailable`)

For the election test, I tested manually on my own before running the pytest. Starting with 5 running servers, I cut one or more of them out to test tolerance of the system for node failures. The nodes are able to detect offline servers and elect a new leader as long as a majority of the original servers are still up and running. If a previous leader is killed, reactivating it starts it off as a follower again, and adjusts accordingly whether a new leaders was elected while it was gone.

The program passes all 6 tests in election_test.py, but sometimes test 6 (and very rarely 4) fail due to the error: `zmq.error.ZMQError: Resource temporarily unavailable`. This seems to be due to pytest and not the program itself, since I have never been able to replicate the error, as well as posts on StackOverflow. How often the test fails seem to also be related to the timers for heartbeats and election countdowns, which indicate to me that pytest does not allocate enough memory or the sockets are not closed properly.

## Part 2: Leader Election Test
### All tests from election_test.py passed (6 fails occasionally due to zmq.error.ZMQError: Resource temporarily unavailable)

Both pytests pass, but the 2nd has a tedency to fail due to `zmq.error.ZMQError: Resource temporarily unavailable` error as in the election test. Manually testing what the second pytest is doing (PUT message, kill leader node, GET message from newly elected leader) shows that it works consistently.

In general, I believe all of the required log replication and commitment to the state machine is implemented thoroughly. Manually, start multiple servers and PUT topics/messages to the leader. Leader will propagate the new entry to its peers, who will decide what to do with the AppendEntries RPC per rules outlined in `response_server`. If it chooses to append (follower term is not larger than that of the leader, and the logs have the same terms at the new entry's index), the log entry will be appended, attributes such as commit_index updated, and also commit any other entries in its log up to the commit_index. Heartbeats also serve the purpose of catching up the followers.

You can quit a server, then query the newly elected leader to see that it has all the same data in its state machine. Modifying the state machine, and then bringing back the previous leader node will replicate the modified log entries to the recovered node. You can prove this by now killing the newly elected leader node and try to get the original node back as leader (edit the election timer to be fastest among peers) and you can then GET the replicated data in its state machine.