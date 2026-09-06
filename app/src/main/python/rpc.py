import sys, io, urllib.parse, threading, traceback, struct, base64, hashlib, socket, logging, asyncio, textwrap, inspect, ast
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

_stdout_lock = threading.Lock()

def get_bmp_bytes(rgb=None, size=(16, 16)):
    if not rgb: rgb = (255, 0, 0)
    if isinstance(size, int): size = [size, size]
    width, height = size
    r, g, b = (max(0, min(255, c)) for c in rgb)
    bgr_color = bytes([b, g, r])
    bytes_per_pixel = 3
    bytes_per_row = (width * bytes_per_pixel + 3) // 4 * 4
    pixel_data_size = bytes_per_row * height
    file_size = 14 + 40 + pixel_data_size
    bmp_header = struct.pack('<2sIII', b'BM', file_size, 0, 54)
    bmp_info = struct.pack('<IIIHHIIIIII', 40, width, height, 1, 24, 0, pixel_data_size, 3780, 3780, 0, 0)
    pixels = b''
    for _ in range(height):
        row = bgr_color * width
        padding = b'\x00' * (bytes_per_row - len(row))
        pixels += row + padding
    return bmp_header + bmp_info + pixels

def pretty_format(obj, width=120):
    if isinstance(obj,str):return obj
    try:
        from IPython.lib.pretty import pretty
        return pretty(obj, max_width=width)
    except ImportError:
        try:
            from pprint import pformat
            return pformat(obj, width=width)
        except:
            return repr(obj)

def stime():
    import time
    ft = time.time()
    return time.strftime('%Y-%m-%d__%H.%M.%S', time.localtime(ft)) + '__.' + f"{ft:.3f}".split('.')[1]
#

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

