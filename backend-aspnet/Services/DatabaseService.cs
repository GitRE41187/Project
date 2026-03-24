using Npgsql;

namespace backend_aspnet.Services;

public class DatabaseService
{
    private readonly string _connectionString;

    public DatabaseService(IConfiguration config)
    {
        _connectionString = ResolveConnectionString(config);
    }

    /// <summary>
    /// 1) DATABASE_URL — รูปแบบ postgres:// ที่ Render (และบริการอื่น) มักตั้งเมื่อลิงก์ PostgreSQL<br/>
    /// 2) ConnectionStrings:Default — Npgsql แบบ Host=...;...<br/>
    /// 3) ค่าเริ่มต้นสำหรับ dev บนเครื่อง
    /// </summary>
    private static string ResolveConnectionString(IConfiguration config)
    {
        var fromEnv = Environment.GetEnvironmentVariable("DATABASE_URL");
        if (!string.IsNullOrWhiteSpace(fromEnv))
        {
            var parsed = TryFromPostgreSqlUri(fromEnv);
            if (parsed != null)
                return parsed;
        }

        var fromConfig = config.GetConnectionString("Default");
        if (!string.IsNullOrWhiteSpace(fromConfig))
            return fromConfig;

        return "Host=localhost;Port=5432;Database=field_control;Username=postgres;Password=;";
    }

    private static string? TryFromPostgreSqlUri(string url)
    {
        try
        {
            var uri = new Uri(url);
            if (uri.Scheme != "postgres" && uri.Scheme != "postgresql")
                return null;

            var userInfo = uri.UserInfo.Split(':', 2);
            var user = Uri.UnescapeDataString(userInfo[0]);
            var pass = userInfo.Length > 1 ? Uri.UnescapeDataString(userInfo[1]) : "";

            var database = uri.AbsolutePath.TrimStart('/');
            if (string.IsNullOrEmpty(database))
                database = "postgres";

            var sslMode = SslMode.Require;
            var q = uri.Query.TrimStart('?');
            if (!string.IsNullOrEmpty(q))
            {
                foreach (var part in q.Split('&', StringSplitOptions.RemoveEmptyEntries))
                {
                    var eq = part.IndexOf('=');
                    if (eq <= 0) continue;
                    var key = part[..eq];
                    var val = Uri.UnescapeDataString(part[(eq + 1)..]);
                    if (key.Equals("sslmode", StringComparison.OrdinalIgnoreCase) &&
                        val.Equals("disable", StringComparison.OrdinalIgnoreCase))
                        sslMode = SslMode.Disable;
                }
            }

            var builder = new NpgsqlConnectionStringBuilder
            {
                Host = uri.Host,
                Port = uri.Port == -1 ? 5432 : uri.Port,
                Database = database,
                Username = user,
                Password = pass,
                SslMode = sslMode
            };
            return builder.ConnectionString;
        }
        catch
        {
            return null;
        }
    }

    public async Task<NpgsqlConnection> GetConnectionAsync()
    {
        var conn = new NpgsqlConnection(_connectionString);
        await conn.OpenAsync();
        return conn;
    }
}
