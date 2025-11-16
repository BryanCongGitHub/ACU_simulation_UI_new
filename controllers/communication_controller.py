import socket
import threading
from typing import Callable, Optional


class CommunicationController:
    """管理底层UDP通信，提供回调注册。"""

    def __init__(self):
        self.send_sock: Optional[socket.socket] = None
        self.recv_sock: Optional[socket.socket] = None
        self.running = False
        self.config = {
            "acu_ip": "10.2.0.1",
            "acu_send_port": 49152,
            "acu_receive_port": 49156,
            "target_ip": "10.2.0.5",
            "target_receive_port": 49152,
            "period_ms": 100,
        }
        self._receive_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self.on_receive: Optional[Callable[[bytes, tuple], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_status: Optional[Callable[[str], None]] = None

    def update_config(self, **cfg):
        with self._lock:
            self.config.update(cfg)
        self._emit_status(f"通信配置更新: {cfg}")

    def setup(self) -> bool:
        with self._lock:
            try:
                # 保证先清理已有资源，避免端口占用或线程冲突
                self._teardown(emit_status=False)
                self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                # 绑定发送端口（本地端口），若配置不合适会抛出异常
                self.send_sock.bind(("0.0.0.0", self.config["acu_send_port"]))
                self.recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.recv_sock.bind(("0.0.0.0", self.config["acu_receive_port"]))
                self.recv_sock.settimeout(0.5)
                self.running = True
                self._emit_status("Socket初始化成功")
                return True
            except Exception as e:
                self._emit_error(f"Socket初始化失败: {e}")
                # 如初始化失败，确保已经清理掉部分建立的资源
                self._teardown(emit_status=False)
                return False

    def start_receive_loop(self):
        with self._lock:
            if not self.running:
                return
            # 避免重复启动
            if self._receive_thread is not None and self._receive_thread.is_alive():
                return

            def _loop():
                self._emit_status("开始接收数据")
                while self.running:
                    try:
                        data, addr = self.recv_sock.recvfrom(1024)
                        if self.on_receive:
                            self.on_receive(data, addr)
                    except socket.timeout:
                        continue
                    except Exception as e:
                        if self.running:
                            self._emit_error(f"接收异常: {e}")

            self._receive_thread = threading.Thread(target=_loop, daemon=True)
            self._receive_thread.start()

    def send(self, data: bytes):
        try:
            with self._lock:
                if self.send_sock:
                    target = (
                        self.config["target_ip"],
                        self.config["target_receive_port"],
                    )
                    self.send_sock.sendto(data, target)
        except Exception as e:
            self._emit_error(f"发送错误: {e}")

    def stop(self):
        with self._lock:
            self._teardown(emit_status=True)

    def _teardown(self, emit_status: bool):
        # Close sockets/threads safely; emit status optionally.
        # 注意：调用此函数时应已持有 self._lock
        had_resources = any(
            [self.send_sock, self.recv_sock, self._receive_thread, self.running]
        )
        self.running = False
        if self.send_sock:
            try:
                self.send_sock.close()
            except Exception:
                pass
            self.send_sock = None
        if self.recv_sock:
            try:
                self.recv_sock.close()
            except Exception:
                pass
            self.recv_sock = None
        try:
            if (
                self._receive_thread is not None
                and threading.current_thread() is not self._receive_thread
            ):
                self._receive_thread.join(timeout=1.0)
        except Exception:
            pass
        finally:
            self._receive_thread = None
        if emit_status and had_resources:
            self._emit_status("通信已停止")

    def _emit_error(self, msg):
        if self.on_error:
            self.on_error(msg)

    def _emit_status(self, msg):
        if self.on_status:
            self.on_status(msg)
