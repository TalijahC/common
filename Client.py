"""
Multi-Threaded TCP Client
Spawns multiple concurrent client sessions to an iterative server.
Measures per-request and aggregate turn-around times.
"""

from __future__ import annotations
import socket
import struct
import threading
import time
import sys

# ── Constants ──────────────────────────────────────────────────────────────────
OPERATIONS = {
    '1': 'Date and Time',
    '2': 'Uptime',
    '3': 'Memory Use',
    '4': 'Netstat',
    '5': 'Current Users',
    '6': 'Running Processes',
}

VALID_COUNTS = [1, 5, 10, 15, 20, 25]

# ── Protocol helpers ───────────────────────────────────────────────────────────

def recvall(sock: socket.socket, n: int) -> bytes | None:
    """Read exactly n bytes from the socket."""
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def recv_msg(sock: socket.socket) -> str | None:
    """Receive a length-prefixed UTF-8 message."""
    raw = recvall(sock, 4)
    if raw is None:
        return None
    length = struct.unpack('!I', raw)[0]
    data = recvall(sock, length)
    return data.decode('utf-8') if data else None


def send_msg(sock: socket.socket, text: str) -> None:
    """Send a length-prefixed UTF-8 message."""
    encoded = text.encode('utf-8')
    sock.sendall(struct.pack('!I', len(encoded)))
    sock.sendall(encoded)

# ── Client session (runs in its own thread) ────────────────────────────────────

def client_session(
    host: str,
    port: int,
    operation: str,
    session_id: int,
    results: list,
    lock: threading.Lock,
    print_lock: threading.Lock,
) -> None:
    """
    Open a connection to the server, send the requested operation,
    receive the response, and record the turn-around time.
    """
    start = time.perf_counter()
    response = None
    error = None

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        send_msg(sock, operation)
        response = recv_msg(sock)
        sock.close()
    except Exception as exc:
        error = str(exc)
    finally:
        elapsed = time.perf_counter() - start

    # Thread-safe result storage
    with lock:
        results.append({
            'session_id': session_id,
            'elapsed':    elapsed,
            'response':   response,
            'error':      error,
        })

    # Thread-safe console output
    with print_lock:
        if error:
            print(f"  Session {session_id:>3}: ERROR — {error}")
        else:
            print(f"  Session {session_id:>3}: Turn-around time = {elapsed * 1000:.2f} ms")

# ── Input helpers ──────────────────────────────────────────────────────────────

def prompt(text: str, default: str = '') -> str:
    val = input(text).strip()
    return val if val else default


def prompt_int(text: str, valid: list[int]) -> int:
    while True:
        try:
            val = int(input(text).strip())
            if val in valid:
                return val
            print(f"    Please enter one of: {valid}")
        except ValueError:
            print(f"    Please enter one of: {valid}")


def prompt_choice(text: str, valid: list[str]) -> str:
    while True:
        val = input(text).strip()
        if val in valid:
            return val
        print(f"    Please enter one of: {list(valid)}")

# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 55)
    print("       Multi-Threaded Client")
    print("=" * 55)

    # 1. Network address and port
    host = prompt("Enter server address [default: 127.0.0.1]: ", '127.0.0.1')
    port_raw = prompt("Enter server port    [default: 12345]:    ", '12345')
    try:
        port = int(port_raw)
    except ValueError:
        print("Invalid port. Using 12345.")
        port = 12345

    # 2. Operation selection
    print("\nAvailable operations:")
    for key, name in OPERATIONS.items():
        print(f"  {key}. {name}")
    operation = prompt_choice("Select operation (1-6): ", list(OPERATIONS.keys()))

    # 3. Number of concurrent client sessions
    print(f"\nValid session counts: {VALID_COUNTS}")
    count = prompt_int("How many client requests to generate? ", VALID_COUNTS)

    # ── Launch threads ─────────────────────────────────────────────────────────
    op_name = OPERATIONS[operation]
    print(f"\nSpawning {count} concurrent session(s) → '{op_name}' @ {host}:{port}\n")

    results: list   = []
    lock            = threading.Lock()
    print_lock      = threading.Lock()
    threads         = []

    for i in range(1, count + 1):
        t = threading.Thread(
            target=client_session,
            args=(host, port, operation, i, results, lock, print_lock),
            daemon=True,
        )
        threads.append(t)

    # Start all threads simultaneously
    for t in threads:
        t.start()

    # Wait for all threads to complete
    for t in threads:
        t.join()

    # ── Aggregate statistics ───────────────────────────────────────────────────
    successful = [r for r in results if r['error'] is None]
    times_ms   = [r['elapsed'] * 1000 for r in successful]

    total_ms   = sum(times_ms)
    avg_ms     = total_ms / len(times_ms) if times_ms else 0.0

    print("\n" + "=" * 55)
    print("  RESULTS SUMMARY")
    print("=" * 55)
    print(f"  Operation             : {op_name}")
    print(f"  Sessions requested    : {count}")
    print(f"  Sessions successful   : {len(successful)}")
    print(f"  Sessions failed       : {count - len(successful)}")
    print("-" * 55)
    if times_ms:
        print(f"  Min turn-around time  : {min(times_ms):.2f} ms")
        print(f"  Max turn-around time  : {max(times_ms):.2f} ms")
        print(f"  Total turn-around time: {total_ms:.2f} ms")
        print(f"  Avg   turn-around time: {avg_ms:.2f} ms")
    print("=" * 55)

    # ── Show a sample server response ─────────────────────────────────────────
    if successful:
        sample = min(successful, key=lambda r: r['session_id'])
        print(f"\n--- Sample Response (Session {sample['session_id']}) ---")
        resp = sample['response'] or ''
        # Limit display to first 80 columns × 20 lines to keep output readable
        lines = resp.splitlines()[:20]
        for line in lines:
            print(line[:80])
        if len(resp.splitlines()) > 20:
            print(f"  ... ({len(resp.splitlines()) - 20} more lines)")
        print()


if __name__ == '__main__':
    main()
