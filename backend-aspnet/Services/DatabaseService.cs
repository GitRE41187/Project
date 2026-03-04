using MySql.Data.MySqlClient;

namespace backend_aspnet.Services;

public class DatabaseService
{
    private readonly string _connectionString;

    public DatabaseService(IConfiguration config)
    {
        _connectionString = config.GetConnectionString("Default") ?? 
            "Server=localhost;Database=field_control;User=root;Password=;";
    }

    public async Task<MySqlConnection> GetConnectionAsync()
    {
        var conn = new MySqlConnection(_connectionString);
        await conn.OpenAsync();
        return conn;
    }
}
