using Microsoft.AspNetCore.SignalR;
using Npgsql;
using backend_aspnet.Hubs;

namespace backend_aspnet.Services;

public class RobotConnectionService
{
    private readonly Dictionary<string, RobotCar> _robots = new();
    private readonly Dictionary<string, string> _connectionToCar = new();
    private readonly IConfiguration _config;
    private readonly AppTimeService _clock;
    private readonly ILogger<RobotConnectionService> _logger;
    private readonly IHubContext<RobotHub> _hubContext;

    public RobotConnectionService(IConfiguration config, AppTimeService clock, ILogger<RobotConnectionService> logger, IHubContext<RobotHub> hubContext)
    {
        _config = config;
        _clock = clock;
        _logger = logger;
        _hubContext = hubContext;
    }

    public async Task RegisterRobotAsync(string connectionId, string carId, string name, string ip, int port)
    {
        var existing = _robots.Values.FirstOrDefault(r => r.CarId == carId);
        if (existing != null && existing.ConnectionId != connectionId)
        {
            _connectionToCar.Remove(existing.ConnectionId);
            existing.ConnectionId = null;
        }

        var robot = _robots.Values.FirstOrDefault(r => r.CarId == carId) ?? new RobotCar
        {
            CarId = carId,
            Name = name,
            Ip = ip,
            Port = port
        };
        robot.ConnectionId = connectionId;
        robot.Name = name;
        robot.Ip = ip;
        robot.Port = port;
        robot.Status = "available";
        robot.LastSeen = DateTime.UtcNow;
        robot.UserId = null;

        _robots[carId] = robot;
        _connectionToCar[connectionId] = carId;

        try
        {
            await using var conn = await new DatabaseService(_config).GetConnectionAsync();
            var cmd = new NpgsqlCommand(
                @"INSERT INTO ROBOT_CARS (car_id, name, ip, port, status, last_seen) VALUES (@c,@n,@i,@p,'available',@t)
                  ON CONFLICT (car_id) DO UPDATE SET
                    name = EXCLUDED.name, ip = EXCLUDED.ip, port = EXCLUDED.port,
                    status = EXCLUDED.status, last_seen = EXCLUDED.last_seen",
                conn);
            cmd.Parameters.AddWithValue("@c", carId);
            cmd.Parameters.AddWithValue("@n", name);
            cmd.Parameters.AddWithValue("@i", ip);
            cmd.Parameters.AddWithValue("@p", port);
            cmd.Parameters.AddWithValue("@t", DateTime.UtcNow);
            await cmd.ExecuteNonQueryAsync();
        }
        catch (Exception ex) { _logger.LogWarning(ex, "DB sync error"); }
    }

    public string? UnregisterRobot(string connectionId)
    {
        if (!_connectionToCar.TryGetValue(connectionId, out var carId))
            return null;
        _connectionToCar.Remove(connectionId);
        if (_robots.TryGetValue(carId, out var robot))
        {
            robot.ConnectionId = null;
            robot.Status = "offline";
            robot.LastSeen = DateTime.UtcNow;
        }
        return carId;
    }

    public void UpdateHeartbeat(string carId, string? status, object? battery, object? position)
    {
        if (_robots.TryGetValue(carId, out var robot))
        {
            robot.LastSeen = DateTime.UtcNow;
            if (!string.IsNullOrEmpty(status)) robot.Status = status;
            robot.Battery = battery;
            robot.Position = position;
        }
    }

    public List<RobotCar> GetAvailableRobots()
    {
        var available = new HashSet<string> { "available", "idle" };
        return _robots.Values
            .Where(r => available.Contains(r.Status) && !string.IsNullOrEmpty(r.ConnectionId))
            .ToList();
    }

    public RobotCar? GetRobot(string carId) => _robots.TryGetValue(carId, out var r) ? r : null;

    public RobotCar? GetUserCar(int userId) =>
        _robots.Values.FirstOrDefault(r => r.UserId == userId && r.Status == "in_use");

    public async Task<bool> SelectRobotAsync(int userId, string carId)
    {
        var robot = GetRobot(carId);
        if (robot == null || robot.Status != "available") return false;

        await using var conn = await new DatabaseService(_config).GetConnectionAsync();
        var now = _clock.NowInRegionDb();
        var activate = new NpgsqlCommand(
            "UPDATE BOOKINGS SET status='active' WHERE user_id=@uid AND status='pending' AND start_time<=@now AND end_time>@now",
            conn);
        activate.Parameters.AddWithValue("@uid", userId);
        activate.Parameters.AddWithValue("@now", now);
        await activate.ExecuteNonQueryAsync();

        var cmd = new NpgsqlCommand(
            "SELECT id FROM BOOKINGS WHERE user_id=@uid AND status='active' AND start_time<=@now AND end_time>@now",
            conn);
        cmd.Parameters.AddWithValue("@uid", userId);
        cmd.Parameters.AddWithValue("@now", now);
        await using var r = await cmd.ExecuteReaderAsync();
        if (!await r.ReadAsync()) return false;
        await r.CloseAsync();

        robot.Status = "in_use";
        robot.UserId = userId;

        var update = new NpgsqlCommand("UPDATE ROBOT_CARS SET status='in_use', current_user_id=@uid WHERE car_id=@c", conn);
        update.Parameters.AddWithValue("@uid", userId);
        update.Parameters.AddWithValue("@c", carId);
        await update.ExecuteNonQueryAsync();
        return true;
    }

    public async Task<bool> ReleaseRobotAsync(int userId, string carId)
    {
        var robot = GetRobot(carId);
        if (robot == null || robot.UserId != userId) return false;

        robot.Status = "available";
        robot.UserId = null;

        await using var conn = await new DatabaseService(_config).GetConnectionAsync();
        var cmd = new NpgsqlCommand("UPDATE ROBOT_CARS SET status='available', current_user_id=NULL WHERE car_id=@c", conn);
        cmd.Parameters.AddWithValue("@c", carId);
        await cmd.ExecuteNonQueryAsync();
        return true;
    }

    public async Task<bool> DeployToUserRobotAsync(int userId, string codeText, string? filename)
    {
        var robot = GetUserCar(userId);
        if (robot == null || string.IsNullOrEmpty(robot.ConnectionId)) return false;

        await _hubContext.Clients.Group($"robot-{robot.CarId}")
            .SendAsync("DeployCode", userId, codeText, filename ?? $"user_{userId}.py");
        return true;
    }
}

public class RobotCar
{
    public string CarId { get; set; } = "";
    public string Name { get; set; } = "";
    public string Ip { get; set; } = "";
    public int Port { get; set; }
    public string Status { get; set; } = "available";
    public DateTime LastSeen { get; set; }
    public int? UserId { get; set; }
    public string? ConnectionId { get; set; }
    public object? Battery { get; set; }
    public object? Position { get; set; }
}
