import os
import sys
import traceback

import rpc


class Tee:
    def __init__(self, stream, file_handle):
        self.stream = stream
        self.file_handle = file_handle

    def write(self, value):
        self.stream.write(value)
        self.file_handle.write(value)
        self.file_handle.flush()

    def flush(self):
        self.stream.flush()
        self.file_handle.flush()


def start(log_path):
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    log_file = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = Tee(sys.__stdout__, log_file)
    sys.stderr = Tee(sys.__stderr__, log_file)
    print("[PYTHON] Chaquopy RPC bootstrap started")
    try:
        server, thread = rpc.start_rpc_server(
            port=1144,
            globals=globals(),
            locals=locals(),
        )
        print(f"[app.py] {rpc} {server} {thread}")
        return True
    except Exception:
        traceback.print_exc()
        return False
