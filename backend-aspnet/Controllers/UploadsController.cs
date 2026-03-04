using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using MySql.Data.MySqlClient;
using backend_aspnet.Services;

namespace backend_aspnet.Controllers;

[ApiController]
[Route("api/[controller]")]
public class UploadsController : ControllerBase
{
    private readonly DatabaseService _db;
    private readonly IConfiguration _config;
    private readonly IHttpClientFactory _http;
    private readonly IWebHostEnvironment _env;
    private readonly RobotConnectionService _robotService;

    public UploadsController(DatabaseService db, IConfiguration config, IHttpClientFactory http, IWebHostEnvironment env, RobotConnectionService robotService)
    {
        _db = db;
        _config = config;
        _http = http;
        _env = env;
        _robotService = robotService;
    }

    private int? GetUserId()
    {
        var userId = User.FindFirst("userId")?.Value ?? User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        return !string.IsNullOrEmpty(userId) && int.TryParse(userId, out var uid) ? uid : null;
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

        var uploadDir = _config["UploadDir"] ?? "uploads";
        var fullDir = Path.Combine(_env.ContentRootPath, uploadDir);
        Directory.CreateDirectory(fullDir);
        var fileName = $"user_{userId}_{DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()}{ext}";
        var filePath = Path.Combine(fullDir, fileName);
        await using (var stream = new FileStream(filePath, FileMode.Create))
            await codeFile.CopyToAsync(stream);

        var relativePath = Path.Combine(uploadDir, fileName).Replace("\\", "/");

        await using var conn = await _db.GetConnectionAsync();
        var cmd = new MySqlCommand("INSERT INTO UPLOADS (user_id, original_filename, file_path, file_size) VALUES (@uid, @orig, @path, @size)", conn);
        cmd.Parameters.AddWithValue("@uid", userId);
        cmd.Parameters.AddWithValue("@orig", codeFile.FileName);
        cmd.Parameters.AddWithValue("@path", filePath);
        cmd.Parameters.AddWithValue("@size", codeFile.Length);
        await cmd.ExecuteNonQueryAsync();
        var uploadId = (int)cmd.LastInsertedId;

        var bookingCmd = new MySqlCommand(@"SELECT id FROM BOOKINGS
            WHERE user_id = @uid AND status = 'active' AND start_time <= NOW() AND end_time > NOW()", conn);
        bookingCmd.Parameters.AddWithValue("@uid", userId);
        await using var br = await bookingCmd.ExecuteReaderAsync();
        var hasActiveBooking = await br.ReadAsync();
        await br.CloseAsync();

        if (hasActiveBooking)
        {
            var car = _robotService.GetUserCar(userId.Value);
            if (car != null)
            {
                try
                {
                    var httpClient = _http.CreateClient();
                    await httpClient.PostAsJsonAsync($"http://{car.Ip}:{car.Port}/upload_code", new
                    {
                        user_id = userId,
                        file_path = filePath,
                        original_filename = codeFile.FileName
                    });
                    var logCmd = new MySqlCommand("INSERT INTO EXECUTION_LOGS (user_id, action, details) VALUES (@uid, 'upload', @d)", conn);
                    logCmd.Parameters.AddWithValue("@uid", userId);
                    logCmd.Parameters.AddWithValue("@d", $"Code uploaded and sent to Pi: {codeFile.FileName}");
                    await logCmd.ExecuteNonQueryAsync();
                    return Ok(new { message = "File uploaded and sent to Raspberry Pi successfully", uploadId, hasActiveBooking = true });
                }
                catch
                {
                    return StatusCode(500, new { error = "File uploaded but failed to send to Raspberry Pi", uploadId, hasActiveBooking = true });
                }
            }
        }

        return Ok(new
        {
            message = "File uploaded successfully. Upload to Raspberry Pi when you have an active booking.",
            uploadId,
            hasActiveBooking = false
        });
    }

    [HttpGet("my-uploads")]
    [Authorize]
    public async Task<IActionResult> MyUploads()
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();

        await using var conn = await _db.GetConnectionAsync();
        var cmd = new MySqlCommand("SELECT id, original_filename, file_path, file_size, uploaded_at FROM UPLOADS WHERE user_id = @uid ORDER BY uploaded_at DESC", conn);
        cmd.Parameters.AddWithValue("@uid", userId);
        await using var r = await cmd.ExecuteReaderAsync();
        var list = new List<object>();
        while (await r.ReadAsync())
        {
            list.Add(new
            {
                id = r.GetInt32(0),
                original_filename = r.GetString(1),
                file_path = r.GetString(2),
                file_size = r.GetInt64(3),
                uploaded_at = r.GetDateTime(4)
            });
        }
        return Ok(new { uploads = list });
    }

    [HttpDelete("{uploadId}")]
    [Authorize]
    public async Task<IActionResult> Delete(int uploadId)
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();

        await using var conn = await _db.GetConnectionAsync();
        var cmd = new MySqlCommand("SELECT file_path FROM UPLOADS WHERE id = @id AND user_id = @uid", conn);
        cmd.Parameters.AddWithValue("@id", uploadId);
        cmd.Parameters.AddWithValue("@uid", userId);
        await using var r = await cmd.ExecuteReaderAsync();
        if (!await r.ReadAsync())
            return NotFound(new { error = "Upload not found" });
        var filePath = r.GetString(0);
        await r.CloseAsync();

        var del = new MySqlCommand("DELETE FROM UPLOADS WHERE id = @id", conn);
        del.Parameters.AddWithValue("@id", uploadId);
        await del.ExecuteNonQueryAsync();

        if (System.IO.File.Exists(filePath))
            try { System.IO.File.Delete(filePath); } catch { }

        return Ok(new { message = "Upload deleted successfully" });
    }

    [HttpGet("download/{uploadId}")]
    [Authorize]
    public async Task<IActionResult> Download(int uploadId)
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();

        await using var conn = await _db.GetConnectionAsync();
        var cmd = new MySqlCommand("SELECT original_filename, file_path FROM UPLOADS WHERE id = @id AND user_id = @uid", conn);
        cmd.Parameters.AddWithValue("@id", uploadId);
        cmd.Parameters.AddWithValue("@uid", userId);
        await using var r = await cmd.ExecuteReaderAsync();
        if (!await r.ReadAsync())
            return NotFound(new { error = "Upload not found" });
        var orig = r.GetString(0);
        var path = r.GetString(1);

        if (!System.IO.File.Exists(path))
            return NotFound(new { error = "File not found on server" });

        return PhysicalFile(path, "application/octet-stream", orig);
    }
}
