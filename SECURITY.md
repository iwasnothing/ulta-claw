# Security Guide

## Overview

This document provides comprehensive security guidelines for deploying and operating Secure Agent Architecture.

## Pre-Deployment Security Checklist

### 1. Credentials

- [ ] Change all default passwords in `.env`
- [ ] Use strong, unique passwords (minimum 32 characters)
- [ ] Rotate passwords regularly (90 days recommended)
- [ ] Store `.env` securely (not in git)
- [ ] Use secrets management in production (Vault, AWS Secrets Manager, etc.)

### 2. Network Configuration

- [ ] Verify agent cannot access internet directly
- [ ] Confirm all traffic goes through Squid proxy
- [ ] Review and minimize whitelist domains
- [ ] Enable firewall rules on host
- [ ] Use private networks for internal communication

### 3. Access Control

- [ ] Verify Redis ACLs are enforced
- [ ] Test each user role's permissions
- [ ] Remove unused users/permissions
- [ ] Implement audit logging

### 4. Container Security

- [ ] Use non-root users in containers
- [ ] Scan images for vulnerabilities
- [ ] Keep images updated
- [ ] Minimize container privileges

### 5. LLM Security

- [ ] Configure provider-side guardrails
- [ ] Set appropriate budget limits
- [ ] Enable provider audit logging
- [ ] Monitor for abuse patterns

## Operational Security

### 1. Monitoring

#### Key Alerts

- Redis connection failures
- Gateway health check failures
- Agent queue backlog (>100 tasks)
- Rate limit exceeded
- Unauthorized access attempts

#### Log Retention

- Access logs: 90 days
- Application logs: 30 days
- Error logs: 365 days
- Audit logs: 7 years (compliance)

### 2. Incident Response

#### Detection

1. Monitor logs for suspicious activity
2. Check queue backlog
3. Review API usage patterns
4. Monitor budget consumption

#### Response Steps

1. Isolate affected component
2. Preserve logs for analysis
3. Rotate credentials
4. Patch vulnerabilities
5. Document incident
6. Post-mortem analysis

### 3. Backup & Recovery

#### What to Backup

- Redis AOF file
- Environment configuration (separately from secrets)
- Whitelist configurations
- LiteLLM configuration

#### Backup Strategy

- Daily automated backups
- Offsite storage
- Encrypted backups
- Regular restore testing

## Hardening Guide

### 1. Redis Hardening

```bash
# Enable only necessary commands
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG ""
rename-command SHUTDOWN ""

# Set max memory
maxmemory 256mb
maxmemory-policy allkeys-lru

# Enable persistence
appendonly yes
```

### 2. Squid Hardening

```bash
# Deny all by default
http_access deny all

# Whitelist approach
acl whitelist dstdomain "/etc/squid/whitelist.txt"
http_access allow whitelist
```

### 3. Gateway Hardening

- Enable request rate limiting
- Implement request size limits
- Add input validation
- Enable CORS only for authorized origins

### 4. Agent Hardening

- No direct file system access
- No command execution
- Limited Python modules
- Sandboxed execution environment

## Penetration Testing

### Test Areas

1. **Network Isolation**
   - Can agent bypass proxy?
   - Can agent reach non-whitelisted domains?

2. **Ingress Filtering**
   - Can malformed requests crash gateway?
   - Can buffer overflows be exploited?

3. **Access Control**
   - Can unauthorized users access Redis?
   - Can agent access config it shouldn't?

4. **Data Exfiltration**
   - Can exfiltrate data to non-whitelisted domains?
   - Can steal API keys?

5. **Prompt Injection**
   - Can prompts cause unauthorized actions?
   - Can agent be tricked into revealing data?

### Test Tools

- Burp Suite (web testing)
- OWASP ZAP (vulnerability scanning)
- Nmap (port scanning)
- Redis-cli (ACL testing)
- Custom test scripts

## Compliance

### GDPR Considerations

- Data minimization in prompts
- Right to be forgotten (clear Redis)
- Data processing agreements with LLM providers

### SOC 2 Considerations

- Access logging and monitoring
- Change management procedures
- Incident response processes
- Regular security reviews

### HIPAA Considerations

- Data encryption at rest and in transit
- Business associate agreements
- Audit trail maintenance

## Security Best Practices

### Development

1. Never commit secrets to git
2. Use `.env.example` with safe defaults
3. Implement security tests in CI/CD
4. Code review all changes
5. Regular dependency updates

### Deployment

1. Use signed images
2. Enable TLS everywhere
3. Implement health checks
4. Use secrets management
5. Enable audit logging

### Operations

1. Monitor security advisories
2. Regular vulnerability scanning
3. Penetration testing
4. Security training for operators
5. Incident response drills

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [Redis Security](https://redis.io/topics/security)

## Contact

For security questions or to report vulnerabilities:
- Email: security@example.com
- PGP Key: [to be added]
