import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class Client {
    private static final String DEFAULT_HOST = "127.0.0.1";
    private static final int DEFAULT_PORT = 5000;
    private static final int BUFFER_SIZE = 4096;
    private static final String END_MARKER = "\n<<END>>\n";

    private static final Map<String, String> OPERATIONS = new HashMap<>();
    private static final Set<Integer> ALLOWED_COUNTS = new HashSet<>();

    static {
        OPERATIONS.put("1", "Date and Time");
        OPERATIONS.put("2", "Uptime");
        OPERATIONS.put("3", "Memory Use");
        OPERATIONS.put("4", "Netstat");
        OPERATIONS.put("5", "Current Users");
        OPERATIONS.put("6", "Running Processes");

        ALLOWED_COUNTS.add(1);
        ALLOWED_COUNTS.add(5);
        ALLOWED_COUNTS.add(10);
        ALLOWED_COUNTS.add(15);
        ALLOWED_COUNTS.add(20);
        ALLOWED_COUNTS.add(25);
    }

    private static String recvUntilMarker(Socket socket) throws IOException {
        StringBuilder data = new StringBuilder();
        BufferedReader reader = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
        char[] buffer = new char[BUFFER_SIZE];
        int read;
        while ((read = reader.read(buffer)) != -1) {
            data.append(buffer, 0, read);
            if (data.indexOf(END_MARKER) >= 0) {
                break;
            }
        }
        String decoded = data.toString();
        int markerIndex = decoded.indexOf(END_MARKER);
        if (markerIndex >= 0) {
            decoded = decoded.substring(0, markerIndex);
        }
        return decoded;
    }

    private static void runSingleClientRequest(
        int requestId,
        String host,
        int port,
        String operation,
        List<Double> timings,
        List<String> responses,
        List<String> errors
    ) {
        long start = System.nanoTime();
        try (Socket client = new Socket(host, port)) {
            PrintWriter writer = new PrintWriter(new OutputStreamWriter(client.getOutputStream(), StandardCharsets.UTF_8), true);
            writer.print(operation + "\n");
            writer.flush();

            String response = recvUntilMarker(client);
            double elapsed = (System.nanoTime() - start) / 1_000_000_000.0;
            timings.set(requestId, elapsed);
            responses.set(requestId, response);
        } catch (Exception exc) {
            timings.set(requestId, null);
            errors.set(requestId, exc.getMessage());
        }
    }

    private static String promptLine(BufferedReader reader, String prompt, String defaultValue) throws IOException {
        System.out.print(prompt);
        String raw = reader.readLine();
        if (raw == null) {
            return defaultValue;
        }
        raw = raw.trim();
        return raw.isEmpty() ? defaultValue : raw;
    }

    private static int promptPort(BufferedReader reader, String prompt, int defaultPort) throws IOException {
        while (true) {
            System.out.print(prompt);
            String raw = reader.readLine();
            if (raw == null || raw.trim().isEmpty()) {
                return defaultPort;
            }
            try {
                int port = Integer.parseInt(raw.trim());
                if (port >= 1 && port <= 65535) {
                    return port;
                }
            } catch (NumberFormatException ignored) {
            }
            System.out.println("Enter a valid port between 1 and 65535.");
        }
    }

    private static String promptOperation(BufferedReader reader) throws IOException {
        System.out.println("\nSelect operation:");
        System.out.println("1. Date and Time");
        System.out.println("2. Uptime");
        System.out.println("3. Memory Use");
        System.out.println("4. Netstat");
        System.out.println("5. Current Users");
        System.out.println("6. Running Processes");

        while (true) {
            System.out.print("Enter 1-6: ");
            String choice = reader.readLine();
            if (choice != null) {
                choice = choice.trim();
            }
            String operation = OPERATIONS.get(choice);
            if (operation != null) {
                return operation;
            }
            System.out.println("Invalid selection. Enter 1-6.");
        }
    }

    private static int promptRequestCount(BufferedReader reader) throws IOException {
        System.out.println("\nHow many client requests? (1, 5, 10, 15, 20, 25)");
        while (true) {
            System.out.print("Enter count: ");
            String raw = reader.readLine();
            if (raw != null) {
                raw = raw.trim();
            }
            try {
                int count = Integer.parseInt(raw);
                if (ALLOWED_COUNTS.contains(count)) {
                    return count;
                }
            } catch (Exception ignored) {
            }
            System.out.println("Invalid count. Choose one of: 1, 5, 10, 15, 20, 25.");
        }
    }

    public static void main(String[] args) throws IOException {
        BufferedReader console = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        String host = promptLine(console, "Server network address [" + DEFAULT_HOST + "]: ", DEFAULT_HOST);
        int port = promptPort(console, "Server port [" + DEFAULT_PORT + "]: ", DEFAULT_PORT);
        String operation = promptOperation(console);
        int requestCount = promptRequestCount(console);

        List<Double> timings = new ArrayList<>();
        List<String> responses = new ArrayList<>();
        List<String> errors = new ArrayList<>();
        List<Thread> threads = new ArrayList<>();

        for (int i = 0; i < requestCount; i++) {
            timings.add(null);
            responses.add("");
            errors.add("");
        }

        System.out.println("\nStarting " + requestCount + " client session(s) for '" + operation + "' to " + host + ":" + port + "...");

        for (int requestId = 0; requestId < requestCount; requestId++) {
            int id = requestId;
            Thread thread = new Thread(() -> runSingleClientRequest(id, host, port, operation, timings, responses, errors));
            threads.add(thread);
            thread.start();
        }

        for (Thread thread : threads) {
            try {
                thread.join();
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
        }

        System.out.println("\nPer-request turn-around time (seconds):");
        List<Double> successTimes = new ArrayList<>();
        for (int i = 0; i < timings.size(); i++) {
            Double elapsed = timings.get(i);
            if (elapsed == null) {
                System.out.println(String.format("Request %2d: FAILED (%s)", i + 1, errors.get(i)));
            } else {
                successTimes.add(elapsed);
                System.out.println(String.format("Request %2d: %.6f", i + 1, elapsed));
            }
        }

        if (!successTimes.isEmpty()) {
            double totalTime = successTimes.stream().mapToDouble(Double::doubleValue).sum();
            double averageTime = totalTime / successTimes.size();
            System.out.println(String.format("\nTotal Turn-around Time: %.6f seconds", totalTime));
            System.out.println(String.format("Average Turn-around Time: %.6f seconds", averageTime));

            System.out.println("\nSample server response from first successful request:\n");
            for (String response : responses) {
                if (response != null && !response.isEmpty()) {
                    System.out.println(response);
                    break;
                }
            }
        } else {
            System.out.println("\nNo successful requests. Check server address/port and ensure the server is running.");
        }
    }
}
