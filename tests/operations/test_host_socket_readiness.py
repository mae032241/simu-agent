"""Real Unix listener probes; no model turn or control request is sent."""
import socket

import pytest

from scripts.probe_root_host_live import control_socket_ready

pytestmark=pytest.mark.process_e2e


def test_socket_inode_without_listener_is_not_ready(tmp_path):
    path=tmp_path/'control.sock'
    assert not control_socket_ready(path)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(path))
        assert path.exists()
        assert not control_socket_ready(path)
        listener.listen(1)
        listener.settimeout(1)
        assert control_socket_ready(path)
        connection,_=listener.accept()
        with connection:
            assert connection.recv(1)==b''  # No RPC, identity or instance mutation.
    assert path.exists()
    assert not control_socket_ready(path)
