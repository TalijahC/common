"""
Iterative (Single-Threaded) TCP Server
Handles one client request at a time (serially).
Supports: Date/Time, Uptime, Memory Use, Netstat, Current Users, Running Processes
"""

from __future__ import annotations
import socket
import subprocess
import struct
import sys

# ── Configuration ──────────────────────────────────────────────────────────────
HOST = '0.0.0.0'   # Listen on all interfaces
PORT = 12345        # Change to match client if needed

# ── Command map ────────────────────────────────────────────────────────────────
COMMANDS = {
    '1': ('Date and Time',       ['date']),
    '2': ('Uptime',              ['uptime']),
    '3': ('Memory Use',          ['vm_stat']),           # macOS; replace with 'free -h' on Linux
    '4': ('Netstat',             ['netstat', '-an']),
    '5': ('Current Users',       ['who']),
    '6': ('Running Processes',   ['ps', 'aux']),
}

# ── Protocol helpers ───────────────────────────────────────────────────────────

def recvall(conn: socket.socket, n: int) -> bytes | None:
    """Read exactly n bytes from the socket."""
    buf = b''
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def recv_msg(conn: socket.socket) -> str | None:
    """Receive a length-prefixed UTF-8 message."""
    raw = recvall(conn, 4)
    if raw is None:
        return None
    length = struct.unpack('!I', raw)[0]
    data = recvall(conn, length)
    return data.decode('utf-8') if data else None


def send_msg(conn: socket.socket, text: str) -> None:
    """Send a length-prefixed UTF-8 message."""
    encoded = text.encode('utf-8')
    conn.sendall(struct.pack('!I', len(encoded)))
    conn.sendall(encoded)

# ── Request handler ────────────────────────────────────────────────────────────

def handle_client(conn: socket.socket, addr: tuple) -> None:
    """Process a single client connection and reply with command output."""
    print(f"  [+] Accepted connection from {addr[0]}:{addr[1]}")
    try:
        # 1. Receive client request
        request = recv_msg(conn)
        if request is None:
            print("  [!] Empty request — disconnecting.")
            return

        request = request.strip()
        print(f"  [>] Request received: '{request}'")

        # 2. Determine and execute the requested operation
        if request in COMMANDS:
            name, cmd = COMMANDS[request]
            print(f"  [*] Executing: {name}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            output = result.stdout if result.stdout else result.stderr
            if not output:
                output = "(no output)"
        else:
            output = f"ERROR: Unknown command '{request}'. Valid commands: 1-6."

        # 3. Reply to the client
        send_msg(conn, output)
        print(f"  [<] Response sent ({len(output)} bytes).")

    except Exception as exc:
        print(f"  [!] Error handling client: {exc}")
    finally:
        # 4. Clean up
        conn.close()
        print(f"  [-] Connection from {addr[0]}:{addr[1]} closed.\n")

# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind((HOST, PORT))
    except OSError as e:
        print(f"[ERROR] Cannot bind to {HOST}:{PORT} — {e}")
        sys.exit(1)

    # backlog=25 lets the OS queue up to 25 pending connections
    # while the server is busy with the current client (like Java's ServerSocket)
    server_sock.listen(25)
    print(f"Iterative Server started — listening on {HOST}:{PORT}")
    print("Supported operations:")
    for key, (name, _) in COMMANDS.items():
        print(f"  {key}. {name}")
    print("\nWaiting for connections... (Ctrl+C to stop)\n")

    try:
        while True:
            # Block until a client connects; handle it fully before accepting next
            conn, addr = server_sock.accept()
            handle_client(conn, addr)
    except KeyboardInterrupt:
        print("\n[INFO] Server shut down by user.")
    finally:
        server_sock.close()


if __name__ == '__main__':
    main()
