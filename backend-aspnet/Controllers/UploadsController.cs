using System.Net.Http.Json;
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
    private readonly IHttpClientFactory _http;
    private readonly RobotConnectionService _robotService;
    private readonly ILogger<UploadsController> _logger;

    public UploadsController(DatabaseService db, AppTimeService clock, IConfiguration config, IHttpClientFactory http, RobotConnectionService robotService, ILogger<UploadsController> logger)
    {
        _db = db;
        _clock = clock;
        _config = config;
        _http = http;
        _robotService = robotService;
        _logger = logger;
    }

    private static object ParsePiPayloadOrRaw(string text)
    {
        try
        {
            return JsonSerializer.Deserialize<object>(text) ?? new { };
        }
        catch
        {
            return new { raw = text };
        }
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
            var httpClient = _http.CreateClient();
            httpClient.Timeout = TimeSpan.FromMinutes(2);
            var piBody = new Dictionary<string, object?>
            {
                ["user_id"] = userId.Value,
                ["content_base64"] = b64,
                ["original_filename"] = codeFile.FileName
            };
            var resp = await httpClient.PostAsJsonAsync($"http://{car.Ip}:{car.Port}/upload_code", piBody);
            var text = await resp.Content.ReadAsStringAsync();
            if (!resp.IsSuccessStatusCode)
            {
                _logger.LogWarning("Upload to robot failed. user={UserId}, car={CarId}, status={StatusCode}, body={Body}", userId.Value, car.CarId, (int)resp.StatusCode, text);
                try
                {
                    var err = JsonSerializer.Deserialize<JsonElement>(text);
                    if (err.TryGetProperty("error", out var e))
                        return StatusCode((int)resp.StatusCode, new { error = e.GetString() ?? "Upload to robot failed" });
                }
                catch { /* fall through */ }
                return StatusCode((int)resp.StatusCode, new { error = "Upload to robot failed", detail = text });
            }

            _logger.LogInformation("Upload to robot success. user={UserId}, car={CarId}, filename={Filename}", userId.Value, car.CarId, codeFile.FileName);
            var piResponse = ParsePiPayloadOrRaw(text);
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
            var httpClient = _http.CreateClient();
            httpClient.Timeout = TimeSpan.FromSeconds(60);
            var resp = await httpClient.GetAsync($"http://{car.Ip}:{car.Port}/user_files/{userId}");
            var text = await resp.Content.ReadAsStringAsync();
            if (!resp.IsSuccessStatusCode)
            {
                _logger.LogWarning("List robot files failed. user={UserId}, car={CarId}, status={StatusCode}, body={Body}", userId.Value, car.CarId, (int)resp.StatusCode, text);
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
            var httpClient = _http.CreateClient();
            httpClient.Timeout = TimeSpan.FromSeconds(60);
            var req = new HttpRequestMessage(HttpMethod.Delete, $"http://{car.Ip}:{car.Port}/user_file")
            {
                Content = JsonContent.Create(new { user_id = userId, filename })
            };
            var resp = await httpClient.SendAsync(req);
            var text = await resp.Content.ReadAsStringAsync();
            if (!resp.IsSuccessStatusCode)
            {
                _logger.LogWarning("Delete robot file failed. user={UserId}, car={CarId}, file={Filename}, status={StatusCode}, body={Body}", userId.Value, car.CarId, filename, (int)resp.StatusCode, text);
                try
                {
                    var err = JsonSerializer.Deserialize<JsonElement>(text);
                    if (err.TryGetProperty("error", out var e))
                        return StatusCode((int)resp.StatusCode, new { error = e.GetString() ?? "Delete failed" });
                }
                catch { /* fall through */ }
                return StatusCode((int)resp.StatusCode, new { error = "Delete failed", detail = text });
            }

            _logger.LogInformation("Delete robot file success. user={UserId}, car={CarId}, file={Filename}", userId.Value, car.CarId, filename);
            var piResponse = ParsePiPayloadOrRaw(text);
            return Ok(new { message = "File deleted on robot", robotCar = car.Name, piResponse });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Delete robot file exception. user={UserId}, car={CarId}, file={Filename}", userId.Value, car.CarId, filename);
            return StatusCode(500, new { error = $"Failed to reach robot: {ex.Message}" });
        }
    }
}
