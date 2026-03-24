using Npgsql;

namespace backend_aspnet.Services;

public class DatabaseService
{
    private readonly string _connectionString;

    public DatabaseService(IConfiguration config)
    {
        _connectionString = config.GetConnectionString("Default") ??
            "Host=localhost;Port=5432;Database=field_control;Username=postgres;Password=;";
    }

    public async Task<NpgsqlConnection> GetConnectionAsync()
    {
        var conn = new NpgsqlConnection(_connectionString);
        await conn.OpenAsync();
        return conn;
    }
}
