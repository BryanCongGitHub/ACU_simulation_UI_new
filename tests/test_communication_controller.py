import queue
import socket
import threading
import time
from unittest.mock import patch

import pytest

from controllers.communication_controller import CommunicationController


class FakeSocket:
    """Minimal socket stub to track bind/close/send without touching real network."""

    def __init__(self, factory, index):
        self.factory = factory
        self.index = index
        self.bound = None
        self.closed = False
        self.sent_payloads = []
        self.recv_queue: "queue.Queue[tuple[bytes, tuple]]" = queue.Queue()

    def bind(self, addr):
        self.factory.bind_calls.append((self.index, addr))
        if self.index in self.factory.fail_on_bind:
            raise OSError("bind failed")
        if self.factory.block_index == self.index:
            self.factory.block_started.set()
            # Block until the test signals that setup may continue
            if not self.factory.unblock_event.wait(timeout=1.0):
                raise TimeoutError("block not released")
        self.bound = addr

    def setsockopt(self, *args, **kwargs):  # pragma: no cover - noop stub
        return None

    def settimeout(self, *args, **kwargs):  # pragma: no cover - noop stub
        return None

    def recvfrom(self, *args, **kwargs):
        if self.factory.raise_on_recv:
            raise self.factory.raise_on_recv
        try:
            return self.recv_queue.get(timeout=self.factory.recv_timeout)
        except queue.Empty:
            raise socket.timeout()

    def sendto(self, data, addr):
        self.sent_payloads.append((data, addr))

    def close(self):
        self.closed = True


class FakeSocketFactory:
    def __init__(self):
        self.instances = []
        self.bind_calls = []
        self.fail_on_bind = set()
        self.block_index = None
        self.block_started = threading.Event()
        self.unblock_event = threading.Event()
        self.recv_timeout = 0.05
        self.raise_on_recv = None

    def __call__(self, *_, **__):
        fake = FakeSocket(self, len(self.instances))
        self.instances.append(fake)
        return fake


def patch_sockets(factory):
    return patch('controllers.communication_controller.socket.socket', side_effect=factory)


def test_setup_is_idempotent_and_recycles_sockets():
    ctrl = CommunicationController()
    factory = FakeSocketFactory()

    with patch_sockets(factory):
        assert ctrl.setup() is True
        first_send, first_recv = factory.instances
        ctrl.update_config(acu_send_port=49200)
        assert ctrl.setup() is True

    second_send, second_recv = factory.instances[2:4]
    assert first_send.closed and first_recv.closed
    assert ctrl.send_sock is second_send
    assert ctrl.recv_sock is second_recv
    assert ctrl.running is True


def test_setup_failure_cleans_up_partial_state():
    ctrl = CommunicationController()
    factory = FakeSocketFactory()
    factory.fail_on_bind.add(1)  # Fail while binding recv socket

    with patch_sockets(factory):
        assert ctrl.setup() is False

    first_send = factory.instances[0]
    assert first_send.closed is True
    assert ctrl.send_sock is None
    assert ctrl.recv_sock is None
    assert ctrl.running is False


def test_stop_can_run_concurrently_with_setup():
    ctrl = CommunicationController()
    factory = FakeSocketFactory()
    factory.block_index = 1  # Block while binding recv socket to simulate long setup

    setup_result = {}

    def setup_target():
        with patch_sockets(factory):
            setup_result['value'] = ctrl.setup()

    setup_thread = threading.Thread(target=setup_target)
    setup_thread.start()

    # Wait until the recv socket bind is in progress
    assert factory.block_started.wait(timeout=1.0)

    stop_thread = threading.Thread(target=ctrl.stop)
    stop_thread.start()

    time.sleep(0.05)
    factory.unblock_event.set()  # Allow setup to finish

    setup_thread.join(timeout=1.0)
    stop_thread.join(timeout=1.0)

    assert setup_result.get('value') is True
    assert ctrl.running is False
    # All sockets should be closed by the stop() we invoked while setup was running
    assert all(sock.closed for sock in factory.instances)


def test_receive_loop_dispatches_packets():
    ctrl = CommunicationController()
    factory = FakeSocketFactory()
    received = []
    received_event = threading.Event()

    def on_receive(data, addr):
        received.append((data, addr))
        received_event.set()

    ctrl.on_receive = on_receive

    with patch_sockets(factory):
        assert ctrl.setup() is True
        assert ctrl.running is True
        ctrl.start_receive_loop()
        assert ctrl._receive_thread is not None and ctrl._receive_thread.is_alive()
        recv_socket = factory.instances[1]
        try:
            recv_socket.recv_queue.put((b"PAYLOAD", ("127.0.0.1", 50000)))
            assert received_event.wait(timeout=1.0)
        finally:
            ctrl.stop()

    assert received == [(b"PAYLOAD", ("127.0.0.1", 50000))]


def test_receive_loop_reports_errors():
    ctrl = CommunicationController()
    factory = FakeSocketFactory()
    factory.raise_on_recv = RuntimeError("boom")
    error_messages = []
    error_event = threading.Event()

    def on_error(msg):
        error_messages.append(msg)
        error_event.set()

    ctrl.on_error = on_error

    with patch_sockets(factory):
        assert ctrl.setup() is True
        ctrl.start_receive_loop()
        # Wait for the error propagation triggered by recvfrom raising RuntimeError
        assert error_event.wait(timeout=1.0)
        ctrl.stop()

    assert any("接收异常" in msg for msg in error_messages)