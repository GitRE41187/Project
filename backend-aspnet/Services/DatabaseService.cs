using System.Reflection;
using System.Text;
using Microsoft.Extensions.Logging;
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
    /// ตรวจว่ามีตารางหลัก (users) หรือไม่ — ถ้ายังไม่มีจะรัน embedded schema จาก backend-aspnet/database/schema.sql
    /// </summary>
    public async Task EnsureSchemaAppliedAsync(ILogger logger, CancellationToken cancellationToken = default)
    {
        await using var conn = new NpgsqlConnection(_connectionString);
        await conn.OpenAsync(cancellationToken);

        await using (var checkCmd = new NpgsqlCommand(
            """
            SELECT EXISTS (
              SELECT 1 FROM information_schema.tables
              WHERE table_schema = 'public' AND table_name = 'users'
            )
            """, conn))
        {
            var exists = (bool)(await checkCmd.ExecuteScalarAsync(cancellationToken))!;
            if (exists)
                return;
        }

        logger.LogInformation("PostgreSQL schema missing; applying embedded schema (backend-aspnet/database/schema.sql)");

        var sql = LoadEmbeddedSchemaSql();
        foreach (var statement in SplitPostgresStatements(sql))
        {
            await using var applyCmd = new NpgsqlCommand(statement, conn);
            applyCmd.CommandTimeout = 120;
            await applyCmd.ExecuteNonQueryAsync(cancellationToken);
        }

        logger.LogInformation("PostgreSQL schema applied successfully.");
    }

    private static string LoadEmbeddedSchemaSql()
    {
        var assembly = Assembly.GetExecutingAssembly();
        var name = assembly.GetManifestResourceNames()
            .FirstOrDefault(n => n.EndsWith("DatabaseSchema.sql", StringComparison.Ordinal));
        if (name == null)
            throw new InvalidOperationException(
                "Embedded schema not found (expected resource ending with DatabaseSchema.sql).");

        using var stream = assembly.GetManifestResourceStream(name)!;
        using var reader = new StreamReader(stream);
        return reader.ReadToEnd();
    }

    /// <summary>
    /// แยกคำสั่ง SQL ตาม `;` โดยไม่ตัดภายใน dollar-quoted string ($$ ... $$) — ใช้กับฟังก์ชัน plpgsql
    /// </summary>
    private static IEnumerable<string> SplitPostgresStatements(string sql)
    {
        var inDollarQuote = false;
        var inLineComment = false;
        var sb = new StringBuilder();
        for (var i = 0; i < sql.Length; i++)
        {
            if (inLineComment)
            {
                if (sql[i] == '\n' || sql[i] == '\r')
                    inLineComment = false;
                continue;
            }

            if (!inDollarQuote && i < sql.Length - 1 && sql[i] == '-' && sql[i + 1] == '-')
            {
                inLineComment = true;
                i++;
                continue;
            }

            if (i < sql.Length - 1 && sql[i] == '$' && sql[i + 1] == '$')
            {
                inDollarQuote = !inDollarQuote;
                sb.Append("$$");
                i++;
                continue;
            }

            if (!inDollarQuote && sql[i] == ';')
            {
                var s = sb.ToString().Trim();
                if (s.Length > 0)
                    yield return s;
                sb.Clear();
                continue;
            }

            sb.Append(sql[i]);
        }

        var tail = sb.ToString().Trim();
        if (tail.Length > 0)
            yield return tail;
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
