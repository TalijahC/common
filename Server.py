import datetime
import platform
import socket
import subprocess
import time

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
BUFFER_SIZE = 4096
END_MARKER = "\n<<END>>\n"


class IterativeServer:
    """Single-threaded iterative TCP server (handles one request at a time)."""

    def __init__(self) -> None:
        self.start_time = time.time()
        self.boot_time = self._get_boot_time()
        self.handlers = {
            "DATETIME": self.get_datetime,
            "UPTIME": self.get_uptime,
            "MEMORY": self.get_memory_use,
            "NETSTAT": self.get_netstat,
            "USERS": self.get_current_users,
            "PROCESSES": self.get_running_processes,
            "HELP": self.get_help,
        }

    @staticmethod
    def _run_command(command: list[str]) -> str:
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except Exception as exc:
            return f"Error running {command!r}: {exc}"

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if result.returncode != 0:
            return stderr or f"Command failed with exit code {result.returncode}."
        return stdout or "No output."

    def _get_boot_time(self) -> float | None:
        system = platform.system().lower()

        if system == "linux":
            try:
                with open("/proc/uptime", "r", encoding="utf-8") as file:
                    uptime_seconds = float(file.read().split()[0])
                return time.time() - uptime_seconds
            except Exception:
                return None

        if system == "darwin":
            output = self._run_command(["sysctl", "-n", "kern.boottime"])
            for token in output.replace("{", " ").replace("}", " ").replace(",", " ").split():
                if token.isdigit() and len(token) >= 9:
                    return float(token)
            return None

        return None

    @staticmethod
    def _format_duration(seconds: float) -> str:
        total = int(seconds)
        days, rem = divmod(total, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, secs = divmod(rem, 60)
        return f"{days}d {hours}h {minutes}m {secs}s"

    @staticmethod
    def normalize_request(request: str) -> str:
        cleaned = " ".join(request.strip().upper().replace("_", " ").split())
        alias = {
            "DATE AND TIME": "DATETIME",
            "DATE TIME": "DATETIME",
            "DATETIME": "DATETIME",
            "UPTIME": "UPTIME",
            "MEMORY USE": "MEMORY",
            "MEMORY": "MEMORY",
            "NETSTAT": "NETSTAT",
            "CURRENT USERS": "USERS",
            "USERS": "USERS",
            "RUNNING PROCESSES": "PROCESSES",
            "PROCESSES": "PROCESSES",
            "HELP": "HELP",
            "QUIT": "QUIT",
        }
        return alias.get(cleaned, cleaned)

    def get_datetime(self) -> str:
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def get_uptime(self) -> str:
        if self.boot_time is not None:
            return f"Since boot: {self._format_duration(time.time() - self.boot_time)}"
        return f"Since server start: {self._format_duration(time.time() - self.start_time)}"

    def get_memory_use(self) -> str:
        system = platform.system().lower()
        if system == "linux":
            return self._run_command(["free", "-h"])
        if system == "darwin":
            vm_stat = self._run_command(["vm_stat"])
            top_one = self._run_command(["top", "-l", "1", "-n", "0"])
            return f"vm_stat:\n{vm_stat}\n\ntop memory summary:\n{top_one}"
        if system == "windows":
            return self._run_command(["wmic", "OS", "get", "FreePhysicalMemory,TotalVisibleMemorySize", "/Value"])
        return "Unsupported OS for memory usage command."

    def get_netstat(self) -> str:
        system = platform.system().lower()
        if system in {"linux", "darwin"}:
            return self._run_command(["netstat", "-an"])
        if system == "windows":
            return self._run_command(["netstat", "-ano"])
        return "Unsupported OS for netstat command."

    def get_current_users(self) -> str:
        system = platform.system().lower()
        if system in {"linux", "darwin"}:
            return self._run_command(["who"])
        if system == "windows":
            return self._run_command(["query", "user"])
        return "Unsupported OS for user listing command."

    def get_running_processes(self) -> str:
        system = platform.system().lower()
        if system in {"linux", "darwin"}:
            return self._run_command(["ps", "aux"])
        if system == "windows":
            return self._run_command(["tasklist"])
        return "Unsupported OS for process listing command."

    @staticmethod
    def get_help() -> str:
        return (
            "Valid operations: Date and Time, Uptime, Memory Use, Netstat, "
            "Current Users, Running Processes"
        )

    def process_request(self, request: str) -> str:
        command = self.normalize_request(request)

        if not command:
            return "Empty request."
        if command == "QUIT":
            return "BYE"

        handler = self.handlers.get(command)
        if handler is None:
            return (
                f"Unknown request '{request.strip()}'. "
                "Use one of: Date and Time, Uptime, Memory Use, Netstat, Current Users, Running Processes."
            )
        return handler()


def recv_line(connection: socket.socket) -> str | None:
    data = bytearray()
    while True:
        chunk = connection.recv(BUFFER_SIZE)
        if not chunk:
            return None
        data.extend(chunk)
        if b"\n" in data:
            break
    return data.decode("utf-8", errors="replace").split("\n", 1)[0]


def send_response(connection: socket.socket, text: str) -> None:
    connection.sendall((text + END_MARKER).encode("utf-8", errors="replace"))


def prompt_server_endpoint() -> tuple[str, int]:
    host_raw = input(f"Server listen address [{DEFAULT_HOST}]: ").strip()
    host = host_raw or DEFAULT_HOST

    while True:
        port_raw = input(f"Server port [{DEFAULT_PORT}]: ").strip()
        if not port_raw:
            return host, DEFAULT_PORT
        try:
            port = int(port_raw)
            if 1 <= port <= 65535:
                return host, port
        except ValueError:
            pass
        print("Enter a valid port between 1 and 65535.")


def run_server() -> None:
    host, port = prompt_server_endpoint()
    app = IterativeServer()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen()
        print(f"Iterative server listening on {host}:{port}")

        while True:
            connection, address = server.accept()
            with connection:
                request = recv_line(connection)
                if request is None:
                    continue

                response = app.process_request(request)
                send_response(connection, response)
                print(f"Handled request from {address[0]}:{address[1]} -> {request.strip()}")


if __name__ == "__main__":
    run_server()
