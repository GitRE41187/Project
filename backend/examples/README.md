# Robot Car WebSocket Connection Examples

This directory contains examples for connecting robot cars to the main server using WebSocket connections.

## Files

### 1. `robot-registration.js` (Legacy HTTP)
- Original HTTP-based robot registration example
- Uses REST API endpoints for robot management
- Suitable for simple HTTP-based communication

### 2. `robot-websocket-client.js` (New WebSocket)
- Modern WebSocket-based robot connection
- Real-time bidirectional communication
- Automatic reconnection and heartbeat management
- Better for real-time robot control and monitoring

## WebSocket Connection Flow

1. **Robot Connection**: Robot car connects to server via WebSocket
2. **Registration**: Robot sends `robot-connect` event with car details
3. **Heartbeat**: Robot sends periodic `robot-heartbeat` events
4. **Status Updates**: Server broadcasts robot status to all clients
5. **Disconnection**: Robot sends `robot-disconnect` event when shutting down

## Usage

### Starting the WebSocket Client

```bash
# Install dependencies
npm install

# Run the WebSocket client example
node robot-websocket-client.js
```

### Environment Variables

Set these environment variables for the robot car:

```bash
ROBOT_CAR_ID=robot-001
ROBOT_CAR_NAME=Alpha Bot
ROBOT_CAR_IP=192.168.1.100
ROBOT_CAR_PORT=5001
SERVER_URL=http://localhost:5000
```

## WebSocket Events

### Robot → Server Events

- `robot-connect`: Register robot with server
- `robot-heartbeat`: Send status updates
- `robot-disconnect`: Notify server of disconnection

### Server → Robot Events

- `robot-command`: Commands from server to robot
- `robot-status-update`: Status updates for other robots

### Server → Client Events

- `robot-status-update`: Real-time robot status changes
- `robot-heartbeat`: Live robot heartbeat data

## Benefits of WebSocket Connection

1. **Real-time Communication**: Instant bidirectional communication
2. **Automatic Reconnection**: Built-in reconnection logic
3. **Heartbeat Monitoring**: Live status monitoring
4. **Better Performance**: Lower latency than HTTP polling
5. **Event-driven**: Reactive programming model

## Migration from HTTP to WebSocket

To migrate existing robot cars from HTTP to WebSocket:

1. Install `python-socketio` for Python robots
2. Replace HTTP registration with WebSocket connection
3. Implement heartbeat mechanism
4. Handle reconnection logic
5. Update frontend to listen for WebSocket events

## Troubleshooting

### Connection Issues
- Check server URL and port
- Verify network connectivity
- Check firewall settings
- Monitor server logs for errors

### Heartbeat Issues
- Ensure heartbeat is sent every 30 seconds
- Check robot status in heartbeat data
- Monitor battery levels and position data

### Reconnection Issues
- Check MAX_RECONNECT_ATTEMPTS setting
- Monitor reconnection attempts in logs
- Verify server availability during reconnection
