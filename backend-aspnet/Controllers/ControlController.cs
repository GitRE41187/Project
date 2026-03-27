using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Npgsql;
using backend_aspnet.Services;

namespace backend_aspnet.Controllers;

[ApiController]
[Route("api/[controller]")]
public class ControlController : ControllerBase
{
    private readonly DatabaseService _db;
    private readonly AppTimeService _clock;
    private readonly RobotConnectionService _robotService;
    private readonly IHttpClientFactory _http;

    public ControlController(DatabaseService db, AppTimeService clock, RobotConnectionService robotService, IHttpClientFactory http)
    {
        _db = db;
        _clock = clock;
        _robotService = robotService;
        _http = http;
    }

    private int? GetUserId()
    {
        var userId = User.FindFirst("userId")?.Value ?? User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        return !string.IsNullOrEmpty(userId) && int.TryParse(userId, out var uid) ? uid : null;
    }

    private async Task<(int? bookingId, DateTime? start, DateTime? end, string? status)?> GetActiveBooking(int userId)
    {
        await using var conn = await _db.GetConnectionAsync();
        var now = _clock.NowInRegionDb();
        var update = new NpgsqlCommand(@"UPDATE BOOKINGS SET status = 'active'
            WHERE user_id = @uid AND status = 'pending' AND start_time <= @now AND end_time > @now", conn);
        update.Parameters.AddWithValue("@uid", userId);
        update.Parameters.AddWithValue("@now", now);
        await update.ExecuteNonQueryAsync();

        var cmd = new NpgsqlCommand(@"SELECT id, start_time, end_time, status FROM BOOKINGS
            WHERE user_id = @uid AND status = 'active' AND start_time <= @now AND end_time > @now", conn);
        cmd.Parameters.AddWithValue("@uid", userId);
        cmd.Parameters.AddWithValue("@now", now);
        await using var r = await cmd.ExecuteReaderAsync();
        if (!await r.ReadAsync()) return null;
        return (r.GetInt32(0), r.GetDateTime(1), r.GetDateTime(2), r.GetString(3));
    }

    private RobotCar? GetSelectedCar(int userId) => _robotService.GetUserCar(userId);

    [HttpPost("upload")]
    [Authorize]
    public async Task<IActionResult> Upload([FromBody] ControlUploadRequest req)
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();
        if (string.IsNullOrEmpty(req.FilePath))
            return BadRequest(new { error = "File path is required" });

        var booking = await GetActiveBooking(userId.Value);
        if (booking == null)
            return StatusCode(403, new { error = "No active booking found" });

        var car = GetSelectedCar(userId.Value);
        if (car == null)
            return StatusCode(403, new { error = "No robot car selected. Please select a robot car first." });

        try
        {
            var client = _http.CreateClient();
            var resp = await client.PostAsJsonAsync($"http://{car.Ip}:{car.Port}/upload_code", new
            {
                user_id = userId,
                file_path = req.FilePath,
                original_filename = req.OriginalFilename ?? "code.py"
            });

            await using var conn = await _db.GetConnectionAsync();
            var log = new NpgsqlCommand("INSERT INTO EXECUTION_LOGS (user_id, booking_id, action, details) VALUES (@uid, @bid, 'upload', @d)", conn);
            log.Parameters.AddWithValue("@uid", userId);
            log.Parameters.AddWithValue("@bid", booking.Value.bookingId);
            log.Parameters.AddWithValue("@d", $"Code uploaded to {car.Name}: {req.OriginalFilename}");
            await log.ExecuteNonQueryAsync();

            return Ok(new { message = "Code uploaded successfully", robotCar = car.Name, piResponse = await resp.Content.ReadFromJsonAsync<object>() });
        }
        catch (Exception)
        {
            return StatusCode(500, new { error = $"Failed to upload code to robot car {car.Name}" });
        }
    }

    [HttpPost("deploy")]
    [Authorize]
    public async Task<IActionResult> Deploy([FromBody] DeployRequest req)
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();
        if (string.IsNullOrEmpty(req.CodeText))
            return BadRequest(new { error = "codeText is required" });

        var booking = await GetActiveBooking(userId.Value);
        if (booking == null)
            return StatusCode(403, new { error = "No active booking found" });

        var car = GetSelectedCar(userId.Value);
        if (car == null || string.IsNullOrEmpty(car.ConnectionId))
            return StatusCode(403, new { error = "No connected robot car selected." });

        var ok = await _robotService.DeployToUserRobotAsync(userId.Value, req.CodeText, req.Filename);
        if (!ok)
            return StatusCode(500, new { error = "Failed to deploy" });

        await using var conn = await _db.GetConnectionAsync();
        var log = new NpgsqlCommand("INSERT INTO EXECUTION_LOGS (user_id, booking_id, action, details) VALUES (@uid, @bid, 'upload', @d)", conn);
        log.Parameters.AddWithValue("@uid", userId);
        log.Parameters.AddWithValue("@bid", booking.Value.bookingId);
        log.Parameters.AddWithValue("@d", $"Deploy requested to {car.Name} ({car.CarId})");
        await log.ExecuteNonQueryAsync();

        return Ok(new { message = "Deploy sent to robot. Await deploy-result via websocket.", carId = car.CarId });
    }

