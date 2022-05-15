from flask import request, jsonify, Flask
from math import ceil
import itertools
import string
import hashlib
import sys
import time

app = Flask(__name__)

passwords = {}

@app.route('/password/<path:path>', methods=['GET'])
def get_password(path):
    p = passwords[path]
    return jsonify(p), 200

@app.route('/password', methods=['POST'])
def crack_password():
    hashed = request.json['hashed']
    max_length = request.json['max_length']
    chunk_rank = request.json['chunk_rank']
    num_chunks = request.json['num_chunks']

    return_cached = False

    # check if cached result exists and should be returned
    if passwords.get(hashed) is not None:
        # return past result if it was resolved (i.e., not None)
        if passwords.get(hashed).get('result') is not None:
            return_cached = True
        else:
            # ...otherwise (case: result is None), check max_length of past attempts
            pw_perf = passwords[hashed]['performance']
            # extract the max number key from the cached result
            past_max_length = max(pw_perf, key=pw_perf.get)

            # return past result if past max_length was as long as that of current arg
            if past_max_length >= max_length:
                return_cached = True

    if return_cached == True:
        return jsonify(passwords[hashed]), 200
    else:    
        (result, performance) = bruteforce_password(hashed, max_length, chunk_rank, num_chunks)
        passwords[hashed] = {'result':result, 'performance':performance}
        return jsonify(passwords[hashed]), 200

def main(params):
    count_params = len(params)

    if count_params == 2:
        port = params[1]

        if port.isdigit():
            app.run(host='127.0.0.1', port=int(port), threaded=False)
    
        else:
            print(f"""
            Argument port needs to consist only of integers.
            Usage: cracker_service.py <port>
            """)
            sys.exit(0)
    else:
        print(f"""
        Program takes 1 arguments, but you provided {count_params}.
        Usage: cracker_service.py <port>
        """)
        sys.exit(0)

def bruteforce_password(hashed_password, max_length, chunk_rank, num_chunks):
        print("beginning bruteforce cracking...")

        chars = string.printable # all printable characters
        # chars = string.ascii_lowercase # lowercase characters
        num_chars = len(chars)
        chunk_size = num_chars/num_chunks
        # set the beginning and ending search space index
        beg_ss_idx = ceil((chunk_rank-1)*chunk_size)
        end_ss_idx = ceil(chunk_rank*chunk_size)
        first_chars = chars[beg_ss_idx:end_ss_idx+1]
        performance = {}

        for password_length in range(2, max_length+1):
            print(password_length)
            start = time.process_time()

            for char in first_chars:
                for guess in itertools.product(chars, repeat=password_length-1):
                    guess = ''.join(guess)
                    guess = char + guess
                    if hashlib.md5(guess.encode()).hexdigest() == hashed_password:
                        end = time.process_time() - start
                        print(end)
                        performance[password_length] = end
                        return (guess, performance)
            end = time.process_time() - start
            print(end)
            performance[password_length] = end
        return (None, performance)

if __name__ == "__main__":
    main(sys.argv)