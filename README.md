# Secure Autonomous Agent Architecture

A secure, production-ready architecture for AI agent execution that prevents "OpenClaw" style vulnerabilities through strict network isolation, ingress/egress filtering, and ACL-based configuration management.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Internet                                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ Ingress
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    WasmEdge Gateway (Rust)                       │
│  - Validates incoming requests                                   │
│  - Enforces ACL policies                                         │
│  - Routes to agent queue                                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Secure Network (internal)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   Redis     │  │   Squid     │  │   LiteLLM   │              │
│  │   (Config)  │  │  (Proxy)    │  │   (API)     │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│               Agent Runtime (Python/LangChain)                   │
│  - LangGraph agent implementation                                │
│  - NO direct internet access                                     │
│  - All egress via Squid → LiteLLM                                │
│  - Pulls tasks from Redis queue                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Security Features

1. **Network Isolation**
   - Agent has no direct internet access
   - All egress filtered through Squid proxy with whitelist
   - Only approved domains accessible

2. **Ingress Filtering**
   - WasmEdge gateway validates all requests
   - Rust-based for memory safety
   - WebAssembly for sandboxing

3. **Configuration Security**
   - Hardened Redis with ACLs
   - No file-based config for mutable data
   - Separate passwords for each component

4. **API Masking**
   - LiteLLM proxy masks LLM API keys
   - Rate limiting and budget controls
   - Failover support

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for CLI)
- Rust 1.75+ (for gateway development)

### Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd ultra-claw

# 2. Setup environment
make setup
# Edit .env with your API keys

# 3. Build and start services
make build
make up

# 4. Verify health
make logs
```

### Using the CLI

```bash
# Install CLI dependencies
make install-cli

# Check system health
python -m cli.main health

# Submit a task
python -m cli.main submit "Hello, world!"

# Watch task result
python -m cli.main result <task-id> --watch

# List all tasks
python -m cli.main tasks

# Get/set config
python -m cli.main config model
python -m cli.main config model '{"name": "claude-3-opus"}'
```

## Configuration

### Environment Variables

See `.env.example` for all required variables:

- `REDIS_*` - Redis connection and ACL passwords
- `LITELM_*` - LiteLLM configuration
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. - LLM provider keys

### Redis ACLs

Users are defined in `config/redis/users.acl`:

- `admin` - Full access
- `gateway` - Read config
- `agent` - Write tasks/results
- `cli` - Read/write config/tasks
- `litellm` - Read litellm config

### Squid Whitelist

Edit `config/squid/whitelist.txt` to add allowed domains.

## Development

### Gateway (Rust)

```bash
cd gateway
cargo run
cargo test
```

### Agent (Python)

```bash
cd agent
pip install -r requirements.txt
python -m agent.main
```

### CLI

```bash
cd cli
pip install -r requirements.txt
python -m cli.main --help
```

## Security Checklist

- [ ] All passwords changed from defaults
- [ ] API keys properly set in `.env`
- [ ] `.env` file not committed to git
- [ ] Redis ACLs configured correctly
- [ ] Squid whitelist minimal and appropriate
- [ ] LiteLLM budget limits set
- [ ] No direct agent network access configured
- [ ] Logging enabled for all components
- [ ] Health checks configured

## Troubleshooting

### Agent not processing tasks

```bash
# Check Redis queue
docker-compose exec redis redis-cli -a $REDIS_PASSWORD llen agent:queue

# Check agent logs
docker-compose logs agent
```

### Gateway connection refused

```bash
# Check gateway is running
docker-compose ps gateway

# Check gateway logs
docker-compose logs gateway
```

### Proxy errors

```bash
# Check Squid logs
docker-compose logs squid

# Verify whitelist
docker-compose exec squid cat /etc/squid/whitelist.txt
```

## License

MIT License - See LICENSE file for details

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Security

For security issues, please email security@example.com instead of using the issue tracker.
