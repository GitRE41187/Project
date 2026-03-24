# Build context = โฟลเดอร์ backend-aspnet (ตั้ง Root Directory บน Render เป็น backend-aspnet)
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY backend-aspnet.csproj .
RUN dotnet restore backend-aspnet.csproj
COPY . .
RUN dotnet publish backend-aspnet.csproj -c Release -o /app/publish /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY --from=build /app/publish .
ENV ASPNETCORE_ENVIRONMENT=Production
CMD ["sh", "-c", "exec dotnet backend-aspnet.dll --urls http://0.0.0.0:$PORT"]
