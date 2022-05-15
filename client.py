from threading import Thread
import requests
import json
import sys
import time

def main(params):
    count_params = len(params)

    if count_params == 5:
        start_port = params[1]
        end_port = params[2]
        hashed_pw = params[3]
        max_length = params[4]

        if check_inputs(start_port, end_port, hashed_pw, max_length) == True:
            ports = [*range(int(start_port), int(end_port)+1)]
            num_chunks = len(ports)
            headers = {"Content-Type": "application/json"}
            data = {'hashed':hashed_pw, 'max_length':int(max_length), 'chunk_rank':0, 'num_chunks': num_chunks}
            threads = {}

            for i, port in enumerate(ports):
                url = f'http://127.0.0.1:{port}'
                data['chunk_rank'] = i+1

                thread = Thread(target=crack, args=(url,data,headers))
                print(f"thread_{i} created...")
                thread.start()
                print(f"thread_{i} started executing")
                threads[f"thread_{i}"] = thread

            for item in threads.items():
                thread = item[1]
                thread.join()

            print("Done executing program")

        else:
            print(f"""
            Fatal error checking arguments. exiting program.
            Usage: client.py <port> <md5_password> <max_password_length>
            """)
            sys.exit(0)
    else:
        print(f"""
        Program takes 4 arguments, but you provided {count_params}.
        Usage: client.py <start_port> <end_port> <md5_password> <max_password_length>
        """)
        sys.exit(0)


def crack(url, data, headers):
    retries = 1
    success = False
    while not success:
        try:
            request = requests.post(url + '/password', data=json.dumps(data), headers=headers)
            request_des = request.json()
            record_perf(request_des['performance'], data['num_chunks'])

            response = requests.get(url + '/password/' + data['hashed'])
            response_des = response.json()
            print(response_des['result'])

            success = True
        except:
            wait = retries * 10
            print(f'service unavailable: attempt to reconnect in {wait} secs...')
            sys.stdout.flush()
            time.sleep(wait)
            retries += 1


def record_perf(performance, num_chunks):
    with open('performance.txt', 'a') as f:
        for pw_len, time in performance.items():
            f.write(f'[{pw_len}, {num_chunks}, {time}]\n')


def check_inputs(start_port, end_port, hashed_pw, max_length):
    if start_port.isdigit() and end_port.isdigit() and max_length.isdigit():
        if len(hashed_pw) == 32 and hashed_pw.isalnum():
            return True
        else:
            print(f"""
            Argument md5_password needs to be a valid 32 character hexadecimal number.
            Usage: client.py <start_port> <end_port> <md5_password> <max_password_length>
            """)
            sys.exit(0)
    else:
        print(f"""
        Argument ports and max_password_length need to consist only of integers.
        Usage: client.py <start_port> <end_port> <md5_password> <max_password_length>
        """)
        sys.exit(0)

if __name__ == "__main__":
    main(sys.argv)