# Build context ต้องเป็น root ของ repository (มีโฟลเดอร์ database/)
# Render: Root Directory ว่าง, Dockerfile Path = backend-aspnet/Dockerfile
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY backend-aspnet/backend-aspnet.csproj ./backend-aspnet/
RUN dotnet restore ./backend-aspnet/backend-aspnet.csproj
COPY database/schema.sql ./database/
COPY backend-aspnet/ ./backend-aspnet/
WORKDIR /src/backend-aspnet
RUN dotnet publish backend-aspnet.csproj -c Release -o /app/publish /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY --from=build /app/publish .
ENV ASPNETCORE_ENVIRONMENT=Production
# Render ตั้ง PORT ให้ที่ runtime — ฟังที่ 0.0.0.0:$PORT
CMD ["sh", "-c", "exec dotnet backend-aspnet.dll --urls http://0.0.0.0:$PORT"]
