# Redis Configuration

## Overview

This directory contains the hardened Redis configuration with ACL-based access control.

## Files

- **redis.conf**: Main Redis configuration with security hardening
- **users.acl**: User access control definitions

## Security Features

1. **Password Protection**: All connections require password authentication
2. **ACLs**: Fine-grained permissions per user type
3. **Command Renaming**: Dangerous commands disabled (FLUSHDB, CONFIG, SHUTDOWN, etc.)
4. **Memory Limits**: 256MB max with LRU eviction
5. **AOF Persistence**: Every second sync (no sensitive data in RDB)

## User Types

| User | Password | Permissions | Purpose |
|------|----------|-------------|---------|
| admin | REDIS_ADMIN_PASSWORD | Full access | Administrative tasks |
| gateway | REDIS_GATEWAY_PASSWORD | Read config | Gateway reads configuration |
| agent | REDIS_AGENT_PASSWORD | Write agent:*, task:*, result:* | Agent runtime |
| cli | REDIS_CLI_PASSWORD | Read/write config, agent, task, result | CLI tool |
| litellm | REDIS_LITELM_PASSWORD | Read litellm:* | LiteLLM configuration |

## Key Patterns

- `config:*` - Configuration data
- `agent:*` - Agent-specific data
- `task:<id>` - Task definitions
- `result:<id>` - Task results
- `agent:queue` - Agent task queue

## Security Notes

1. Never expose Redis port publicly
2. Use strong, unique passwords for each user
3. Monitor Redis logs for suspicious activity
4. Regularly rotate passwords
5. Backup AOF file for disaster recovery
