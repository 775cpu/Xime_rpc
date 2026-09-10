import os
import sys
import traceback
import threading
import json

import server_http
import server_mqtt


MAX_LOG_BYTES = 5 * 1024 * 1024
RPC_CONFIG_PATH = "/sdcard/Alarms/xime_rpc.json"

def load_rpc_config():
    defaults = {
        "http_enabled": True,
        "http_port": 1144,
        "http_host": "0.0.0.0",
        "http_key": "",
        "mqtt_enabled": False,
        "mqtt_brokers": "broker.emqx.io:1883",
        "mqtt_request_topic": "sys/device/request",
        "mqtt_response_topic": "sys/device/response",
        "mqtt_pub_key": "",
    }
    try:
        with open(RPC_CONFIG_PATH, "r", encoding="utf-8") as config_file:
            values = json.load(config_file)
        if isinstance(values, dict):
            defaults.update(values)
    except (OSError, ValueError):
        pass
    return defaults


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
        config = load_rpc_config()
        server = thread = None
        if config.get('http_enabled', True):
            server, thread = server_http.start_rpc_server(
                port=int(config.get('http_port', 1144)),
                ip=str(config.get('http_host', '0.0.0.0')),
                key=str(config.get('http_key', '')),
                globals=globals(),
                locals=locals(),
            )
        mqtt_server = server_mqtt.start(config) if config.get("mqtt_enabled", False) else None
        print(f"[app.py] rpc config loaded, mqtt={mqtt_server is not None}")
        print(f"[app.py] HTTP={server} MQTT={mqtt_server} thread={thread}")
        return True
    except Exception:
        traceback.print_exc()
        return False
