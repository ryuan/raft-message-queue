import zmq
import json
import sys
import time

MQ = {}

def server(ip, port):
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.setsockopt(zmq.LINGER, 0)
    socket.bind(f"tcp://{ip}:{port}")
    print(f"Bound to server on port {port}")

    try:
        while True:
            message = socket.recv_json()
            print("Received message: ", message)

            if message["type"] == "topic" and message["method"] == "PUT":
                if message["topic"] not in MQ and isinstance(message["topic"], str):
                    MQ[message["topic"]] = []
                    socket.send_json({"success": True})
                else:
                    socket.send_json({"success": False})
            elif message["type"] == "topic" and message["method"] == "GET":
                socket.send_json({"success": True, "topics": list(MQ.keys())})

            elif message["type"] == "message" and message["method"] == "PUT":
                if message["topic"] in MQ and isinstance(message["topic"], str) and isinstance(message["message"], str):
                    MQ[message["topic"]].append(message["message"])
                    socket.send_json({"success": True})
                else:
                    socket.send_json({"success": False})
            elif message["type"] == "message" and message["method"] == "GET":
                if isinstance(message["topic"], str) and MQ.get(message["topic"]):
                    socket.send_json({"success": True, "message": MQ[message["topic"]].pop(0)})
                else:
                    socket.send_json({"success": False})

            elif message["type"] == "status":
                socket.send_json({"role": "anything", "term": 0})
            else:
                socket.send_json({"fatal_failure": True})

            time.sleep(0.1)

    except KeyboardInterrupt:
        socket.close()
        context.term()


if __name__ == "__main__":
    this_file_name, config_path, node_id = sys.argv
    node_id = int(node_id)

    config_json = json.load(open(config_path))
    node_config = config_json["addresses"][node_id]
    ip, port = node_config["ip"], node_config["port"]
    server(ip, port)