    [HttpPost("run")]
    [Authorize]
    public async Task<IActionResult> Run()
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();
        var booking = await GetActiveBooking(userId.Value);
        if (booking == null) return StatusCode(403, new { error = "No active booking found" });
        var car = GetSelectedCar(userId.Value);
        if (car == null) return StatusCode(403, new { error = "No robot car selected. Please select a robot car first." });

        try
        {
            var client = _http.CreateClient();
            var resp = await client.PostAsJsonAsync($"http://{car.Ip}:{car.Port}/run", new { user_id = userId });
            await LogAsync(userId.Value, booking.Value.bookingId!.Value, "run", $"Code execution started on {car.Name}");
            return Ok(new { message = "Code execution started", robotCar = car.Name, piResponse = await resp.Content.ReadFromJsonAsync<object>() });
        }
        catch { return StatusCode(500, new { error = $"Failed to run code on robot car {car.Name}" }); }
    }

    [HttpPost("stop")]
    [Authorize]
    public async Task<IActionResult> Stop()
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();
        var booking = await GetActiveBooking(userId.Value);
        if (booking == null) return StatusCode(403, new { error = "No active booking found" });
        var car = GetSelectedCar(userId.Value);
        if (car == null) return StatusCode(403, new { error = "No robot car selected. Please select a robot car first." });

        try
        {
            var client = _http.CreateClient();
            var resp = await client.PostAsJsonAsync($"http://{car.Ip}:{car.Port}/stop", new { user_id = userId });
            await LogAsync(userId.Value, booking.Value.bookingId!.Value, "stop", $"Code execution stopped on {car.Name}");
            return Ok(new { message = "Code execution stopped", robotCar = car.Name, piResponse = await resp.Content.ReadFromJsonAsync<object>() });
        }
        catch { return StatusCode(500, new { error = $"Failed to stop code on robot car {car.Name}" }); }
    }

    [HttpPost("reset")]
    [Authorize]
    public async Task<IActionResult> Reset()
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();
        var booking = await GetActiveBooking(userId.Value);
        if (booking == null) return StatusCode(403, new { error = "No active booking found" });
        var car = GetSelectedCar(userId.Value);
        if (car == null) return StatusCode(403, new { error = "No robot car selected. Please select a robot car first." });

        try
        {
            var client = _http.CreateClient();
            var resp = await client.PostAsJsonAsync($"http://{car.Ip}:{car.Port}/reset", new { user_id = userId });
            await LogAsync(userId.Value, booking.Value.bookingId!.Value, "reset", $"Field reset to start position on {car.Name}");
            return Ok(new { message = "Field reset successfully", robotCar = car.Name, piResponse = await resp.Content.ReadFromJsonAsync<object>() });
        }
        catch { return StatusCode(500, new { error = $"Failed to reset field on robot car {car.Name}" }); }
    }

    [HttpGet("status")]
    [Authorize]
    public async Task<IActionResult> Status()
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();
        var booking = await GetActiveBooking(userId.Value);
        if (booking == null)
            return Ok(new { hasActiveBooking = false });

        var car = GetSelectedCar(userId.Value);
        if (car == null)
            return Ok(new { hasActiveBooking = true, booking = new { id = booking.Value.bookingId, start_time = booking.Value.start, end_time = booking.Value.end, status = booking.Value.status }, hasSelectedCar = false, executionStatus = new { error = "No robot car selected" } });

        try
        {
            var client = _http.CreateClient();
            var resp = await client.GetFromJsonAsync<object>($"http://{car.Ip}:{car.Port}/status/{userId}");
            return Ok(new
            {
                hasActiveBooking = true,
                booking = new { id = booking.Value.bookingId, start_time = booking.Value.start, end_time = booking.Value.end, status = booking.Value.status },
                hasSelectedCar = true,
                selectedCar = new { id = car.CarId, name = car.Name },
                executionStatus = resp
            });
        }
        catch
        {
            return Ok(new
            {
                hasActiveBooking = true,
                booking = new { id = booking.Value.bookingId, start_time = booking.Value.start, end_time = booking.Value.end, status = booking.Value.status },
                hasSelectedCar = true,
                selectedCar = new { id = car.CarId, name = car.Name },
                executionStatus = new { error = $"Unable to get execution status from {car.Name}" }
            });
        }
    }

    [HttpPost("camera/start")]
    [Authorize]
    public async Task<IActionResult> CameraStart()
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();
        var booking = await GetActiveBooking(userId.Value);
        if (booking == null) return StatusCode(403, new { error = "No active booking found" });
        var car = GetSelectedCar(userId.Value);
        if (car == null) return StatusCode(403, new { error = "No robot car selected. Please select a robot car first." });

        try
        {
            var client = _http.CreateClient();
            var resp = await client.PostAsJsonAsync($"http://{car.Ip}:{car.Port}/camera/start", new { user_id = userId });
            await LogAsync(userId.Value, booking.Value.bookingId!.Value, "camera_start", $"Camera streaming started on {car.Name}");
            return Ok(new { message = "Camera started successfully", robotCar = car.Name, cameraStreamUrl = $"http://{car.Ip}:{car.Port}/camera/stream", piResponse = await resp.Content.ReadFromJsonAsync<object>() });
        }
        catch { return StatusCode(500, new { error = $"Failed to start camera on robot car {car.Name}" }); }
    }

    [HttpPost("camera/stop")]
    [Authorize]
    public async Task<IActionResult> CameraStop()
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();
        var booking = await GetActiveBooking(userId.Value);
        if (booking == null) return StatusCode(403, new { error = "No active booking found" });
        var car = GetSelectedCar(userId.Value);
        if (car == null) return StatusCode(403, new { error = "No robot car selected. Please select a robot car first." });

        try
        {
            var client = _http.CreateClient();
            var resp = await client.PostAsJsonAsync($"http://{car.Ip}:{car.Port}/camera/stop", new { user_id = userId });
            await LogAsync(userId.Value, booking.Value.bookingId!.Value, "camera_stop", $"Camera streaming stopped on {car.Name}");
            return Ok(new { message = "Camera stopped successfully", robotCar = car.Name, piResponse = await resp.Content.ReadFromJsonAsync<object>() });
        }
        catch { return StatusCode(500, new { error = $"Failed to stop camera on robot car {car.Name}" }); }
    }

    [HttpGet("camera/status")]
    [Authorize]
    public async Task<IActionResult> CameraStatus()
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();
        var booking = await GetActiveBooking(userId.Value);
        if (booking == null)
            return Ok(new { hasActiveBooking = false });

        var car = GetSelectedCar(userId.Value);
        if (car == null)
            return Ok(new { hasActiveBooking = true, booking = new { id = booking.Value.bookingId }, hasSelectedCar = false, cameraStatus = new { error = "No robot car selected" } });

        try
        {
            var client = _http.CreateClient();
            var resp = await client.GetFromJsonAsync<Dictionary<string, object>>($"http://{car.Ip}:{car.Port}/camera/status");
            var cameraActive = resp != null && resp.ContainsKey("camera_active") && Convert.ToBoolean(resp["camera_active"]);
            return Ok(new
            {
                hasActiveBooking = true,
                booking = new { id = booking.Value.bookingId },
                hasSelectedCar = true,
                selectedCar = new { id = car.CarId, name = car.Name },
                cameraStatus = (object)(resp ?? new Dictionary<string, object>()),
                cameraStreamUrl = cameraActive ? $"http://{car.Ip}:{car.Port}/camera/stream" : null
            });
        }
        catch
        {
            return Ok(new
            {
                hasActiveBooking = true,
                hasSelectedCar = true,
                selectedCar = new { id = car.CarId, name = car.Name },
                cameraStatus = new { error = $"Unable to get camera status from {car.Name}" }
            });
        }
    }

    [HttpPost("checkin")]
    [Authorize]
    public async Task<IActionResult> Checkin()
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();

        await using var conn = await _db.GetConnectionAsync();
        var now = _clock.NowInRegionDb();
        var cmd = new NpgsqlCommand(@"SELECT id, start_time, end_time, status FROM BOOKINGS
            WHERE user_id = @uid AND status = 'pending' AND start_time <= @now AND end_time > @now
            ORDER BY start_time DESC LIMIT 1", conn);
        cmd.Parameters.AddWithValue("@uid", userId);
        cmd.Parameters.AddWithValue("@now", now);
        await using var r = await cmd.ExecuteReaderAsync();
        if (!await r.ReadAsync())
            return NotFound(new { error = "No pending booking found for current time slot" });

        var bid = r.GetInt32(0);
        var start = r.GetDateTime(1);
        var end = r.GetDateTime(2);
        await r.CloseAsync();

        var update = new NpgsqlCommand("UPDATE BOOKINGS SET status = 'active' WHERE id = @id", conn);
        update.Parameters.AddWithValue("@id", bid);
        await update.ExecuteNonQueryAsync();

        await LogAsync(userId.Value, bid, "upload", $"Manual check-in at {DateTime.UtcNow:O}");

        return Ok(new
        {
            message = "Successfully checked in",
            booking = new { id = bid, start_time = start, end_time = end, status = "active" }
        });
    }

    [HttpPost("move/{direction}")]
    [Authorize]
    public async Task<IActionResult> Move(string direction)
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();
        var booking = await GetActiveBooking(userId.Value);
        if (booking == null) return StatusCode(403, new { error = "No active booking found" });
        var car = GetSelectedCar(userId.Value);
        if (car == null) return StatusCode(403, new { error = "No robot car selected. Please select a robot car first." });

        var directions = new[] { "front", "back", "left", "right" };
        if (!directions.Contains(direction))
            return BadRequest(new { error = "Invalid direction" });

        try
        {
            var client = _http.CreateClient();
            var resp = await client.PostAsJsonAsync($"http://{car.Ip}:{car.Port}/control/{direction}", new { duration = 0.5 });
            await LogAsync(userId.Value, booking.Value.bookingId!.Value, "upload", $"Move {direction} on {car.Name}");
            return Ok(new { message = $"Move {direction} sent", piResponse = await resp.Content.ReadFromJsonAsync<object>() });
        }
        catch { return StatusCode(500, new { error = $"Failed to move {direction}" }); }
    }

    private async Task LogAsync(int userId, int bookingId, string action, string details)
    {
        await using var conn = await _db.GetConnectionAsync();
        var cmd = new NpgsqlCommand("INSERT INTO EXECUTION_LOGS (user_id, booking_id, action, details) VALUES (@uid, @bid, @act, @d)", conn);
        cmd.Parameters.AddWithValue("@uid", userId);
        cmd.Parameters.AddWithValue("@bid", bookingId);
        cmd.Parameters.AddWithValue("@act", action);
        cmd.Parameters.AddWithValue("@d", details);
        await cmd.ExecuteNonQueryAsync();
    }
}

public class ControlUploadRequest
{
    public string? FilePath { get; set; }
    public string? OriginalFilename { get; set; }
}

public class DeployRequest
{
    public string? CodeText { get; set; }
    public string? Filename { get; set; }
}
