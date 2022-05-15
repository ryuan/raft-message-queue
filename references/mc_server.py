import zmq
import sys
import ipaddress


def main(params):
    count_params = len(params)

    if count_params == 4:
        ip = params[1]
        post_port = params[2]
        pub_port = params[3]

        if check_ip(ip) and post_port.isdigit() and pub_port.isdigit():
            # setup context (let ZMQ manage any open sockets and async I/O threads)
            context = zmq.Context()
            # create a response socket and bind/assign the host IP address and port to it
            s_post = context.socket(zmq.REP)
            s_post.bind(f"tcp://{ip}:{post_port}")
            # create a publisher socket and bind/assign the host IP address and port to it
            s_pub = context.socket(zmq.PUB)
            s_pub.bind(f"tcp://{ip}:{pub_port}")

            while True:
                """POST: blocking call to receive and store message"""
                # call ZMQ's recv_json method to deserialize the JSON message
                update = s_post.recv_multipart()

                print(f"echo data received from client: {update}")
                s_post.send_multipart(update)

                """PUB: publish the new message received on server"""
                # publish new messages as as they come in
                s_pub.send_multipart(update)

        else:
            print(f"""
            Argument IP needs to be in a proper IP address format.
            Argument ports needs to consist only of integers.
            Preferably, ports to listen on is a non-privileged port greater than 1023.
            Usage: pub_server.py <ip> <post_port> <pub_port>
            """)
            sys.exit(0)
    else:
        print(f"""
        Program takes 3 arguments, but you provided {count_params}.
        Usage: pub_server.py <ip> <post_port> <pub_port>
        """)
        sys.exit(0)

def check_ip(input):
    try:
        try_assign_ip = ipaddress.ip_address(input)
        return True
    except:
        return False

if __name__ == "__main__":
    main(sys.argv)