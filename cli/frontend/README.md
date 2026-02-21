# Secure Agent Health Check UI

A Next.js-based web interface for monitoring the health status of the Secure Agent Architecture.

## Development

To run the frontend in development mode:

```bash
cd cli/frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:3000`.

## Production

The production build is handled by the Docker container. The Dockerfile:
1. Builds the Next.js app in standalone mode
2. Serves it using the Next.js standalone server
3. Runs the FastAPI backend on port 8888

## Environment Variables

- `NEXT_PUBLIC_API_BASE_URL`: URL of the FastAPI backend (default: `http://localhost:8888`)
- `NODE_ENV`: Node environment (default: `production`)

## Features

- Real-time health monitoring of all system components
- Auto-refresh every 3 seconds (toggleable)
- Detailed status for each component
- Response time tracking
- Modal for viewing detailed component information

## Components Monitored

- Gateway
- Adaptor Channel
- Agent
- Redis
- LiteLLM
- Squid
- Network Connections
