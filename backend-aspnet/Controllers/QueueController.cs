using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Npgsql;
using backend_aspnet.Services;

namespace backend_aspnet.Controllers;

[ApiController]
[Route("api/[controller]")]
public class QueueController : ControllerBase
{
    private readonly DatabaseService _db;
    private readonly AppTimeService _clock;
    private readonly IHttpClientFactory _httpFactory;

    public QueueController(DatabaseService db, AppTimeService clock, IHttpClientFactory httpFactory)
    {
        _db = db;
        _clock = clock;
        _httpFactory = httpFactory;
    }

    private int? GetUserId()
    {
        var userId = User.FindFirst("userId")?.Value ?? User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        return !string.IsNullOrEmpty(userId) && int.TryParse(userId, out var uid) ? uid : null;
    }

    private static bool TryParseLocalInput(string input, out DateTime localDateTime)
    {
        if (DateTime.TryParse(input, out var parsed))
        {
            localDateTime = DateTime.SpecifyKind(parsed, DateTimeKind.Unspecified);
            return true;
        }

        localDateTime = default;
        return false;
    }

    private async Task SyncBookingStatusAsync(NpgsqlConnection conn, int? userId = null)
    {
        var now = _clock.NowInRegionDb();

        var activateSql = "UPDATE BOOKINGS SET status = 'active' WHERE status = 'pending' AND start_time <= @now AND end_time > @now";
        var doneSql = "UPDATE BOOKINGS SET status = 'done' WHERE status = 'active' AND end_time <= @now";
        if (userId.HasValue)
        {
            activateSql += " AND user_id = @uid";
            doneSql += " AND user_id = @uid";
        }

        var activate = new NpgsqlCommand(activateSql, conn);
        activate.Parameters.AddWithValue("@now", now);
        if (userId.HasValue) activate.Parameters.AddWithValue("@uid", userId.Value);
        await activate.ExecuteNonQueryAsync();

        var done = new NpgsqlCommand(doneSql, conn);
        done.Parameters.AddWithValue("@now", now);
        if (userId.HasValue) done.Parameters.AddWithValue("@uid", userId.Value);
        await done.ExecuteNonQueryAsync();
    }

    [HttpGet]
    public async Task<IActionResult> GetQueue()
    {
        await using var conn = await _db.GetConnectionAsync();
        await SyncBookingStatusAsync(conn);
        var cmd = new NpgsqlCommand(@"
            SELECT b.id, b.user_id, b.field_id, b.start_time, b.end_time, b.status, b.created_at, u.username
            FROM BOOKINGS b JOIN USERS u ON b.user_id = u.id
            WHERE b.status IN ('pending', 'active')
            ORDER BY b.start_time ASC", conn);
        await using var r = await cmd.ExecuteReaderAsync();
        var list = new List<object>();
        while (await r.ReadAsync())
        {
            list.Add(new
            {
                id = r.GetInt32(0),
                user_id = r.GetInt32(1),
                field_id = r.GetInt32(2),
                start_time = r.GetDateTime(3),
                end_time = r.GetDateTime(4),
                status = r.GetString(5),
                created_at = r.GetDateTime(6),
                username = r.GetString(7)
            });
        }
        return Ok(new { queue = list });
    }

    [HttpPost("book")]
    [Authorize]
    public async Task<IActionResult> Book([FromBody] BookRequest req)
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();

        if (string.IsNullOrEmpty(req.StartTime) || string.IsNullOrEmpty(req.EndTime))
            return BadRequest(new { error = "Start time and end time are required" });

        if (!TryParseLocalInput(req.StartTime, out var start) || !TryParseLocalInput(req.EndTime, out var end))
            return BadRequest(new { error = "Invalid time format. Please use yyyy-MM-ddTHH:mm." });
        var fieldId = req.FieldId ?? 1;

        if (start >= end) return BadRequest(new { error = "End time must be after start time" });
        var duration = end - start;
        if (duration > TimeSpan.FromHours(1))
            return BadRequest(new { error = "Booking duration must not exceed 1 hour." });
        if (start <= _clock.NowInRegionDb()) return BadRequest(new { error = "Cannot book in the past" });

        await using var conn = await _db.GetConnectionAsync();
        var check = new NpgsqlCommand(@"
            SELECT id FROM BOOKINGS WHERE field_id = @fid AND status IN ('pending', 'active')
            AND ((start_time <= @s AND end_time > @s) OR (start_time < @e AND end_time >= @e) OR (start_time >= @s AND end_time <= @e))", conn);
        check.Parameters.AddWithValue("@fid", fieldId);
        check.Parameters.AddWithValue("@s", start);
        check.Parameters.AddWithValue("@e", end);
        await using (var r = await check.ExecuteReaderAsync())
        {
            if (await r.ReadAsync())
                return BadRequest(new { error = "Time slot conflicts with existing booking" });
        }

        var insert = new NpgsqlCommand("INSERT INTO BOOKINGS (user_id, field_id, start_time, end_time) VALUES (@uid, @fid, @s, @e) RETURNING id", conn);
        insert.Parameters.AddWithValue("@uid", userId);
        insert.Parameters.AddWithValue("@fid", fieldId);
        insert.Parameters.AddWithValue("@s", start);
        insert.Parameters.AddWithValue("@e", end);
        var bookingId = (int)(await insert.ExecuteScalarAsync())!;

        var log = new NpgsqlCommand("INSERT INTO EXECUTION_LOGS (user_id, booking_id, action, details) VALUES (@uid, @bid, 'upload', @d)", conn);
        log.Parameters.AddWithValue("@uid", userId);
        log.Parameters.AddWithValue("@bid", bookingId);
        log.Parameters.AddWithValue("@d", $"Booked slot from {start} to {end}");
        await log.ExecuteNonQueryAsync();

        return StatusCode(201, new { message = "Slot booked successfully", bookingId });
    }

    [HttpDelete("cancel/{bookingId}")]
    [Authorize]
    public async Task<IActionResult> Cancel(int bookingId)
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();

        await using var conn = await _db.GetConnectionAsync();
        var cmd = new NpgsqlCommand("SELECT id, status FROM BOOKINGS WHERE id = @id AND user_id = @uid", conn);
        cmd.Parameters.AddWithValue("@id", bookingId);
        cmd.Parameters.AddWithValue("@uid", userId);
        await using var r = await cmd.ExecuteReaderAsync();
        if (!await r.ReadAsync())
            return NotFound(new { error = "Booking not found" });
        var status = r.GetString(1);
        await r.CloseAsync();

        if (status == "done")
            return BadRequest(new { error = "Cannot cancel completed booking" });

        if (status == "active")
        {
            var carCmd = new NpgsqlCommand("SELECT ip, port FROM ROBOT_CARS WHERE current_user_id = @uid LIMIT 1", conn);
            carCmd.Parameters.AddWithValue("@uid", userId);
            await using var carR = await carCmd.ExecuteReaderAsync();
            if (await carR.ReadAsync())
            {
                var ip = carR.GetString(0);
                var port = carR.GetInt32(1);
                try
                {
                    var http = _httpFactory.CreateClient();
                    await http.PostAsJsonAsync($"http://{ip}:{port}/stop", new { user_id = userId });
                }
                catch { /* ignore */ }
            }
        }

        var update = new NpgsqlCommand("UPDATE BOOKINGS SET status = 'cancelled' WHERE id = @id", conn);
        update.Parameters.AddWithValue("@id", bookingId);
        await update.ExecuteNonQueryAsync();

        var log = new NpgsqlCommand("INSERT INTO EXECUTION_LOGS (user_id, booking_id, action, details) VALUES (@uid, @bid, 'stop', 'Booking cancelled by user')", conn);
        log.Parameters.AddWithValue("@uid", userId);
        log.Parameters.AddWithValue("@bid", bookingId);
        await log.ExecuteNonQueryAsync();

        return Ok(new { message = "Booking cancelled successfully" });
    }

