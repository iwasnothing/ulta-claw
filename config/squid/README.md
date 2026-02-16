# Squid Proxy Configuration

## Overview

This directory contains the Squid proxy configuration for egress filtering and network isolation.

## Files

- **squid.conf**: Main Squid configuration with security settings
- **whitelist.txt**: Allowed domains for agent egress

## Security Features

1. **Whitelist-only Access**: Only domains in whitelist.txt are accessible
2. **No Caching**: All caching disabled for security
3. **No Disk Storage**: `cache_dir null` - nothing written to disk
4. **Anonymization**: `forwarded_for delete` - hides client identity
5. **Connection Limits**: Timeouts prevent hanging connections

## Whitelist Format

Add domains to `whitelist.txt`:

```
api.openai.com
api.anthropic.com
api.mistral.ai
```

## Network Zones

- **ingress-net**: Gateway traffic only
- **secure-net**: Internal communication
- **agent-net**: Agent runtime
- **egress-net**: Squid proxy to internet

## Security Guidelines

1. Keep whitelist minimal - only add required domains
2. Review whitelist regularly
3. Monitor access logs for blocked requests
4. Use specific domains (subdomains), not wildcards
5. Test whitelist changes before deploying

## Adding Domains

1. Edit `whitelist.txt`
2. Add domain (one per line)
3. Restart Squid: `docker-compose restart squid`
4. Test: `docker-compose exec agent curl -v https://new-domain.com`

## Logs

View Squid access logs:

```bash
docker-compose logs squid
```

Or inside container:

```bash
docker-compose exec squid tail -f /var/log/squid/access.log
```
