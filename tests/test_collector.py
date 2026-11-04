import socket
import unittest

import paramiko

from collector import (
    CPU_COMMAND,
    MEMORY_COMMAND,
    NETWORK_COMMAND,
    DISK_COMMAND,
    PORTS_COMMAND,
    PORTS_FALLBACK_COMMAND,
    TIMEOUT_SECONDS,
    collect_metrics,
)

CPU = "cpu  100 0 50 850 0 0 0 0 0 0\ncpu0 100 0 50 850 0 0 0 0 0 0\n"
MEMORY = """\
              total        used        free      shared  buff/cache   available
Mem:        8000000     3000000     4000000      100000     1000000     4500000
Swap:             0           0           0
"""
NETWORK = """\
Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 10 1 0 0 0 0 0 0 20 1 0 0 0 0 0 0
  eth0: 1000 1 0 0 0 0 0 0 2000 1 0 0 0 0 0 0
"""
SS = """\
Netid State  Recv-Q Send-Q Local Address:Port Peer Address:PortProcess
tcp   LISTEN 0      128          0.0.0.0:22        0.0.0.0:*    users:(("sshd",pid=1,fd=3))
tcp   LISTEN 0      128             [::]:80           [::]:*    users:(("nginx",pid=2,fd=5))
"""
NETSTAT = """\
Active Internet connections (only servers)
Proto Recv-Q Send-Q Local Address           Foreign Address         State       PID/Program name
tcp        0      0 0.0.0.0:22              0.0.0.0:*               LISTEN      123/sshd
"""
DISK = """\
Filesystem 1024-blocks Used Available Capacity Mounted on
/dev/root 100 39 61 39% /
/dev/sda1 100 10 90 10% /boot
"""

SERVER = {
    "host": "10.1.1.8",
    "port": 22,
    "ssh_user": "monitor",
    "ssh_password": "ssh-secret-XYZZY-99",
}


class FakeSession:
    def __init__(self, outputs):
        self.outputs = outputs
        self.commands = []
        self.closed = False

    def run(self, command):
        self.commands.append(command)
        return self.outputs[command]

    def close(self):
        self.closed = True


class CollectorTests(unittest.TestCase):
    def test_good_parse_uses_only_fixed_commands(self):
        session = FakeSession(
            {
                CPU_COMMAND: (0, CPU),
                MEMORY_COMMAND: (0, MEMORY),
                NETWORK_COMMAND: (0, NETWORK),
                PORTS_COMMAND: (0, SS),
                DISK_COMMAND: (0, DISK),
            }
        )
        seen = {}

        def connect(host, port, username, password, timeout):
            seen.update(
                host=host,
                port=port,
                username=username,
                password=password,
                timeout=timeout,
            )
            return session

        result = collect_metrics(SERVER, connect=connect)
        self.assertIsNone(result["error"])
        self.assertEqual(result["cpu_percent"], 15.0)
        self.assertEqual(result["memory"], {"total": 8000000, "used": 3000000, "free": 4000000})
        self.assertEqual(
            result["network"],
            [
                {"interface": "lo", "bytes_in": 10, "bytes_out": 20},
                {"interface": "eth0", "bytes_in": 1000, "bytes_out": 2000},
            ],
        )
        self.assertEqual(
            result["ports"],
            [
                {"port": 22, "protocol": "tcp", "address": "0.0.0.0", "process": "sshd"},
                {"port": 80, "protocol": "tcp", "address": "::", "process": "nginx"},
            ],
        )
        self.assertEqual(
            session.commands,
            [CPU_COMMAND, MEMORY_COMMAND, NETWORK_COMMAND, PORTS_COMMAND, DISK_COMMAND],
        )
        self.assertEqual(result["disk"], {"percent": 39, "mount": "/", "label": "39% on /"})
        self.assertNotIn(SERVER["host"], " ".join(session.commands))
        self.assertNotIn(SERVER["ssh_password"], " ".join(session.commands))
        self.assertEqual(seen["timeout"], TIMEOUT_SECONDS)
        self.assertLessEqual(TIMEOUT_SECONDS, 5)
        self.assertTrue(session.closed)
        self.assertNotIn("ssh_password", result)
        self.assertNotIn("ssh_user", result)

    def test_timeout(self):
        session = FakeSession({})

        def connect(host, port, username, password, timeout):
            def run(_command):
                raise socket.timeout("timed out")

            session.run = run
            return session

        result = collect_metrics(SERVER, connect=connect)
        self.assertEqual(result, {"error": "timed out"})
        self.assertTrue(session.closed)

    def test_authentication_failure(self):
        def connect(host, port, username, password, timeout):
            raise paramiko.AuthenticationException("authentication failed")

        result = collect_metrics(SERVER, connect=connect)
        self.assertEqual(result, {"error": "authentication failed"})

    def test_ss_falls_back_to_netstat(self):
        session = FakeSession(
            {
                CPU_COMMAND: (0, CPU),
                MEMORY_COMMAND: (0, MEMORY),
                NETWORK_COMMAND: (0, NETWORK),
                PORTS_COMMAND: (127, "ss: not found"),
                PORTS_FALLBACK_COMMAND: (0, NETSTAT),
                DISK_COMMAND: (0, DISK),
            }
        )
        result = collect_metrics(SERVER, connect=lambda *args, **kwargs: session)
        self.assertEqual(
            result["ports"],
            [{"port": 22, "protocol": "tcp", "address": "0.0.0.0", "process": "sshd"}],
        )
        self.assertIn(PORTS_FALLBACK_COMMAND, session.commands)
        self.assertTrue(session.closed)


if __name__ == "__main__":
    unittest.main()
