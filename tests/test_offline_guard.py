import socket

import pytest


def test_real_network_access_is_blocked():
    with pytest.raises(RuntimeError, match="must not use the network"):
        socket.create_connection(("example.com", 80))
    with pytest.raises(RuntimeError, match="must not use the network"):
        socket.getaddrinfo("example.com", 80)
