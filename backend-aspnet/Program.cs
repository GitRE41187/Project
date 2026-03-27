using System.Text;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
using Microsoft.Extensions.Logging;
using backend_aspnet.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

builder.Services.AddSingleton<DatabaseService>();
builder.Services.AddSingleton<AppTimeService>();
builder.Services.AddSingleton<RobotConnectionService>();
builder.Services.AddHttpClient();
builder.Services.AddSignalR();

builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        policy.WithOrigins(builder.Configuration["ClientUrl"] ?? "http://localhost:3000")
            .AllowAnyHeader()
            .AllowAnyMethod()
            .AllowCredentials();
    });
});

var jwtSecret = builder.Configuration["Jwt:Secret"] ?? "your-super-secret-key-change-in-production-min-32-chars";
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.TokenValidationParameters = new Microsoft.IdentityModel.Tokens.TokenValidationParameters
        {
            ValidateIssuerSigningKey = true,
            IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtSecret)),
            ValidateIssuer = false,
            ValidateAudience = false,
            ClockSkew = TimeSpan.Zero,
            NameClaimType = "username",
            RoleClaimType = "role"
        };
    });

var app = builder.Build();

try
{
    var db = app.Services.GetRequiredService<DatabaseService>();
    var dbLogger = app.Services.GetRequiredService<ILogger<DatabaseService>>();
    await db.EnsureSchemaAppliedAsync(dbLogger);
}
catch (Exception ex)
{
    var log = app.Services.GetRequiredService<ILoggerFactory>().CreateLogger("DatabaseService");
    log.LogCritical(ex, "Failed to ensure PostgreSQL schema; API will start but DB operations may fail.");
}

app.UseCors();
app.UseDefaultFiles();
app.UseStaticFiles();
app.UseAuthentication();
app.UseAuthorization();

app.MapControllers();
app.MapHub<backend_aspnet.Hubs.RobotHub>("/hubs/robot");

app.MapGet("/api/health", () => new
{
    status = "OK",
    timestamp = DateTime.UtcNow.ToString("o"),
    uptime = Environment.TickCount64 / 1000.0
});

app.MapFallbackToFile("index.html");

app.Run();
