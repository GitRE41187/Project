using System.Net.Http.Json;
using System.Security.Claims;
using System.Text.Json;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Npgsql;
using backend_aspnet.Services;

namespace backend_aspnet.Controllers;

[ApiController]
[Route("api/[controller]")]
public class UploadsController : ControllerBase
{
    private readonly DatabaseService _db;
    private readonly AppTimeService _clock;
    private readonly IConfiguration _config;
    private readonly IHttpClientFactory _http;
    private readonly RobotConnectionService _robotService;

    public UploadsController(DatabaseService db, AppTimeService clock, IConfiguration config, IHttpClientFactory http, RobotConnectionService robotService)
    {
        _db = db;
        _clock = clock;
        _config = config;
        _http = http;
        _robotService = robotService;
    }

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

        if (_robotService.GetUserCar(userId) == null)
            return StatusCode(403, new { error = "No robot car selected. Please select a robot car first." });

        return null;
    }

    [HttpPost("upload")]
    [Authorize]
    [RequestSizeLimit(10_485_760)]
    public async Task<IActionResult> Upload(IFormFile? codeFile)
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();
        if (codeFile == null)
            return BadRequest(new { error = "No file uploaded" });

        var ext = Path.GetExtension(codeFile.FileName).ToLowerInvariant();
        if (ext != ".py")
            return BadRequest(new { error = "Only Python files (.py) are allowed" });

        var maxSize = _config.GetValue<long>("MaxFileSize", 10 * 1024 * 1024);
        if (codeFile.Length > maxSize)
            return BadRequest(new { error = "File too large" });

        var blocked = await RequireBookingAndSelectedCarAsync(userId.Value);
        if (blocked != null) return blocked;

        var car = _robotService.GetUserCar(userId.Value)!;

        await using var ms = new MemoryStream();
        await codeFile.CopyToAsync(ms);
        var b64 = Convert.ToBase64String(ms.ToArray());

        try
        {
            var httpClient = _http.CreateClient();
            var resp = await httpClient.PostAsJsonAsync($"http://{car.Ip}:{car.Port}/upload_code", new
            {
                user_id = userId,
                content_base64 = b64,
                original_filename = codeFile.FileName
            });
            var text = await resp.Content.ReadAsStringAsync();
            if (!resp.IsSuccessStatusCode)
            {
                try
                {
                    var err = JsonSerializer.Deserialize<JsonElement>(text);
                    if (err.TryGetProperty("error", out var e))
                        return StatusCode((int)resp.StatusCode, new { error = e.GetString() ?? "Upload to robot failed" });
                }
                catch { /* fall through */ }
                return StatusCode((int)resp.StatusCode, new { error = "Upload to robot failed", detail = text });
            }

            object? piResponse = null;
            try { piResponse = JsonSerializer.Deserialize<object>(text); } catch { piResponse = text; }
            return Ok(new { message = "File uploaded to robot successfully", robotCar = car.Name, piResponse });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { error = $"Failed to reach robot car: {ex.Message}" });
        }
    }

    [HttpGet("my-uploads")]
    [Authorize]
    public async Task<IActionResult> MyUploads()
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();

        var blocked = await RequireBookingAndSelectedCarAsync(userId.Value);
        if (blocked != null) return blocked;

        var car = _robotService.GetUserCar(userId.Value)!;

        try
        {
            var httpClient = _http.CreateClient();
            var resp = await httpClient.GetAsync($"http://{car.Ip}:{car.Port}/user_files/{userId}");
            var text = await resp.Content.ReadAsStringAsync();
            if (!resp.IsSuccessStatusCode)
            {
                try
                {
                    var err = JsonSerializer.Deserialize<JsonElement>(text);
                    if (err.TryGetProperty("error", out var e))
                        return StatusCode((int)resp.StatusCode, new { error = e.GetString() ?? "List files failed" });
                }
                catch { /* fall through */ }
                return StatusCode((int)resp.StatusCode, new { error = "List files failed", detail = text });
            }

            using var doc = JsonDocument.Parse(string.IsNullOrWhiteSpace(text) ? "{}" : text);
            var root = doc.RootElement;
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
            return StatusCode(500, new { error = $"Failed to list files from robot: {ex.Message}" });
        }
    }

    [HttpDelete("file")]
    [Authorize]
    public async Task<IActionResult> DeleteRobotFile([FromQuery] string? filename)
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();
        if (string.IsNullOrWhiteSpace(filename))
            return BadRequest(new { error = "filename query parameter is required" });

        var blocked = await RequireBookingAndSelectedCarAsync(userId.Value);
        if (blocked != null) return blocked;

        var car = _robotService.GetUserCar(userId.Value)!;

        try
        {
            var httpClient = _http.CreateClient();
            var req = new HttpRequestMessage(HttpMethod.Delete, $"http://{car.Ip}:{car.Port}/user_file")
            {
                Content = JsonContent.Create(new { user_id = userId, filename })
            };
            var resp = await httpClient.SendAsync(req);
            var text = await resp.Content.ReadAsStringAsync();
            if (!resp.IsSuccessStatusCode)
            {
                try
                {
                    var err = JsonSerializer.Deserialize<JsonElement>(text);
                    if (err.TryGetProperty("error", out var e))
                        return StatusCode((int)resp.StatusCode, new { error = e.GetString() ?? "Delete failed" });
                }
                catch { /* fall through */ }
                return StatusCode((int)resp.StatusCode, new { error = "Delete failed", detail = text });
            }

            object? piResponse = null;
            try { piResponse = JsonSerializer.Deserialize<object>(text); } catch { piResponse = text; }
            return Ok(new { message = "File deleted on robot", robotCar = car.Name, piResponse });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { error = $"Failed to reach robot: {ex.Message}" });
        }
    }
}
