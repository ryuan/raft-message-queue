import zmq
import json
import sys
import time


def external_server(ip, port):
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.setsockopt(zmq.LINGER, 0)
    socket.bind(f"tcp://{ip}:{port}")
    print(f"Bound server {port}")

    try:
        while True:
            message = socket.recv_multipart()
            print("Received message: ", message)
            if message["type"] == "status":
                socket.send_multipart({"role": "anything", "term": 0})
            elif message["type"] == "message" and message["method"] == "PUT":
                socket.send_multipart({"success": True})
            elif message["type"] == "message" and message["method"] == "GET":
                socket.send_multipart({"success": True, "message": "anything"})
            elif message["type"] == "topic" and message["method"] == "PUT":
                socket.send_multipart({"success": True})
            elif message["type"] == "topic" and message["method"] == "GET":
                socket.send_multipart({"success": True, "topics": ["hello", "world"]})
            else:
                socket.send_multipart({"i have no idea": False})
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
    external_server(ip, port)