    [HttpGet("my-bookings")]
    [Authorize]
    public async Task<IActionResult> MyBookings()
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();

        await using var conn = await _db.GetConnectionAsync();
        await SyncBookingStatusAsync(conn, userId);
        var cmd = new NpgsqlCommand(@"
            SELECT b.id, b.field_id, b.start_time, b.end_time, b.status, b.created_at, f.name as field_name
            FROM BOOKINGS b LEFT JOIN FIELDS f ON b.field_id = f.id
            WHERE b.user_id = @uid ORDER BY b.created_at DESC", conn);
        cmd.Parameters.AddWithValue("@uid", userId);
        await using var r = await cmd.ExecuteReaderAsync();
        var list = new List<object>();
        while (await r.ReadAsync())
        {
            list.Add(new
            {
                id = r.GetInt32(0),
                field_id = r.GetInt32(1),
                start_time = r.GetDateTime(2),
                end_time = r.GetDateTime(3),
                status = r.GetString(4),
                created_at = r.GetDateTime(5),
                field_name = r.IsDBNull(6) ? "Main Field" : r.GetString(6)
            });
        }
        return Ok(new { bookings = list });
    }

    [HttpGet("admin/all")]
    [Authorize(Roles = "admin")]
    public async Task<IActionResult> AdminAll()
    {
        await using var conn = await _db.GetConnectionAsync();
        await SyncBookingStatusAsync(conn);
        var cmd = new NpgsqlCommand(@"
            SELECT b.id, b.user_id, b.field_id, b.start_time, b.end_time, b.status, b.created_at, u.username, f.name as field_name
            FROM BOOKINGS b JOIN USERS u ON b.user_id = u.id LEFT JOIN FIELDS f ON b.field_id = f.id
            ORDER BY b.created_at DESC", conn);
        await using var r = await cmd.ExecuteReaderAsync();
        var list = new List<object>();
        while (await r.ReadAsync())
        {
            list.Add(new
            {
                id = r.GetInt32(0),
                user_id = r.GetInt32(1),
                field_id = r.GetInt32(2),
                start_time = r.GetDateTime(3),
                end_time = r.GetDateTime(4),
                status = r.GetString(5),
                created_at = r.GetDateTime(6),
                username = r.GetString(7),
                field_name = r.IsDBNull(8) ? "Main Field" : r.GetString(8)
            });
        }
        return Ok(new { bookings = list });
    }
}

public class BookRequest
{
    public string? StartTime { get; set; }
    public string? EndTime { get; set; }
    public int? FieldId { get; set; }
}
