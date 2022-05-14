import json
import sys
import time

import zmq


def external_server(port):
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.setsockopt(zmq.LINGER, 0)
    socket.bind(f"tcp://127.0.0.1:{port}")
    print(f"Bound server {port}")

    try:
        while True:
            message = socket.recv_json()
            print("Received message: ", message)
            if message["type"] == "status":
                socket.send_json({"role": "anything", "term": 0})
            else:
                socket.send_json({"i have no idea": False})
            time.sleep(0.1)
    except KeyboardInterrupt:
        socket.close()
        context.term()


if __name__ == "__main__":
    _this_file_name, config_path, node_id = sys.argv
    node_id = int(node_id)

    config_json = json.load(open(config_path))
    node_config = config_json["addresses"][node_id]
    ip, port = node_config["ip"], node_config["port"]
    external_server(port)
