import zmq
import json
import sys
import time

def client(ip, port):
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect(f"tcp://{ip}:{port}")
    print(f"Connected to server on port {port}")

    try:
        while True:
            message = {}

            type = input("type: ")
            message["type"] = type
            method = input("method: ")
            message["method"] = method
            if type == "message" or method == "PUT":
                topic = input("topic: ")
                message["topic"] = topic
                if type == "message" and method == "PUT":
                    text = input("message: ")
                    message["message"] = text

            print("Preparing to send message ", message)
            socket.send_json(message)

            print("Message sent!")

            response = socket.recv_json()
            print("Received message from server: ", response)
            
    except KeyboardInterrupt:
        socket.close()
        context.term()


if __name__ == "__main__":
    _this_file_name, config_path, node_id = sys.argv
    node_id = int(node_id)

    config_json = json.load(open(config_path))
    node_config = config_json["addresses"][node_id]
    ip, port = node_config["ip"], node_config["port"]
    client(ip, port)