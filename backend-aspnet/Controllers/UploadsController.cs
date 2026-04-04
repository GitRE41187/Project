using System.Security.Claims;
using System.Text.Json;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Npgsql;
using backend_aspnet.Services;
using Microsoft.AspNetCore.Http;

namespace backend_aspnet.Controllers;

[ApiController]
[Route("api/[controller]")]
public class UploadsController : ControllerBase
{
    private readonly DatabaseService _db;
    private readonly AppTimeService _clock;
    private readonly IConfiguration _config;
    private readonly RobotConnectionService _robotService;
    private readonly RobotCommandBrokerService _broker;
    private readonly ILogger<UploadsController> _logger;

    public UploadsController(DatabaseService db, AppTimeService clock, IConfiguration config, RobotConnectionService robotService, RobotCommandBrokerService broker, ILogger<UploadsController> logger)
    {
        _db = db;
        _clock = clock;
        _config = config;
        _robotService = robotService;
        _broker = broker;
        _logger = logger;
    }

    private static bool IsRequestTimeout(Exception ex)
    {
        if (ex is TaskCanceledException) return true;
        if (ex.InnerException is TimeoutException) return true;
        if (ex.InnerException is TaskCanceledException) return true;
        return false;
    }

    private static object ParseResultPayload(JsonElement? payload)
    {
        if (payload == null) return new { };
        try
        {
            return JsonSerializer.Deserialize<object>(payload.Value.GetRawText()) ?? new { };
        }
        catch
        {
            return new { };
        }
    }

    private Task<RobotCommandResult> ExecuteRobotCommandAsync(RobotCar car, string command, object? payload, TimeSpan timeout) =>
        _broker.SendCommandAsync(car.CarId, command, payload, timeout);

    private int? GetUserId()
    {
        var userId = User.FindFirst("userId")?.Value ?? User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        return !string.IsNullOrEmpty(userId) && int.TryParse(userId, out var uid) ? uid : null;
    }

    private async Task<(int bookingId, DateTime start, DateTime end, string status)?> GetActiveBooking(int userId)
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

    private async Task<IActionResult?> RequireBookingAndSelectedCarAsync(int userId)
    {
        var booking = await GetActiveBooking(userId);
        if (booking == null)
            return StatusCode(403, new { error = "No active booking. Please book a slot and check in." });

        if (await _robotService.GetUserCarAsync(userId) == null)
            return StatusCode(403, new { error = "No robot car selected. Please select a robot car first." });

        return null;
    }

    [HttpPost("upload")]
    [Authorize]
    [Consumes("multipart/form-data")]
    [RequestSizeLimit(10_485_760)]
    [RequestFormLimits(MultipartBodyLengthLimit = 10_485_760)]
    public async Task<IActionResult> Upload([FromForm] IFormFile? codeFile)
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();
        _logger.LogInformation("Upload request received from user {UserId}", userId.Value);
        if (codeFile == null || codeFile.Length == 0)
            return BadRequest(new { error = "No file uploaded" });

        var ext = Path.GetExtension(codeFile.FileName).ToLowerInvariant();
        if (ext != ".py")
            return BadRequest(new { error = "Only Python files (.py) are allowed" });

        var maxSize = _config.GetValue<long>("MaxFileSize", 10 * 1024 * 1024);
        if (codeFile.Length > maxSize)
            return BadRequest(new { error = "File too large" });

        var blocked = await RequireBookingAndSelectedCarAsync(userId.Value);
        if (blocked != null) return blocked;

        var car = (await _robotService.GetUserCarAsync(userId.Value))!;

        await using var ms = new MemoryStream();
        await codeFile.CopyToAsync(ms);
        var b64 = Convert.ToBase64String(ms.ToArray());

