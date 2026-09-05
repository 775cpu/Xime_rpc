import os
import sys
import traceback
import threading

import rpc


MAX_LOG_BYTES = 5 * 1024 * 1024


class LimitedLogFile:
    def __init__(self, path, max_bytes=MAX_LOG_BYTES):
        self.path = path
        self.max_bytes = max_bytes
        self.lock = threading.Lock()
        self.file = open(path, "a+b", buffering=0)

    def write(self, value):
        data = value.encode("utf-8") if isinstance(value, str) else value
        with self.lock:
            self.file.seek(0, 2)
            if self.file.tell() + len(data) > self.max_bytes:
                keep = self.max_bytes // 2
                self.file.seek(-min(keep, self.file.tell()), 2)
                tail = self.file.read()
                self.file.seek(0)
                self.file.truncate()
                self.file.write(tail)
            self.file.seek(0, 2)
            self.file.write(data)

    def flush(self):
        with self.lock:
            self.file.flush()


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
    log_file = LimitedLogFile(log_path)
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
