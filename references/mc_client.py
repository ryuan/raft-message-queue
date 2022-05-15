import zmq
import sys
import ipaddress
import time
import json
from threading import Thread


def main(params):
    count_params = len(params)
    channels = ["#all", "#dist-sys", "#gaming", "#life-hacks", "#fitness", "#music"]

    if count_params == 6:
        if check_ip(params[1]) and params[2].isdigit() and params[3].isdigit():
            if params[4] in channels:
                ip = params[1]
                post_port = params[2]
                pub_port = params[3]
                channel = params[4].lower()
                username = params[5]

                # make sure that thread running request socket is closed when channel is #all
                if channel != "#all":
                    thread_req = Thread(target=client_req, args=(ip, post_port, channel, username))
                    thread_req.start()
                thread_pub = Thread(target=client_sub, args=(ip, pub_port, channel))
                thread_pub.start()
            else:
                print(f"""
                You need to select a valid channel to join. Choose from options below...
                Usage: mc_client.py <ip> <post_port> <pub_port> <channel> <username>
                Channel Options: [#all, #dist-sys, #gaming, #life-hacks, #fitness, #music]
                """)
                sys.exit(0)
        else:
            print(f"""
            Argument IP needs to be in a proper IP address format.
            Argument ports and channel need to consist only of integers.
            Usage: mc_client.py <ip> <post_port> <pub_port> <channel> <username>
            Channel Options: [#all, #dist-sys, #gaming, #life-hacks, #fitness, #music]
            """)
            sys.exit(0)
    else:
        print(f"""
        Program takes 5 arguments, but you provided {count_params}.
        Usage: mc_client.py <ip> <post_port> <pub_port> <channel> <username>
        Channel Options: [#all, #dist-sys, #gaming, #life-hacks, #fitness, #music]
        """)
        sys.exit(0)

def client_req(ip, post_port, channel, username):
    # setup context (let ZMQ manage any open sockets and async I/O threads)
    context = zmq.Context()

    while True:
        # create a request socket for each new input (REQ sockets can send only once)
        s_req = context.socket(zmq.REQ)
        s_req.connect(f"tcp://{ip}:{post_port}")

        print(f"message channel {channel}: ")
        post_time = time.ctime()
        message = input()
        message = json.dumps({"username": username, "time": post_time, "message": message}).encode()

        # call ZMQ's send_json method to serialize via JSON and send the message
        s_req.send_multipart([channel.encode(),message])

def client_sub(ip, pub_port, channel):
    # setup context (let ZMQ manage any open sockets and async I/O threads)
    context = zmq.Context()
    # create a subscribe socket and connect to it
    s_sub = context.socket(zmq.SUB)

    # check if channel is #all, in which case receive all updates from server
    if channel == "#all":
        channel = ""
    s_sub.setsockopt(zmq.SUBSCRIBE, channel.encode())
    s_sub.connect(f"tcp://{ip}:{pub_port}")

    # constantly listen for updates from server, then print deserialized message
    while True:
        update = s_sub.recv_multipart()
        
        channel = update[0].decode()

        message = json.loads(update[1])
        username = message["username"]
        time = message["time"]
        message = message["message"]
        print(f"[{channel}] {username}: {message} ({time})")

def check_ip(input):
    try:
        try_assign_ip = ipaddress.ip_address(input)
        return True
    except:
        return False

if __name__ == "__main__":
    main(sys.argv)