        try
        {
            var piBody = new Dictionary<string, object?>
            {
                ["user_id"] = userId.Value,
                ["content_base64"] = b64,
                ["original_filename"] = codeFile.FileName
            };
            var result = await ExecuteRobotCommandAsync(car, "upload_code", piBody, TimeSpan.FromMinutes(2));
            if (!result.Success)
            {
                _logger.LogWarning("Upload to robot failed. user={UserId}, car={CarId}, status={StatusCode}, error={Error}", userId.Value, car.CarId, result.StatusCode, result.Error);
                return StatusCode(result.StatusCode, new { error = result.Error ?? "Upload to robot failed" });
            }

            _logger.LogInformation("Upload to robot success. user={UserId}, car={CarId}, filename={Filename}", userId.Value, car.CarId, codeFile.FileName);
            var piResponse = ParseResultPayload(result.Payload);
            return Ok(new { message = "File uploaded to robot successfully", robotCar = car.Name, piResponse });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Upload to robot exception. user={UserId}, car={CarId}", userId.Value, car.CarId);
            return StatusCode(500, new { error = $"Failed to reach robot car: {ex.Message}" });
        }
    }

    [HttpGet("my-uploads")]
    [Authorize]
    public async Task<IActionResult> MyUploads()
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();
        _logger.LogInformation("MyUploads request received from user {UserId}", userId.Value);

        var blocked = await RequireBookingAndSelectedCarAsync(userId.Value);
        if (blocked != null) return blocked;

        var car = (await _robotService.GetUserCarAsync(userId.Value))!;

        try
        {
            var result = await ExecuteRobotCommandAsync(car, "list_files", new { user_id = userId.Value }, TimeSpan.FromSeconds(30));
            if (!result.Success)
            {
                _logger.LogWarning("List robot files failed. user={UserId}, car={CarId}, status={StatusCode}, error={Error}", userId.Value, car.CarId, result.StatusCode, result.Error);
                return StatusCode(result.StatusCode, new { error = result.Error ?? "List files failed" });
            }

            var root = result.Payload ?? JsonSerializer.SerializeToElement(new { });
            var filesList = new List<object>();
            if (root.ValueKind == JsonValueKind.Object && root.TryGetProperty("files", out var f) && f.ValueKind == JsonValueKind.Array)
            {
                foreach (var item in f.EnumerateArray())
                {
                    var o = JsonSerializer.Deserialize<object>(item.GetRawText());
                    if (o != null) filesList.Add(o);
                }
            }

            return Ok(new { files = filesList, robotCar = car.Name });
        }
        catch (Exception ex)
        {
            if (IsRequestTimeout(ex))
            {
                _logger.LogWarning(ex, "List robot files timeout. user={UserId}, car={CarId}", userId.Value, car.CarId);
                return StatusCode(504, new
                {
                    error = "Robot did not respond in time while listing files",
                    detail = "Please try again. If this repeats, confirm the robot is connected to the hub over SignalR."
                });
            }
            _logger.LogError(ex, "List robot files exception. user={UserId}, car={CarId}", userId.Value, car.CarId);
            return StatusCode(500, new { error = $"Failed to list files from robot: {ex.Message}" });
        }
    }

    [HttpDelete("file")]
    [Authorize]
    public async Task<IActionResult> DeleteRobotFile([FromQuery] string? filename)
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();
        _logger.LogInformation("Delete robot file request received from user {UserId}, filename={Filename}", userId.Value, filename);
        if (string.IsNullOrWhiteSpace(filename))
            return BadRequest(new { error = "filename query parameter is required" });

        var blocked = await RequireBookingAndSelectedCarAsync(userId.Value);
        if (blocked != null) return blocked;

        var car = (await _robotService.GetUserCarAsync(userId.Value))!;

        try
        {
            var result = await ExecuteRobotCommandAsync(car, "delete_file", new { user_id = userId.Value, filename }, TimeSpan.FromSeconds(30));
            if (!result.Success)
            {
                _logger.LogWarning("Delete robot file failed. user={UserId}, car={CarId}, file={Filename}, status={StatusCode}, error={Error}", userId.Value, car.CarId, filename, result.StatusCode, result.Error);
                return StatusCode(result.StatusCode, new { error = result.Error ?? "Delete failed" });
            }

            _logger.LogInformation("Delete robot file success. user={UserId}, car={CarId}, file={Filename}", userId.Value, car.CarId, filename);
            var piResponse = ParseResultPayload(result.Payload);
            return Ok(new { message = "File deleted on robot", robotCar = car.Name, piResponse });
        }
        catch (Exception ex)
        {
            if (IsRequestTimeout(ex))
            {
                _logger.LogWarning(ex, "Delete robot file timeout. user={UserId}, car={CarId}, file={Filename}", userId.Value, car.CarId, filename);
                return StatusCode(504, new
                {
                    error = "Robot did not respond in time while deleting file",
                    detail = "Please try again. If this repeats, confirm the robot is connected to the hub over SignalR."
                });
            }
            _logger.LogError(ex, "Delete robot file exception. user={UserId}, car={CarId}, file={Filename}", userId.Value, car.CarId, filename);
            return StatusCode(500, new { error = $"Failed to reach robot: {ex.Message}" });
        }
    }
}
