import socket
import threading
import time

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
BUFFER_SIZE = 4096
END_MARKER = "\n<<END>>\n"

OPERATIONS = {
    "1": "Date and Time",
    "2": "Uptime",
    "3": "Memory Use",
    "4": "Netstat",
    "5": "Current Users",
    "6": "Running Processes",
}
ALLOWED_COUNTS = {1, 5, 10, 15, 20, 25}


def recv_until_marker(connection: socket.socket) -> str:
    data = bytearray()
    marker = END_MARKER.encode("utf-8")

    while marker not in data:
        chunk = connection.recv(BUFFER_SIZE)
        if not chunk:
            break
        data.extend(chunk)

    decoded = data.decode("utf-8", errors="replace")
    if END_MARKER in decoded:
        decoded = decoded.split(END_MARKER, 1)[0]
    return decoded


def run_single_client_request(
    request_id: int,
    host: str,
    port: int,
    operation: str,
    timings: list[float | None],
    responses: list[str],
    errors: list[str],
) -> None:
    start = time.perf_counter()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.connect((host, port))
            client.sendall((operation + "\n").encode("utf-8"))
            response = recv_until_marker(client)

        elapsed = time.perf_counter() - start
        timings[request_id] = elapsed
        responses[request_id] = response
    except Exception as exc:
        timings[request_id] = None
        errors[request_id] = str(exc)


def prompt_host_port() -> tuple[str, int]:
    host_raw = input(f"Server network address [{DEFAULT_HOST}]: ").strip()
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


def prompt_operation() -> str:
    print("\nSelect operation:")
    print("1. Date and Time")
    print("2. Uptime")
    print("3. Memory Use")
    print("4. Netstat")
    print("5. Current Users")
    print("6. Running Processes")

    while True:
        choice = input("Enter 1-6: ").strip()
        operation = OPERATIONS.get(choice)
        if operation is not None:
            return operation
        print("Invalid selection. Enter 1-6.")


def prompt_request_count() -> int:
    print("\nHow many client requests? (1, 5, 10, 15, 20, 25)")
    while True:
        raw = input("Enter count: ").strip()
        try:
            count = int(raw)
            if count in ALLOWED_COUNTS:
                return count
        except ValueError:
            pass
        print("Invalid count. Choose one of: 1, 5, 10, 15, 20, 25.")


def main() -> None:
    host, port = prompt_host_port()
    operation = prompt_operation()
    request_count = prompt_request_count()

    timings: list[float | None] = [None] * request_count
    responses = [""] * request_count
    errors = [""] * request_count
    threads: list[threading.Thread] = []

    print(f"\nStarting {request_count} client session(s) for '{operation}' to {host}:{port}...")

    for request_id in range(request_count):
        thread = threading.Thread(
            target=run_single_client_request,
            args=(request_id, host, port, operation, timings, responses, errors),
            daemon=False,
        )
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    print("\nPer-request turn-around time (seconds):")
    success_times = []
    for index, elapsed in enumerate(timings, start=1):
        if elapsed is None:
            print(f"Request {index:>2}: FAILED ({errors[index - 1]})")
        else:
            success_times.append(elapsed)
            print(f"Request {index:>2}: {elapsed:.6f}")

    if success_times:
        total_time = sum(success_times)
        average_time = total_time / len(success_times)
        print(f"\nTotal Turn-around Time: {total_time:.6f} seconds")
        print(f"Average Turn-around Time: {average_time:.6f} seconds")

        print("\nSample server response from first successful request:\n")
        for response in responses:
            if response:
                print(response)
                break
    else:
        print("\nNo successful requests. Check server address/port and ensure the server is running.")


if __name__ == "__main__":
    main()
