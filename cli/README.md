# Secure Agent CLI

Management CLI for the Secure Agent Architecture.

The CLI runs inside a Docker container and communicates with all services via the internal Docker network.

## Starting the System

Start all core services:
```bash
make up
```

Start with CLI included (for health checks and management):
```bash
make up-cli
```

## Usage

The CLI is accessed via `docker-compose exec`:

```bash
docker-compose exec cli secure-agent <command> [options]
```

### Health Check

Check the health of all system components:

```bash
make health
# or
docker-compose exec cli secure-agent health
```

### Health Check Options

**Verbose mode** - Show detailed information:
```bash
make health-verbose
# or
docker-compose exec cli secure-agent health --verbose
```

**Watch mode** - Continuously monitor health status:
```bash
make health-watch
# or
docker-compose exec cli secure-agent health --watch
```

### Other Commands

**Submit a task:**
```bash
docker-compose exec cli secure-agent submit "Your task here"
```

**Get task result:**
```bash
docker-compose exec cli secure-agent result <task_id>
```

**List tasks:**
```bash
docker-compose exec cli secure-agent tasks
```

**Get/Set config:**
```bash
docker-compose exec cli secure-agent config <key>
docker-compose exec cli secure-agent config <key> <json_value>
```

**Show queue status:**
```bash
docker-compose exec cli secure-agent queue
```

**Clear queue:**
```bash
docker-compose exec cli secure-agent queue --clear
```

## Health Check Components

The health check monitors the following components:

| Component | Check Method | Docker Service |
|-----------|-------------|----------------|
| **Gateway** | HTTP `/health` endpoint | `gateway` |
| **Adaptor Channel** | Redis queue connectivity | `redis` |
| **Agent** | Redis heartbeat and status | `agent` |
| **Redis** | Connection and info query | `redis` |
| **LiteLLM** | HTTP health endpoint | `litellm` |
| **Squid** | TCP port connectivity | `squid` |
| **Connections** | Inter-component network tests | All services |

## Health Status

- **healthy**: Component is fully operational
- **degraded**: Component is working but with issues (e.g., stale heartbeat)
- **unhealthy**: Component is down or inaccessible

## Environment Variables

The CLI service uses the following environment variables (configured in docker-compose.yml):

```bash
# Redis connection
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=${REDIS_PASSWORD}

# Gateway URL
GATEWAY_URL=http://gateway:8080

# LiteLLM URL
LITELM_URL=http://litellm:4000

# Squid proxy
SQUID_HOST=squid
SQUID_PORT=3128
```

## Docker Service Names

When the CLI runs inside Docker, it uses service names to communicate with other containers:

| Service | Internal Address |
|---------|------------------|
| Redis | `redis:6379` |
| Gateway | `http://gateway:8080` |
| LiteLLM | `http://litellm:4000` |
| Squid | `squid:3128` |
| Agent | `agent` (via Redis queue) |

## Example Output

```
┌─────────────────────────────────────────────────────────────────────────┐
│ System Status: HEALTHY - 2026-02-18 12:45:30                          │
├─────────────────────────────────────────────────────────────────────────┤
│ Component            Status             Response Time                  │
├─────────────────────────────────────────────────────────────────────────┤
│ Gateway              HEALTHY            45.2 ms                        │
│ Adaptor Channel      HEALTHY            12.3 ms                        │
│ Agent                HEALTHY            23.1 ms                        │
│ Redis                HEALTHY            8.7 ms                         │
│ LiteLLM              HEALTHY            32.4 ms                        │
│ Squid                HEALTHY            5.2 ms                         │
│ Connections          HEALTHY            15.8 ms                        │
└─────────────────────────────────────────────────────────────────────────┘
```

## Troubleshooting

**CLI not running**: Start the CLI service:
```bash
make up-cli
# or
docker-compose --profile tools up -d
```

**Gateway unreachable**: Check Docker containers:
```bash
docker-compose ps
docker-compose logs gateway
```

**Redis connection failed**: Verify password in `.env` file matches Redis configuration.

**Services not starting**: Check logs:
```bash
docker-compose logs -f
```

## Development

For local development (outside Docker), install dependencies manually:
```bash
cd cli
pip install -r requirements.txt
python cli/main.py health
```

Note: When running locally, you'll need to use `localhost` instead of service names:
```bash
REDIS_HOST=localhost REDIS_PASSWORD=your_password python cli/main.py health
```
