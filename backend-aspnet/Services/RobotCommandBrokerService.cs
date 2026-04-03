using System.Collections.Concurrent;
using System.Text.Json;
using Microsoft.AspNetCore.SignalR;
using backend_aspnet.Hubs;

namespace backend_aspnet.Services;

public sealed class RobotCommandBrokerService
{
    private readonly IHubContext<RobotHub> _hub;
    private readonly RobotConnectionService _robots;
    private readonly ILogger<RobotCommandBrokerService> _logger;
    private readonly ConcurrentDictionary<string, TaskCompletionSource<RobotCommandResult>> _pending = new();

    public RobotCommandBrokerService(
        IHubContext<RobotHub> hub,
        RobotConnectionService robots,
        ILogger<RobotCommandBrokerService> logger)
    {
        _hub = hub;
        _robots = robots;
        _logger = logger;
    }

    public async Task<RobotCommandResult> SendCommandAsync(
        string carId,
        string command,
        object? payload,
        TimeSpan timeout,
        CancellationToken cancellationToken = default)
    {
        var robot = _robots.GetRobot(carId);
        if (robot == null || string.IsNullOrWhiteSpace(robot.ConnectionId))
        {
            return RobotCommandResult.Offline(carId, command, "Robot is offline or not connected to hub");
        }

        var correlationId = Guid.NewGuid().ToString("N");
        var request = new RobotCommandRequest
        {
            CorrelationId = correlationId,
            CarId = carId,
            Command = command,
            Payload = payload,
            RequestedAt = DateTime.UtcNow.ToString("o")
        };

        var tcs = new TaskCompletionSource<RobotCommandResult>(TaskCreationOptions.RunContinuationsAsynchronously);
        if (!_pending.TryAdd(correlationId, tcs))
            return RobotCommandResult.Fail(carId, command, "Failed to enqueue robot command");

        try
        {
            _logger.LogInformation("Sending robot command {Command} to {CarId} ({CorrelationId})", command, carId, correlationId);
            await _hub.Clients.Group($"robot-{carId}").SendAsync("RobotCommandRequest", request, cancellationToken);

            using var cts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            cts.CancelAfter(timeout);
            await using var reg = cts.Token.Register(() => tcs.TrySetCanceled());
            var result = await tcs.Task;
            return result;
        }
        catch (TaskCanceledException)
        {
            _logger.LogWarning("Robot command timeout {Command} to {CarId} ({CorrelationId})", command, carId, correlationId);
            return RobotCommandResult.Timeout(carId, command, $"Timed out waiting for robot response ({timeout.TotalSeconds:0}s)");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Robot command failed {Command} to {CarId} ({CorrelationId})", command, carId, correlationId);
            return RobotCommandResult.Fail(carId, command, $"Broker send failed: {ex.Message}");
        }
        finally
        {
            _pending.TryRemove(correlationId, out _);
        }
    }

    public void CompleteResult(RobotCommandResult result)
    {
        if (string.IsNullOrWhiteSpace(result.CorrelationId)) return;
        if (_pending.TryGetValue(result.CorrelationId, out var tcs))
            tcs.TrySetResult(result);
    }
}

public sealed class RobotCommandRequest
{
    public string CorrelationId { get; set; } = "";
    public string CarId { get; set; } = "";
    public string Command { get; set; } = "";
    public object? Payload { get; set; }
    public string RequestedAt { get; set; } = "";
}

public sealed class RobotCommandResult
{
    public string CorrelationId { get; set; } = "";
    public string CarId { get; set; } = "";
    public string Command { get; set; } = "";
    public bool Success { get; set; }
    public int StatusCode { get; set; } = 200;
    public string? Error { get; set; }
    public JsonElement? Payload { get; set; }
    public string RespondedAt { get; set; } = DateTime.UtcNow.ToString("o");

    public static RobotCommandResult Offline(string carId, string command, string error) =>
        new() { CarId = carId, Command = command, Success = false, StatusCode = 503, Error = error };

    public static RobotCommandResult Timeout(string carId, string command, string error) =>
        new() { CarId = carId, Command = command, Success = false, StatusCode = 504, Error = error };

    public static RobotCommandResult Fail(string carId, string command, string error) =>
        new() { CarId = carId, Command = command, Success = false, StatusCode = 500, Error = error };
}
