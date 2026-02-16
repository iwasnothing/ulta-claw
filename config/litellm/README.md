# LiteLLM Configuration

## Overview

This directory contains the LiteLLM proxy configuration for API masking and management.

## Configuration File

`config.yaml` - Main configuration file containing:

- **Model List**: Supported LLM models and their API keys
- **Fallbacks**: Automatic failover configuration
- **Rate Limiting**: Budget and request limits
- **Security Settings**: Master key and database configuration
- **API Keys**: Internal keys for different services

## Security Notes

1. The `master_key` in `config.yaml` is loaded from environment variable `LITELM_MASTER_KEY`
2. Individual service keys (`agent_key_123`, `gateway_key_456`) are internal identifiers
3. All actual provider API keys are loaded from environment variables
4. The proxy validates and masks all requests before forwarding to providers

## Adding New Models

Add to `model_list` in `config.yaml`:

```yaml
- model_name: your-model-name
  litellm_params:
    model: provider/model-id
    api_key: os.environ/YOUR_API_KEY_ENV
```

## Budget Controls

Set budget limits to prevent overspending:

```yaml
max_budget: 100.0      # Maximum daily spend
budget_limit: 50.0     # Current available budget
```

## Monitoring

Access LiteLLM metrics at:
- http://localhost:4000/health
- http://localhost:4000/metrics (if configured)
