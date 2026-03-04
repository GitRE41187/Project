using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using backend_aspnet.Services;

namespace backend_aspnet.Controllers;

[ApiController]
[Route("api/[controller]")]
public class RobotsController : ControllerBase
{
    private readonly RobotConnectionService _robotService;

    public RobotsController(RobotConnectionService robotService)
    {
        _robotService = robotService;
    }

    private int? GetUserId()
    {
        var userId = User.FindFirst("userId")?.Value ?? User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        return !string.IsNullOrEmpty(userId) && int.TryParse(userId, out var uid) ? uid : null;
    }

    [HttpGet("available")]
    [Authorize]
    public IActionResult Available()
    {
        var cars = _robotService.GetAvailableRobots();
        return Ok(new
        {
            availableCars = cars.Select(c => new
            {
                id = c.CarId,
                name = c.Name,
                ip = c.Ip,
                port = c.Port,
                lastSeen = c.LastSeen,
                status = c.Status,
                isConnected = !string.IsNullOrEmpty(c.ConnectionId),
                connectionType = "websocket",
                battery = c.Battery
            }),
            total = cars.Count,
            connectedRobots = cars.Count
        });
    }

    [HttpPost("select")]
    [Authorize]
    public async Task<IActionResult> Select([FromBody] SelectRequest req)
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();
        if (string.IsNullOrEmpty(req.CarId))
            return BadRequest(new { error = "carId is required" });

        var ok = await _robotService.SelectRobotAsync(userId.Value, req.CarId);
        if (!ok)
        {
            var robot = _robotService.GetRobot(req.CarId);
            if (robot == null) return NotFound(new { error = "Robot not found" });
            if (robot.Status != "available") return StatusCode(409, new { error = "Robot car not available" });
            return StatusCode(403, new { error = "No active booking" });
        }

        var selected = _robotService.GetRobot(req.CarId)!;
        return Ok(new
        {
            message = "Robot car selected successfully",
            selectedCar = new { id = selected.CarId, name = selected.Name, ip = selected.Ip, port = selected.Port }
        });
    }

    [HttpPost("release")]
    [Authorize]
    public async Task<IActionResult> Release([FromBody] ReleaseRequest req)
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();
        if (string.IsNullOrEmpty(req.CarId))
            return BadRequest(new { error = "carId is required" });

        var ok = await _robotService.ReleaseRobotAsync(userId.Value, req.CarId);
        if (!ok)
        {
            var robot = _robotService.GetRobot(req.CarId);
            if (robot == null) return NotFound(new { error = "Robot not found" });
            return StatusCode(403, new { error = "Not your robot" });
        }
        return Ok(new { message = "Robot car released successfully" });
    }

    [HttpGet("my-car")]
    [Authorize]
    public IActionResult MyCar()
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();

        var car = _robotService.GetUserCar(userId.Value);
        if (car == null)
            return Ok(new { hasSelectedCar = false });
        return Ok(new
        {
            hasSelectedCar = true,
            selectedCar = new { id = car.CarId, name = car.Name, ip = car.Ip, port = car.Port }
        });
    }
}

public class SelectRequest { public string? CarId { get; set; } }
public class ReleaseRequest { public string? CarId { get; set; } }
