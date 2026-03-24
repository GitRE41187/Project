# Build context = root ของ repository (ใช้เมื่อ Render ไม่ได้ตั้ง Root Directory เป็น backend-aspnet)
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
CMD ["sh", "-c", "exec dotnet backend-aspnet.dll --urls http://0.0.0.0:$PORT"]
