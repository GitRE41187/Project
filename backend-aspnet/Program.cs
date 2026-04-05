using System.Text;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Http.Features;
using Microsoft.IdentityModel.Tokens;
using Microsoft.Extensions.Logging;
using backend_aspnet.Services;

var builder = WebApplication.CreateBuilder(args);

builder.WebHost.ConfigureKestrel(o => o.Limits.MaxRequestBodySize = 20 * 1024 * 1024);
builder.Services.Configure<FormOptions>(o => o.MultipartBodyLengthLimit = 20 * 1024 * 1024);

builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

builder.Services.AddSingleton<DatabaseService>();
builder.Services.AddSingleton<AppTimeService>();
builder.Services.AddSingleton<RobotConnectionService>();
builder.Services.AddSingleton<RobotCommandBrokerService>();
builder.Services.AddSingleton<StaticCodesCatalogService>();
builder.Services.AddHttpClient();
builder.Services.AddSignalR();

builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        var origins = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "http://localhost:3000",
            "http://localhost:5000",
            "https://localhost:5001"
        };
        var clientUrl = builder.Configuration["ClientUrl"];
        if (!string.IsNullOrWhiteSpace(clientUrl))
            origins.Add(clientUrl.TrimEnd('/'));
        policy.WithOrigins(origins.ToArray())
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
