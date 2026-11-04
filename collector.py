import re
import socket

import paramiko

# Fixed read-only commands. Inventory text is never interpolated into these.
CPU_COMMAND = "cat /proc/stat"
MEMORY_COMMAND = "free"
NETWORK_COMMAND = "cat /proc/net/dev"
PORTS_COMMAND = "ss -lntup"
PORTS_FALLBACK_COMMAND = "netstat -lntup"
DISK_COMMAND = "df -P"
TIMEOUT_SECONDS = 5


def collect_metrics(server, connect=None):
    """Read CPU, memory, network, and listening ports. Return an error string on failure."""
    opener = connect or open_ssh
    client = None
    try:
        client = opener(
            server["host"],
            int(server["port"]),
            server["ssh_user"],
            server["ssh_password"],
            TIMEOUT_SECONDS,
        )
        cpu_code, cpu_text = client.run(CPU_COMMAND)
        memory_code, memory_text = client.run(MEMORY_COMMAND)
        network_code, network_text = client.run(NETWORK_COMMAND)
        ports_code, ports_text = client.run(PORTS_COMMAND)
        if ports_code != 0:
            ports_code, ports_text = client.run(PORTS_FALLBACK_COMMAND)
        disk_code, disk_text = client.run(DISK_COMMAND)
        if cpu_code != 0 or memory_code != 0 or network_code != 0 or ports_code != 0:
            return {"error": "could not read metrics"}
        disk = None
        if disk_code == 0:
            try:
                disk = parse_disk(disk_text)
            except ValueError:
                disk = None
        return {
            "error": None,
            "cpu_percent": parse_cpu(cpu_text),
            "memory": parse_memory(memory_text),
            "network": parse_network(network_text),
            "ports": parse_ports(ports_text),
            "disk": disk,
        }
    except ValueError:
        return {"error": "could not read metrics"}
    except Exception as exc:
        return {"error": classify_error(exc)}
    finally:
        if client is not None:
            client.close()


def classify_error(exc):
    if isinstance(exc, paramiko.AuthenticationException):
        return "authentication failed"
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "timed out"
    message = str(exc).lower()
    if "timed out" in message or "timeout" in message:
        return "timed out"
    if "authentication" in message:
        return "authentication failed"
    return "unreachable"


def open_ssh(host, port, username, password, timeout):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=timeout,
            banner_timeout=timeout,
            auth_timeout=timeout,
            look_for_keys=False,
            allow_agent=False,
        )
    except Exception:
        client.close()
        raise
    return ParamikoSession(client, timeout)


class ParamikoSession:
    def __init__(self, client, timeout):
        self._client = client
        self._timeout = timeout

    def run(self, command):
        _stdin, stdout, stderr = self._client.exec_command(command, timeout=self._timeout)
        stdout.channel.settimeout(self._timeout)
        output = stdout.read().decode("utf-8", errors="replace")
        error_output = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        text = output if output.strip() else error_output
        return code, text

    def close(self):
        self._client.close()


def parse_cpu(text):
    for line in text.splitlines():
        if not line.startswith("cpu "):
            continue
        numbers = [int(part) for part in line.split()[1:]]
        total = sum(numbers)
        if total <= 0:
            return 0.0
        idle = numbers[3] if len(numbers) > 3 else 0
        iowait = numbers[4] if len(numbers) > 4 else 0
        busy = total - idle - iowait
        return round(100.0 * busy / total, 1)
    raise ValueError("missing cpu totals")


def parse_memory(text):
    for line in text.splitlines():
        if not line.startswith("Mem:"):
            continue
        parts = line.split()
        return {
            "total": int(parts[1]),
            "used": int(parts[2]),
            "free": int(parts[3]),
        }
    raise ValueError("missing memory totals")


def parse_network(text):
    interfaces = []
    for line in text.splitlines():
        if ":" not in line:
            continue
        name, _, rest = line.partition(":")
        name = name.strip()
        if not name or name.lower() == "face" or "|" in name:
            continue
        numbers = rest.split()
        if len(numbers) < 9:
            continue
        interfaces.append(
            {
                "interface": name,
                "bytes_in": int(numbers[0]),
                "bytes_out": int(numbers[8]),
            }
        )
    if not interfaces:
        raise ValueError("missing interface counters")
    return interfaces


def parse_disk(text):
    fullest = None
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 6 or parts[0] == "Filesystem":
            continue
        capacity = parts[-2]
        if not capacity.endswith("%"):
            continue
        percent = int(capacity[:-1])
        mount = parts[-1]
        if fullest is None or percent > fullest[0]:
            fullest = (percent, mount)
    if fullest is None:
        raise ValueError("missing disk totals")
    percent, mount = fullest
    return {"percent": percent, "mount": mount, "label": f"{percent}% on {mount}"}


def parse_ports(text):
    ports = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        if lowered.startswith(("netid", "state", "proto", "active")):
            continue
        process = ""
        users = re.search(r'users:\(\("([^"]+)"', line)
        program = re.search(r"(\d+)/(\S+)\s*$", line)
        if users:
            process = users.group(1)
            line = line[: users.start()]
        elif program:
            process = program.group(2)
            line = line[: program.start()]
        parts = line.split()
        if not parts:
            continue
        protocol = parts[0].lower()
        if protocol not in {"tcp", "udp", "tcp6", "udp6"}:
            continue
        if protocol.endswith("6"):
            protocol = protocol[:-1]
        local = next((part for part in parts if _has_port(part)), None)
        if local is None:
            continue
        address, port = _split_address(local)
        if port is None:
            continue
        ports.append(
            {
                "port": port,
                "protocol": protocol,
                "address": address,
                "process": process,
            }
        )
    return ports


def _has_port(value):
    _address, port = _split_address(value)
    return port is not None


def _split_address(value):
    if value.startswith("["):
        host, separator, port = value[1:].partition("]:")
        if separator and port.isdigit():
            return host, int(port)
        return None, None
    host, separator, port = value.rpartition(":")
    if separator and port.isdigit() and host:
        return host, int(port)
    return None, None
