using Microsoft.AspNetCore.SignalR;
using backend_aspnet.Services;

namespace backend_aspnet.Hubs;

public class RobotHub : Hub
{
    private readonly RobotConnectionService _robotService;

    public RobotHub(RobotConnectionService robotService)
    {
        _robotService = robotService;
    }

    public async Task RobotConnect(string carId, string name, string ip, int port)
    {
        if (string.IsNullOrEmpty(carId) || string.IsNullOrEmpty(name) || string.IsNullOrEmpty(ip))
            return;

        await _robotService.RegisterRobotAsync(Context.ConnectionId, carId, name, ip, port);
        Context.Items["carId"] = carId;
        await Groups.AddToGroupAsync(Context.ConnectionId, $"robot-{carId}");

        await Clients.All.SendAsync("RobotStatusUpdate", new
        {
            carId,
            name,
            ip,
            port,
            status = "connected",
            timestamp = DateTime.UtcNow.ToString("o")
        });
    }

    public Task RobotHeartbeat(string carId, string? status, object? battery, object? position)
    {
        _robotService.UpdateHeartbeat(carId, status, battery, position);
        return Clients.All.SendAsync("RobotHeartbeat", new
        {
            carId,
            status,
            battery,
            position,
            timestamp = DateTime.UtcNow.ToString("o")
        });
    }

    public Task RobotDebug(object payload) => Clients.All.SendAsync("RobotDebug", payload);
    public Task RobotStatus(string carId, string? status, int? userId) =>
        Clients.All.SendAsync("RobotStatusUpdate", new { carId, status, userId, timestamp = DateTime.UtcNow.ToString("o") });
    public Task RobotCodeUploaded(object payload) => Clients.All.SendAsync("RobotCodeUploaded", payload);
    public Task DeployResult(object payload) => Clients.All.SendAsync("DeployResult", payload);

    public override async Task OnDisconnectedAsync(Exception? exception)
    {
        var carId = Context.Items["carId"]?.ToString();
        var disconnectedCarId = _robotService.UnregisterRobot(Context.ConnectionId) ?? carId;

        if (!string.IsNullOrEmpty(disconnectedCarId))
        {
            await Clients.All.SendAsync("RobotStatusUpdate", new
            {
                carId = disconnectedCarId,
                status = "disconnected",
                timestamp = DateTime.UtcNow.ToString("o")
            });
        }
        await base.OnDisconnectedAsync(exception);
    }
}