class WebSocket:
    """Small text WebSocket connection used by the RPC server."""
    def __init__(self, handler):
        self.handler = handler
        self.socket = handler.connection
        self.send_lock = threading.Lock()
        self.closed = False

    def send(self, message):
        if isinstance(message, str):
            message = message.encode('utf-8')
        if len(message) >= 126:
            if len(message) < 65536:
                header = struct.pack('!BBH', 0x81, 126, len(message))
            else:
                header = struct.pack('!BBQ', 0x81, 127, len(message))
        else:
            header = bytes((0x81, len(message)))
        with self.send_lock:
            self.socket.sendall(header + message)

    def receive(self):
        """Return the next text message, or None when the peer disconnects."""
        fragments = []
        while True:
            header = self._read_exact(2)
            if not header:
                return None
            first, second = header
            final = bool(first & 0x80)
            opcode = first & 0x0f
            masked = bool(second & 0x80)
            length = second & 0x7f
            if length == 126:
                length = struct.unpack('!H', self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack('!Q', self._read_exact(8))[0]
            mask = self._read_exact(4) if masked else b''
            payload = bytearray(self._read_exact(length))
            if masked:
                for index in range(length):
                    payload[index] ^= mask[index % 4]
            if opcode == 0x8:
                self.close()
                return None
            if opcode == 0x9:
                self._send_control(0xA, payload)
                continue
            if opcode in (0x1, 0x0):
                fragments.append(bytes(payload))
                if final:
                    return b''.join(fragments).decode('utf-8')
                continue
            if opcode == 0xA:
                continue
            raise ValueError(f'unsupported WebSocket opcode: {opcode}')

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                with self.send_lock:
                    self.socket.sendall(b'\x88\x00')
            except OSError:
                pass

    def _send_control(self, opcode, payload=b''):
        with self.send_lock:
            self.socket.sendall(bytes((0x80 | opcode, len(payload))) + payload)

    def _read_exact(self, size):
        data = b''
        while len(data) < size:
            chunk = self.socket.recv(size - len(data))
            if not chunk:
                return b''
            data += chunk
        return data

class RPCRequestHandler(BaseHTTPRequestHandler):
    key = ''
    globals_dict = None
    locals_dict={}
    favicon_bytes = None
    websocket_handler = None
    websocket_handlers = {}
    websocket_path = '/ws'
    redirect_root = None
    main_loop = None  # 记录主线程的 event loop
    
    def log_message(self, format, *args):
        print(f"[RPC] {stime()[12:]}  {self.client_address[0]}:{self.client_address[1]} {format % args}")
        
    def do_GET(self):
        websocket_path = self.path.split('?', 1)[0]
        websocket_handler = self.websocket_handlers.get(websocket_path, self.websocket_handler)
        if (websocket_handler and (websocket_path == self.websocket_path or websocket_path in self.websocket_handlers)
            and self.headers.get('Upgrade', '').lower() == 'websocket'):
            self.handle_websocket(websocket_handler)
            return
        if self.path == '/' and self.redirect_root:
            self.send_response(302)
            self.send_header('Location', self.redirect_root)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        if self.path == '/favicon.ico' and self.favicon_bytes:
            self.send_response(200)
            self.send_header('Content-Type', 'image/x-icon')
            self.send_header('Cache-Control', 'max-age=86400')
            self.send_header('Content-Length', str(len(self.favicon_bytes)))
            self.end_headers()
            self.wfile.write(self.favicon_bytes)
            return
        self.handle_rpc()

    def handle_websocket(self, websocket_handler):
        self.protocol_version = 'HTTP/1.1' 
        
        key = self.headers.get('Sec-WebSocket-Key')
        if not key or self.headers.get('Sec-WebSocket-Version') != '13':
            self.send_error(400, 'WebSocket version 13 and key are required')
            return
            
        accept = base64.b64encode(hashlib.sha1(
            (key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode('ascii')
        ).digest()).decode('ascii')
        
        self.send_response(101, 'Switching Protocols')
        self.send_header('Upgrade', 'websocket')
        self.send_header('Connection', 'Upgrade')
        self.send_header('Sec-WebSocket-Accept', accept)
        self.end_headers()
        
        websocket = WebSocket(self)
        try:
            websocket_handler(websocket, self)
        except (ConnectionError, BrokenPipeError, socket.error):
            pass
        except Exception:
            traceback.print_exc()
        finally:
            websocket.close()
            
    def do_POST(self):
        self.handle_rpc()
        
    def _execute_coroutine(self, coro, exec_globals):
        """核心机制：将协程抛给主业务的事件循环执行，彻底解决 aiohttp 跨线程/未在 task 中运行的问题"""
        target_loop = self.main_loop
        # 如果启动时没指定 loop，尝试在全局变量里智能寻找（比如 tracker._loop）
        if not target_loop or not target_loop.is_running():
            for v in exec_globals.values():
                if hasattr(v, '_loop') and isinstance(v._loop, asyncio.AbstractEventLoop) and v._loop.is_running():
                    target_loop = v._loop
                    break
                if isinstance(v, asyncio.AbstractEventLoop) and v.is_running():
                    target_loop = v
                    break

        if target_loop and target_loop.is_running():
            # 使用 threadsafe 会自动将其包裹为 Task 执行，满足 aiohttp 要求
            future = asyncio.run_coroutine_threadsafe(coro, target_loop)
            return future.result() 
        else:
            # 降级方案：当前线程如果没有找到主循环，就新建一个（不适用于依赖上下文的库如 aiohttp）
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

    def handle_rpc(self):
        try:
            raw_path = self.path
            if self.key:
                prefix = self.key + '/'
                if not raw_path.startswith(prefix):
                    self.send_error(403, "Forbidden")
                    return
                code_str = raw_path[len(prefix):]  
            else:            
                if raw_path.startswith('/'):
                    raw_path = raw_path[1:]
                code_str = raw_path
            if not code_str:
                self.send_error(400, "No code")
                return
            code = urllib.parse.unquote(code_str)

            exec_globals = self.globals_dict.copy() if self.globals_dict else {}
            exec_globals['__name__'] = '__rpc_exec__'
            exec_globals['request'] = self
            exec_globals['q'] = self
            class ResponseWrapper:
                def __init__(self):
                    self.status = 200
                    self.headers = {}
                    self.data = None
                def set_data(self, data):
                    self.data = data
                def set_status(self, code):
                    self.status = code
                def set_header(self, key, value):
                    self.headers[key] = value
            resp = ResponseWrapper()
            exec_globals['response'] = resp
            exec_globals['p'] = resp
            try:
                with _stdout_lock:
                    old_stdout = sys.stdout
                    sys.stdout = io.StringIO()
                    try:
                        try:
                            compiled_code = compile(code, '<rpc>', 'exec')
                            exec(compiled_code, exec_globals, self.locals_dict)
                        except SyntaxError as se:
                            if 'await' in code:
                                indented_code = textwrap.indent(code, '    ')
                                try:
                                    dummy_tree = ast.parse(f"async def _():\n{indented_code}")
                                    body = dummy_tree.body[0].body
                                    is_single_expr = (len(body) == 1 and isinstance(body[0], ast.Expr))
                                except Exception:
                                    is_single_expr = False

                                if is_single_expr:
                                    async_code = f"async def __rpc_async__():\n    return ({code})"
                                else:
                                    async_code = f"async def __rpc_async__():\n{indented_code}\n    return locals()"

                                exec_globals_async = exec_globals.copy()
                                exec_globals_async.update(self.locals_dict)
                                exec(async_code, exec_globals_async, self.locals_dict)
                                coro_func = self.locals_dict.pop('__rpc_async__')
                                coro = coro_func()

                                # 核心：派发执行
                                res_locals = self._execute_coroutine(coro, exec_globals)
                                
                                if isinstance(res_locals, dict):
                                    self.locals_dict.update(res_locals)
                                elif res_locals is not None:
                                    self.locals_dict['r'] = res_locals
                            else:
                                raise se
                        output = sys.stdout.getvalue()
                    finally:
                        sys.stdout = old_stdout

                if resp.data is not None:
                    result_obj = resp.data
                elif 'r' in self.locals_dict:
                    result_obj = self.locals_dict['r']
                elif 'r' in exec_globals:
                    result_obj = exec_globals['r']
                elif output:
                    result_obj = output
                else:
                    result_obj = f"no 'r' variable, locals keys: {list(exec_globals.keys())}"

                # 不要 处理直接赋值未写 await，但得到一个 coroutine 的情况（例如: r = tracker.get_klines() ）
                # if inspect.isawaitable(result_obj):
                    # result_obj = self._execute_coroutine(result_obj, exec_globals)
                    # if 'r' in self.locals_dict and inspect.isawaitable(self.locals_dict.get('r')):
                        # self.locals_dict['r'] = result_obj

                result_str = pretty_format(result_obj)
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    self.send_header(k, v)
            except Exception as e:
                result_str = traceback.format_exc()
                logging.getLogger("error").exception(
                    "RPC execution failed client=%s path=%s code=%s",
                    self.client_address, self.path, code[:500],
                )
                self.send_response(500)
            
            if 'Content-Type' not in resp.headers:
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            
            if resp.data is not None:
                body = resp.data
                if isinstance(body, str):
                    body = body.encode('utf-8')
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    logging.getLogger("app").info("RPC client disconnected before response path=%s", self.path)
            else:
                try:
                    self.wfile.write(result_str.encode('utf-8'))
                except (BrokenPipeError, ConnectionResetError):
                    logging.getLogger("app").info("RPC client disconnected before response path=%s", self.path)
        except Exception as e:
            if not isinstance(e, (BrokenPipeError, ConnectionResetError)):
                self.send_error(500, str(e))

def start_rpc_server(port=1133, key='', ip='0.0.0.0', globals=None, locals=None, daemon=True,
                     favicon_rgb=None, favicon_size=16, websocket_handler=None,
                     websocket_path='/ws', redirect_root=None, websocket_handlers=None,
                     main_loop=None): # <--- 增加了 main_loop 参数
    if not key:key = ''
    RPCRequestHandler.key = key
    RPCRequestHandler.globals_dict = globals if globals else {}
    RPCRequestHandler.locals_dict = locals if locals is not None else {}
    RPCRequestHandler.websocket_handler = websocket_handler
    RPCRequestHandler.websocket_path = websocket_path
    RPCRequestHandler.websocket_handlers = websocket_handlers or {}
    RPCRequestHandler.redirect_root = redirect_root
    RPCRequestHandler.main_loop = main_loop # 绑定主循环
    
    if favicon_rgb is None:
        favicon_rgb = (port // 100, port % 100, 0)
    RPCRequestHandler.favicon_bytes = get_bmp_bytes(rgb=favicon_rgb, size=favicon_size)
    server = ThreadedHTTPServer((ip, port), RPCRequestHandler)
    thread = threading.Thread(target=server.serve_forever, name='RPC_Server', daemon=daemon)
    thread.start()
    server.thread = thread
    print(f"[RPC] {stime()} server at http://{ip}:{port}/{key}")
    return server

def qpsu(url="http://192.168.1.100/D%3A/test/qpsu.zip",write_to=''):
    import urllib.request, zipfile, io, sys, importlib.abc, importlib.machinery
    data = urllib.request.urlopen(url).read()
    z = zipfile.ZipFile(io.BytesIO(data))
    class ZipImporter(importlib.abc.PathEntryFinder):
        def __init__(self, zf): self.zf = zf
        def find_spec(self, fullname, path=None, target=None):
            pkg_path = fullname.replace('.', '/') + '/__init__.py'  
            if pkg_path in self.zf.namelist():
                return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
            mod_path = fullname.replace('.', '/') + '.py'  
            if mod_path in self.zf.namelist():
                return importlib.machinery.ModuleSpec(fullname, self)
            return None
        def create_module(self, spec): return None
        def exec_module(self, module):
            fullname = module.__name__
            pkg_path = fullname.replace('.', '/') + '/__init__.py'  
            if pkg_path in self.zf.namelist():
                code = self.zf.read(pkg_path).decode('utf-8')
                module.__path__ = []  
                module.__file__ = f"<zip://{pkg_path}>"  
                exec(code, module.__dict__)
                return
            mod_path = fullname.replace('.', '/') + '.py'
            code = self.zf.read(mod_path).decode('utf-8')
            module.__file__ = f"<zip://{mod_path}>"  
            exec(code, module.__dict__)
    sys.meta_path.insert(0, ZipImporter(z))
    from qgb import py,U,T,N,F
    return py,U,T,N,F
    
if __name__ == '__main__':
    start_rpc_server(port=1144, key='', globals=globals(),locals=locals())
    # import sys;'qgb.U' in sys.modules or sys.path.append('C:/QGB/Anaconda3/Lib/site-packages/Pythonwin/');from qgb import *
    input("Press Ctrl+C or anykey to stop\n")