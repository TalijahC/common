import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

public class Server {
    private static final String DEFAULT_HOST = "127.0.0.1";
    private static final int DEFAULT_PORT = 5000;
    private static final String END_MARKER = "\n<<END>>\n";

    private final long startTimeMillis;
    private final Long bootTimeMillis;
    private final Map<String, RequestHandler> handlers;

    private interface RequestHandler {
        String handle();
    }

    public Server() {
        this.startTimeMillis = System.currentTimeMillis();
        this.bootTimeMillis = getBootTimeMillis();
        this.handlers = new HashMap<>();
        handlers.put("DATETIME", this::getDateTime);
        handlers.put("UPTIME", this::getUptime);
        handlers.put("MEMORY", this::getMemoryUse);
        handlers.put("NETSTAT", this::getNetstat);
        handlers.put("USERS", this::getCurrentUsers);
        handlers.put("PROCESSES", this::getRunningProcesses);
        handlers.put("HELP", this::getHelp);
    }

    private static String runCommand(String... command) {
        ProcessBuilder builder = new ProcessBuilder(command);
        try {
            Process process = builder.start();
            String stdout = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8).trim();
            String stderr = new String(process.getErrorStream().readAllBytes(), StandardCharsets.UTF_8).trim();
            int exitCode = process.waitFor();
            if (exitCode != 0) {
                return stderr.isEmpty() ? "Command failed with exit code " + exitCode + "." : stderr;
            }
            return stdout.isEmpty() ? "No output." : stdout;
        } catch (Exception exc) {
            return "Error running " + String.join(" ", command) + ": " + exc.getMessage();
        }
    }

    private static Long getBootTimeMillis() {
        String system = System.getProperty("os.name").toLowerCase(Locale.ROOT);
        if (system.contains("linux")) {
            try {
                String content = Files.readString(Path.of("/proc/uptime"), StandardCharsets.UTF_8);
                String[] parts = content.split("\\s+");
                double uptimeSeconds = Double.parseDouble(parts[0]);
                return System.currentTimeMillis() - (long) (uptimeSeconds * 1000.0);
            } catch (Exception ignored) {
                return null;
            }
        }
        if (system.contains("darwin") || system.contains("mac")) {
            String output = runCommand("sysctl", "-n", "kern.boottime");
            String cleaned = output.replace("{", " ").replace("}", " ").replace(",", " ");
            for (String token : cleaned.split("\\s+")) {
                if (token.matches("\\d{9,}")) {
                    try {
                        long seconds = Long.parseLong(token);
                        return seconds * 1000L;
                    } catch (NumberFormatException ignored) {
                        return null;
                    }
                }
            }
        }
        return null;
    }

    private static String formatDuration(long millis) {
        long totalSeconds = Math.max(0, millis / 1000);
        long days = totalSeconds / 86400;
        long remainder = totalSeconds % 86400;
        long hours = remainder / 3600;
        remainder %= 3600;
        long minutes = remainder / 60;
        long seconds = remainder % 60;
        return days + "d " + hours + "h " + minutes + "m " + seconds + "s";
    }

    private static String normalizeRequest(String request) {
        String cleaned = request.trim().toUpperCase(Locale.ROOT).replace("_", " ");
        cleaned = cleaned.replaceAll("\\s+", " ");
        Map<String, String> alias = Map.ofEntries(
            Map.entry("DATE AND TIME", "DATETIME"),
            Map.entry("DATE TIME", "DATETIME"),
            Map.entry("DATETIME", "DATETIME"),
            Map.entry("UPTIME", "UPTIME"),
            Map.entry("MEMORY USE", "MEMORY"),
            Map.entry("MEMORY", "MEMORY"),
            Map.entry("NETSTAT", "NETSTAT"),
            Map.entry("CURRENT USERS", "USERS"),
            Map.entry("USERS", "USERS"),
            Map.entry("RUNNING PROCESSES", "PROCESSES"),
            Map.entry("PROCESSES", "PROCESSES"),
            Map.entry("HELP", "HELP"),
            Map.entry("QUIT", "QUIT")
        );
        return alias.getOrDefault(cleaned, cleaned);
    }

    private String getDateTime() {
        return LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
    }

    private String getUptime() {
        if (bootTimeMillis != null) {
            return "Since boot: " + formatDuration(System.currentTimeMillis() - bootTimeMillis);
        }
        return "Since server start: " + formatDuration(System.currentTimeMillis() - startTimeMillis);
    }

    private String getMemoryUse() {
        String system = System.getProperty("os.name").toLowerCase(Locale.ROOT);
        if (system.contains("linux")) {
            return runCommand("free", "-h");
        }
        if (system.contains("darwin") || system.contains("mac")) {
            String vmStat = runCommand("vm_stat");
            String topOne = runCommand("top", "-l", "1", "-n", "0");
            return "vm_stat:\n" + vmStat + "\n\ntop memory summary:\n" + topOne;
        }
        if (system.contains("windows")) {
            return runCommand("wmic", "OS", "get", "FreePhysicalMemory,TotalVisibleMemorySize", "/Value");
        }
        return "Unsupported OS for memory usage command.";
    }

    private String getNetstat() {
        String system = System.getProperty("os.name").toLowerCase(Locale.ROOT);
        if (system.contains("linux") || system.contains("darwin") || system.contains("mac")) {
            return runCommand("netstat", "-an");
        }
        if (system.contains("windows")) {
            return runCommand("netstat", "-ano");
        }
        return "Unsupported OS for netstat command.";
    }

    private String getCurrentUsers() {
        String system = System.getProperty("os.name").toLowerCase(Locale.ROOT);
        if (system.contains("linux") || system.contains("darwin") || system.contains("mac")) {
            return runCommand("who");
        }
        if (system.contains("windows")) {
            return runCommand("query", "user");
        }
        return "Unsupported OS for user listing command.";
    }

    private String getRunningProcesses() {
        String system = System.getProperty("os.name").toLowerCase(Locale.ROOT);
        if (system.contains("linux") || system.contains("darwin") || system.contains("mac")) {
            return runCommand("ps", "aux");
        }
        if (system.contains("windows")) {
            return runCommand("tasklist");
        }
        return "Unsupported OS for process listing command.";
    }

    private String getHelp() {
        return "Valid operations: Date and Time, Uptime, Memory Use, Netstat, Current Users, Running Processes";
    }

    private String processRequest(String request) {
        String command = normalizeRequest(request);
        if (command.isEmpty()) {
            return "Empty request.";
        }
        if ("QUIT".equals(command)) {
            return "BYE";
        }
        RequestHandler handler = handlers.get(command);
        if (handler == null) {
            return "Unknown request '" + request.trim() + "'. Use one of: Date and Time, Uptime, Memory Use, Netstat, Current Users, Running Processes.";
        }
        return handler.handle();
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

    private static String recvLine(Socket socket) throws IOException {
        BufferedReader reader = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
        String line = reader.readLine();
        return line == null ? null : line;
    }

    private static void sendResponse(Socket socket, String text) throws IOException {
        PrintWriter writer = new PrintWriter(new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8), true);
        writer.print(text + END_MARKER);
        writer.flush();
    }

    private static void runServer() throws IOException {
        BufferedReader console = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        String host = promptLine(console, "Server listen address [" + DEFAULT_HOST + "]: ", DEFAULT_HOST);
        int port = promptPort(console, "Server port [" + DEFAULT_PORT + "]: ", DEFAULT_PORT);

        Server app = new Server();

        try (ServerSocket serverSocket = new ServerSocket()) {
            serverSocket.bind(new InetSocketAddress(host, port));
            System.out.println("Iterative server listening on " + host + ":" + port);
            while (true) {
                try (Socket connection = serverSocket.accept()) {
                    String request = recvLine(connection);
                    if (request == null) {
                        continue;
                    }
                    String response = app.processRequest(request);
                    sendResponse(connection, response);
                    System.out.println("Handled request from " + connection.getInetAddress().getHostAddress() + ":" + connection.getPort() + " -> " + request.trim());
                }
            }
        }
    }

    public static void main(String[] args) throws IOException {
        runServer();
    }
}
