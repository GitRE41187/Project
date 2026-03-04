using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using MySql.Data.MySqlClient;
using backend_aspnet.Services;

namespace backend_aspnet.Controllers;

[ApiController]
[Route("api/[controller]")]
public class LogsController : ControllerBase
{
    private readonly DatabaseService _db;

    public LogsController(DatabaseService db)
    {
        _db = db;
    }

    private int? GetUserId()
    {
        var userId = User.FindFirst("userId")?.Value ?? User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        return !string.IsNullOrEmpty(userId) && int.TryParse(userId, out var uid) ? uid : null;
    }

    [HttpGet("my-logs")]
    [Authorize]
    public async Task<IActionResult> MyLogs([FromQuery] int limit = 50, [FromQuery] int offset = 0)
    {
        var userId = GetUserId();
        if (userId == null) return Unauthorized();

        await using var conn = await _db.GetConnectionAsync();
        var cmd = new MySqlCommand(@"
            SELECT el.id, el.action, el.details, el.executed_at, b.start_time, b.end_time
            FROM EXECUTION_LOGS el LEFT JOIN BOOKINGS b ON el.booking_id = b.id
            WHERE el.user_id = @uid ORDER BY el.executed_at DESC LIMIT @lim OFFSET @off", conn);
        cmd.Parameters.AddWithValue("@uid", userId);
        cmd.Parameters.AddWithValue("@lim", limit);
        cmd.Parameters.AddWithValue("@off", offset);
        await using var r = await cmd.ExecuteReaderAsync();
        var list = new List<object>();
        while (await r.ReadAsync())
        {
            list.Add(new
            {
                id = r.GetInt32(0),
                action = r.GetString(1),
                details = r.GetString(2),
                executed_at = r.GetDateTime(3),
                start_time = r.IsDBNull(4) ? (DateTime?)null : r.GetDateTime(4),
                end_time = r.IsDBNull(5) ? (DateTime?)null : r.GetDateTime(5)
            });
        }
        return Ok(new { logs = list });
    }

    [HttpGet("admin/all")]
    [Authorize(Roles = "admin")]
    public async Task<IActionResult> AdminAll([FromQuery] int limit = 100, [FromQuery] int offset = 0, [FromQuery] int? userId = null, [FromQuery] string? action = null)
    {
        await using var conn = await _db.GetConnectionAsync();
        var sql = @"
            SELECT el.id, el.user_id, el.action, el.details, el.executed_at, u.username, b.start_time, b.end_time
            FROM EXECUTION_LOGS el JOIN USERS u ON el.user_id = u.id LEFT JOIN BOOKINGS b ON el.booking_id = b.id
            WHERE 1=1";
        if (userId.HasValue) sql += " AND el.user_id = @uid";
        if (!string.IsNullOrEmpty(action)) sql += " AND el.action = @act";
        sql += " ORDER BY el.executed_at DESC LIMIT @lim OFFSET @off";

        var cmd = new MySqlCommand(sql, conn);
        cmd.Parameters.AddWithValue("@lim", limit);
        cmd.Parameters.AddWithValue("@off", offset);
        if (userId.HasValue) cmd.Parameters.AddWithValue("@uid", userId);
        if (!string.IsNullOrEmpty(action)) cmd.Parameters.AddWithValue("@act", action);

        await using var r = await cmd.ExecuteReaderAsync();
        var list = new List<object>();
        while (await r.ReadAsync())
        {
            list.Add(new
            {
                id = r.GetInt32(0),
                user_id = r.GetInt32(1),
                action = r.GetString(2),
                details = r.GetString(3),
                executed_at = r.GetDateTime(4),
                username = r.GetString(5),
                start_time = r.IsDBNull(6) ? (DateTime?)null : r.GetDateTime(6),
                end_time = r.IsDBNull(7) ? (DateTime?)null : r.GetDateTime(7)
            });
        }
        return Ok(new { logs = list });
    }

    [HttpGet("admin/stats")]
    [Authorize(Roles = "admin")]
    public async Task<IActionResult> AdminStats()
    {
        await using var conn = await _db.GetConnectionAsync();

        var stats = new Dictionary<string, int>();
        foreach (var (key, sql) in new[] {
            ("totalUsers", "SELECT COUNT(*) FROM USERS"),
            ("totalBookings", "SELECT COUNT(*) FROM BOOKINGS"),
            ("activeBookings", "SELECT COUNT(*) FROM BOOKINGS WHERE status = 'active' AND start_time <= NOW() AND end_time > NOW()"),
            ("totalUploads", "SELECT COUNT(*) FROM UPLOADS"),
            ("recentActivity", "SELECT COUNT(*) FROM EXECUTION_LOGS WHERE executed_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)")
        })
        {
            var cmd = new MySqlCommand(sql, conn);
            stats[key] = Convert.ToInt32(await cmd.ExecuteScalarAsync());
        }

        var actionCmd = new MySqlCommand(@"
            SELECT action, COUNT(*) as cnt FROM EXECUTION_LOGS
            WHERE executed_at >= DATE_SUB(NOW(), INTERVAL 7 DAY) GROUP BY action", conn);
        await using var r = await actionCmd.ExecuteReaderAsync();
        var actionBreakdown = new List<object>();
        while (await r.ReadAsync())
            actionBreakdown.Add(new { action = r.GetString(0), count = r.GetInt64(1) });

        return Ok(new { stats, actionBreakdown });
    }
}
