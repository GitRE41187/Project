using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using Microsoft.AspNetCore.Mvc;
using Microsoft.IdentityModel.Tokens;
using Npgsql;
using backend_aspnet.Services;

namespace backend_aspnet.Controllers;

[ApiController]
[Route("api/[controller]")]
public class AuthController : ControllerBase
{
    private readonly DatabaseService _db;
    private readonly IConfiguration _config;

    public AuthController(DatabaseService db, IConfiguration config)
    {
        _db = db;
        _config = config;
    }

    [HttpPost("register")]
    public async Task<IActionResult> Register([FromBody] RegisterRequest req)
    {
        if (string.IsNullOrWhiteSpace(req.Username) || string.IsNullOrWhiteSpace(req.Email) || string.IsNullOrWhiteSpace(req.Password))
            return BadRequest(new { error = "All fields are required" });
        if (req.Password.Length < 6)
            return BadRequest(new { error = "Password must be at least 6 characters" });

        await using var conn = await _db.GetConnectionAsync();
        var cmd = new NpgsqlCommand("SELECT id FROM USERS WHERE username = @u OR email = @e", conn);
        cmd.Parameters.AddWithValue("@u", req.Username);
        cmd.Parameters.AddWithValue("@e", req.Email);
        await using var r = await cmd.ExecuteReaderAsync();
        if (await r.ReadAsync())
            return BadRequest(new { error = "Username or email already exists" });
        await r.CloseAsync();

        var hash = BCrypt.Net.BCrypt.HashPassword(req.Password, 10);
        var insert = new NpgsqlCommand("INSERT INTO USERS (username, email, password_hash) VALUES (@u, @e, @h) RETURNING id", conn);
        insert.Parameters.AddWithValue("@u", req.Username);
        insert.Parameters.AddWithValue("@e", req.Email);
        insert.Parameters.AddWithValue("@h", hash);
        var userId = (int)(await insert.ExecuteScalarAsync())!;

        var token = GenerateToken(userId, req.Username, "user");
        return StatusCode(201, new
        {
            message = "User registered successfully",
            token,
            user = new { id = userId, username = req.Username, email = req.Email, role = "user" }
        });
    }

    [HttpPost("login")]
    public async Task<IActionResult> Login([FromBody] LoginRequest req)
    {
        if (string.IsNullOrWhiteSpace(req.Username) || string.IsNullOrWhiteSpace(req.Password))
            return Unauthorized(new { error = "Invalid credentials" });

        await using var conn = await _db.GetConnectionAsync();
        var cmd = new NpgsqlCommand("SELECT id, username, email, password_hash, role FROM USERS WHERE username = @u", conn);
        cmd.Parameters.AddWithValue("@u", req.Username);
        await using var r = await cmd.ExecuteReaderAsync();
        if (!await r.ReadAsync())
            return Unauthorized(new { error = "Invalid credentials" });

        var id = r.GetInt32(0);
        var username = r.GetString(1);
        var email = r.GetString(2);
        var hash = r.GetString(3);
        var role = r.GetString(4);

        if (!BCrypt.Net.BCrypt.Verify(req.Password, hash))
            return Unauthorized(new { error = "Invalid credentials" });

        var token = GenerateToken(id, username, role);
        return Ok(new
        {
            message = "Login successful",
            token,
            user = new { id, username, email, role }
        });
    }

    [HttpGet("me")]
    [Microsoft.AspNetCore.Authorization.Authorize]
    public async Task<IActionResult> Me()
    {
        var userId = User.FindFirst("userId")?.Value ?? User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        if (string.IsNullOrEmpty(userId) || !int.TryParse(userId, out var uid))
            return Unauthorized();

        await using var conn = await _db.GetConnectionAsync();
        var cmd = new NpgsqlCommand("SELECT id, username, email, role, created_at FROM USERS WHERE id = @id", conn);
        cmd.Parameters.AddWithValue("@id", uid);
        await using var r = await cmd.ExecuteReaderAsync();
        if (!await r.ReadAsync())
            return NotFound(new { error = "User not found" });

        return Ok(new
        {
            user = new
            {
                id = r.GetInt32(0),
                username = r.GetString(1),
                email = r.GetString(2),
                role = r.GetString(3),
                created_at = r.GetDateTime(4)
            }
        });
    }

    private string GenerateToken(int userId, string username, string role)
    {
        var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(_config["Jwt:Secret"] ?? "default-secret"));
        var creds = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);
        var exp = _config["Jwt:ExpiresIn"] == "24h" ? 24 : 24;
        var claims = new[]
        {
            new Claim("userId", userId.ToString()),
            new Claim("username", username),
            new Claim("role", role)
        };
        var token = new JwtSecurityToken(
            claims: claims,
            expires: DateTime.UtcNow.AddHours(exp),
            signingCredentials: creds
        );
        return new JwtSecurityTokenHandler().WriteToken(token);
    }
}

public class RegisterRequest
{
    public string? Username { get; set; }
    public string? Email { get; set; }
    public string? Password { get; set; }
}

public class LoginRequest
{
    public string? Username { get; set; }
    public string? Password { get; set; }
}
