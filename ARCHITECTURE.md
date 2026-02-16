# Secure Agent Architecture

## High-Level Design

This document describes architectural decisions and design patterns used in Secure Agent Architecture.

## Core Principles

### 1. Defense in Depth

Multiple layers of security controls protect the system:

1. **Network Isolation**: Agent has no direct internet access
2. **Ingress Filtering**: WasmEdge gateway validates all requests
3. **Egress Filtering**: Squid proxy with whitelist
4. **API Masking**: LiteLLM hides provider credentials
5. **ACL-Based Config**: Redis access controls per service

### 2. Least Privilege

Each service has minimal required permissions:

| Service | Access | Reason |
|---------|--------|--------|
| Gateway | Read config | Needs to validate requests |
| Agent | Write tasks/results | Processes tasks only |
| CLI | Read/write config/tasks | Management operations |
| LiteLLM | Read config | API routing only |

### 3. Immutable Infrastructure

- Configuration stored in Redis, not files
- Docker images versioned and signed
- Secrets in environment variables only

## Component Details

### WasmEdge Gateway (Rust)

**Responsibilities**:
- Request validation and sanitization
- Task submission to Redis queue
- Result retrieval
- Rate limiting (optional)

**Why Rust?**
- Memory safety - no buffer overflows
- Performance - low latency for request handling
- WasmEdge integration - sandboxing capabilities

**Design Patterns**:
- Repository pattern for Redis access
- Middleware for request validation
- Async/await for concurrent processing

### Agent Runtime (Python/LangChain)

**Responsibilities**:
- LangGraph agent execution
- LLM interactions through LiteLLM
- Task processing from Redis queue
- No direct network access

**Why Python?**
- Rich ML/AI ecosystem
- LangChain/LangGraph integration
- Easy development and debugging

**Design Patterns**:
- State pattern for agent states
- Queue consumer pattern
- Retry pattern with exponential backoff

### Redis (Config & Queue)

**Responsibilities**:
- Configuration storage
- Task queue
- Result storage
- Pub/Sub (optional for events)

**Security Hardening**:
- ACLs per user type
- Password authentication required
- Dangerous commands disabled
- AOF persistence (no RDB with secrets)

### Squid Proxy

**Responsibilities**:
- Egress filtering
- Whitelist enforcement
- No caching (security)
- Connection limiting

**Why Squid?**
- Mature, battle-tested
- Flexible ACLs
- Excellent logging

### LiteLLM Proxy

**Responsibilities**:
- API key masking
- Model routing
- Rate limiting
- Budget controls
- Failover handling

**Why LiteLLM?**
- Multi-provider support
- Built-in rate limiting
- Simple configuration

## Data Flow

### Request Flow

```
Client → Gateway (validate)
         ↓
       Redis (store task)
         ↓
       Agent (process)
         ↓
       Squid (filter egress)
         ↓
      LiteLLM (mask API)
         ↓
       Provider API
         ↓
       LiteLLM (response)
         ↓
       Agent (process)
         ↓
       Redis (store result)
         ↓
      Gateway (retrieve)
         ↓
       Client
```

### Task Creation Flow

1. **Client** sends HTTP POST to Gateway with task data
2. **Gateway** validates request and config
3. **Gateway** stores task in Redis as `task:{task_id}`
4. **Gateway** pushes task ID to Redis queue `agent:queue`
5. **Agent** polls queue via `BRPOP agent:queue`
6. **Agent** fetches task data from Redis
7. **Agent** processes task (LLM via LiteLLM proxy)
8. **Agent** stores result in Redis as `result:{task_id}`
9. **Client** polls Gateway (`GET /task/{task_id}`) for result

### Isolation Enforcement

1. **Gateway** has no access to internal Redis keys
2. **Agent** can only write to `agent:*`, `task:*`, `result:*`
3. **Agent** has no direct internet - must use proxy
4. **Proxy** only allows whitelisted domains
5. **LiteLLM** masks all provider API keys

## Threat Model

### Mitigated Threats

1. **Prompt Injection**
   - Input sanitization at gateway
   - LLM-level guardrails (configurable)

2. **Command Injection**
   - No command execution in agent
   - Rust memory safety in gateway

3. **Data Exfiltration**
   - Egress whitelist blocks unauthorized domains
   - No direct internet from agent

4. **Credential Theft**
   - API keys masked by LiteLLM
   - No credential storage in agent

5. **Configuration Tampering**
   - ACL-based Redis access
   - Config changes through CLI only

6. **Resource Exhaustion**
   - Memory limits on Redis
   - Connection timeouts
   - Budget limits on LiteLLM

### Remaining Considerations

1. **LLM-side vulnerabilities** - Use model-specific guardrails
2. **Social engineering** - User training and policies
3. **Supply chain attacks** - Image signing and verification
4. **Zero-day exploits** - Regular updates and monitoring

## Scalability

### Horizontal Scaling

- **Gateway**: Stateless, can run multiple instances
- **Agent**: Stateless, can run multiple instances
- **Redis**: Single instance (consider cluster for scale)
- **Squid/LiteLLM**: Single instance (consider load balancer)

### Performance Considerations

- Gateway latency: <10ms expected
- Agent processing: Model-dependent (500ms-30s)
- Queue depth: Monitor with health checks
- Redis memory: Monitor and increase as needed

## Monitoring

### Key Metrics

- Queue length (`agent:queue`)
- Task completion rate
- Error rate
- Average processing time
- Redis memory usage
- LiteLLM budget usage

### Logging Levels

- **ERROR**: Failures requiring attention
- **WARNING**: Recoverable issues
- **INFO**: Normal operations
- **DEBUG**: Detailed tracing (disabled in prod)

## Future Enhancements

1. **Authentication**: JWT-based client auth
2. **Encryption**: TLS for all internal traffic
3. **Audit Trail**: Immutable log of all operations
4. **Rate Limiting**: Per-client request limits
5. **Model Caching**: Cache common responses
6. **Multi-tenant**: Isolated queues per tenant
7. **Observability**: Prometheus metrics and Grafana dashboards
