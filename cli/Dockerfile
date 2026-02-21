FROM node:18-alpine AS frontend-builder

# Set working directory
WORKDIR /app/frontend

# Copy frontend files
COPY frontend/package*.json ./
RUN npm install

COPY frontend/tsconfig.json frontend/next.config.js frontend/tailwind.config.ts frontend/postcss.config.js ./
COPY frontend/app ./app
COPY frontend/public ./public

# Build Next.js app
RUN npm run build

# Use Python image with Node.js installed
FROM python:3.11-slim

# Install Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    redis-tools \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install FastAPI and uvicorn
RUN pip install --no-cache-dir fastapi uvicorn[standard]

# Copy API and CLI source code
COPY api/ ./api/
COPY cli/ ./cli/

# Copy built frontend from previous stage
COPY --from=frontend-builder /app/frontend/.next/standalone ./
COPY --from=frontend-builder /app/frontend/.next/static ./.next/static
COPY --from=frontend-builder /app/frontend/public ./public

# Copy API source
COPY api ./api

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Start FastAPI backend in background\n\
echo "Starting FastAPI backend on port 8888..."\n\
cd /app && python -m uvicorn api.main:app --host 0.0.0.0 --port 8888 &\n\
FASTAPI_PID=$!\n\
\n\
# Wait a moment for backend to start\n\
sleep 2\n\
\n\
# Start Next.js frontend\n\
echo "Starting Next.js frontend on port 3000..."\n\
NODE_ENV=production node server.js &\n\
NEXTJS_PID=$!\n\
\n\
# Wait for both processes\n\
wait $FASTAPI_PID $NEXTJS_PID' \
    > /usr/local/bin/entrypoint.sh && \
    chmod +x /usr/local/bin/entrypoint.sh

# Set default environment variables
ENV REDIS_HOST=redis
ENV REDIS_PORT=6379
ENV GATEWAY_URL=http://gateway:8080
ENV LITELM_URL=http://litellm:4000
ENV SQUID_HOST=squid
ENV SQUID_PORT=3128
ENV NODE_ENV=production
ENV NEXT_PUBLIC_API_BASE_URL=http://localhost:8888

# Expose ports
EXPOSE 3000 8888

# Set the default command
CMD ["/usr/local/bin/entrypoint.sh"]
