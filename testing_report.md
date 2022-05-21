# Testing Report

At a basic level, the program passed every message_queue.py test, as well as all the election_test.py.

The message queue was rather simple, so aside from the pytest, I just manually tried every possible combination of message from the client to the single server.

For the election test, I tested manually on my own before running the pytest. Starting with 5 running servers, I cut one or more of them out to test tolerance of the system for node failures. The nodes are able to detect offline servers and elect a new leader as long as a majority of the original servers are still up and running. If a previous leader is killed, reactivating it starts it off as a follower again, and adjusts accordingly whether a new leaders was elected while it was gone.

Log replication - mostly implemented but debugging one critical piece. WORKING STILL PLEASE AVOID GRADING UNLESS THERES ABSOLUTELY NO TIME.