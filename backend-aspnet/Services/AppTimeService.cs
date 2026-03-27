namespace backend_aspnet.Services;

public class AppTimeService
{
    private readonly TimeZoneInfo _timeZone;

    public AppTimeService(IConfiguration config)
    {
        _timeZone = ResolveTimeZone(config);
    }

    public DateTime NowInRegionDb()
    {
        var local = TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, _timeZone);
        return DateTime.SpecifyKind(local, DateTimeKind.Unspecified);
    }

    private static TimeZoneInfo ResolveTimeZone(IConfiguration config)
    {
        var preferred = config["App:TimeZone"] ?? config["TIMEZONE"] ?? config["TZ"] ?? "Asia/Bangkok";
        foreach (var id in CandidateIds(preferred))
        {
            try { return TimeZoneInfo.FindSystemTimeZoneById(id); }
            catch { }
        }
        return TimeZoneInfo.Utc;
    }

    private static IEnumerable<string> CandidateIds(string preferred)
    {
        yield return preferred;
        if (preferred.Equals("Asia/Bangkok", StringComparison.OrdinalIgnoreCase))
            yield return "SE Asia Standard Time";
        if (preferred.Equals("SE Asia Standard Time", StringComparison.OrdinalIgnoreCase))
            yield return "Asia/Bangkok";
        yield return "UTC";
    }
}
