using System.Text.Json;

namespace backend_aspnet.Services;

public sealed class StaticScriptEntry
{
    public string Id { get; init; } = "";
    public string FileName { get; init; } = "";
    public string Title { get; init; } = "";
    public string? Description { get; init; }
}

public sealed class StaticCodesCatalogService
{
    private readonly IWebHostEnvironment _env;
    private readonly ILogger<StaticCodesCatalogService> _logger;

    public StaticCodesCatalogService(IWebHostEnvironment env, ILogger<StaticCodesCatalogService> logger)
    {
        _env = env;
        _logger = logger;
    }

    private string? ResolveScriptsRoot()
    {
        var candidates = new[]
        {
            Path.Combine(AppContext.BaseDirectory, "static_codes"),
            Path.Combine(_env.ContentRootPath, "static_codes"),
            Path.GetFullPath(Path.Combine(_env.ContentRootPath, "..", "raspberry-pi", "static_codes"))
        };
        foreach (var dir in candidates)
        {
            try
            {
                if (Directory.Exists(dir))
                    return dir;
            }
            catch
            {
                /* ignore */
            }
        }
        return null;
    }

    private Dictionary<string, StaticManifestEntry> ReadManifest(string root)
    {
        var path = Path.Combine(root, "manifest.json");
        if (!File.Exists(path))
            return new Dictionary<string, StaticManifestEntry>(StringComparer.OrdinalIgnoreCase);
        try
        {
            var json = File.ReadAllText(path);
            var doc = JsonSerializer.Deserialize<StaticManifestFile>(json, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
                PropertyNamingPolicy = JsonNamingPolicy.CamelCase
            });
            if (doc?.Entries == null)
                return new Dictionary<string, StaticManifestEntry>(StringComparer.OrdinalIgnoreCase);
            return doc.Entries.ToDictionary(
                kv => kv.Key,
                kv => kv.Value ?? new StaticManifestEntry(),
                StringComparer.OrdinalIgnoreCase);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Could not parse static codes manifest.json");
            return new Dictionary<string, StaticManifestEntry>(StringComparer.OrdinalIgnoreCase);
        }
    }

    public IReadOnlyList<StaticScriptEntry> ListScripts()
    {
        var root = ResolveScriptsRoot();
        if (root == null)
        {
            _logger.LogWarning("Static codes directory not found (checked base dir, content root, ../raspberry-pi/static_codes)");
            return Array.Empty<StaticScriptEntry>();
        }

        var manifest = ReadManifest(root);
        var files = Directory.GetFiles(root, "*.py", SearchOption.TopDirectoryOnly)
            .Select(Path.GetFileName)
            .Where(f => f != null && !f.StartsWith("_", StringComparison.Ordinal))
            .Cast<string>()
            .OrderBy(f => f, StringComparer.OrdinalIgnoreCase)
            .ToList();

        var list = new List<StaticScriptEntry>();
        foreach (var file in files)
        {
            var stem = Path.GetFileNameWithoutExtension(file);
            manifest.TryGetValue(stem, out var meta);
            var title = string.IsNullOrWhiteSpace(meta?.Title) ? stem : meta!.Title!;
            list.Add(new StaticScriptEntry
            {
                Id = stem,
                FileName = file,
                Title = title,
                Description = meta?.Description
            });
        }
        return list;
    }

    public StaticScriptEntry? FindById(string id)
    {
        if (string.IsNullOrWhiteSpace(id))
            return null;
        return ListScripts().FirstOrDefault(s => s.Id.Equals(id.Trim(), StringComparison.OrdinalIgnoreCase));
    }

    public (bool ok, string? content, string? error) ReadSource(string id)
    {
        var entry = FindById(id);
        if (entry == null)
            return (false, null, "Script not found");
        var root = ResolveScriptsRoot();
        if (root == null)
            return (false, null, "Static codes directory not available");
        var full = Path.Combine(root, entry.FileName);
        if (!File.Exists(full) || !full.StartsWith(Path.GetFullPath(root), StringComparison.OrdinalIgnoreCase))
            return (false, null, "Invalid script path");
        try
        {
            var text = File.ReadAllText(full);
            return (true, text, null);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to read static script {File}", entry.FileName);
            return (false, null, "Could not read script file");
        }
    }

    private sealed class StaticManifestFile
    {
        public Dictionary<string, StaticManifestEntry>? Entries { get; set; }
    }

    private sealed class StaticManifestEntry
    {
        public string? Title { get; set; }
        public string? Description { get; set; }
    }
}
