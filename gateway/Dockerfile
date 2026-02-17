# Build stage
FROM --platform=linux/arm64 rust:1.88-bookworm AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config libssl-dev curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Detect architecture for WasmEdge installation
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "aarch64" ]; then \
        ARCH_NAME="aarch64"; \
    elif [ "$ARCH" = "x86_64" ]; then \
        ARCH_NAME="amd64"; \
    else \
        echo "Unsupported architecture: $ARCH"; \
        exit 1; \
    fi && \
    echo "Detected architecture: $ARCH_NAME" && \
    curl -sSf https://raw.githubusercontent.com/WasmEdge/WasmEdge/master/utils/install.sh | bash -s -- -v 0.13.5 -p $ARCH_NAME

# Set WasmEdge environment variables
ENV PATH="/root/.wasmedge/bin:${PATH}"
ENV WASMEDGE_DIR="/root/.wasmedge"
ENV LD_LIBRARY_PATH="/root/.wasmedge/lib:${LD_LIBRARY_PATH}"

# Copy source
COPY Cargo.toml ./
COPY src ./src

# Build
RUN cargo build --release

# Runtime stage
FROM --platform=linux/arm64 debian:bookworm-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates tzdata libgcc1 \
    && rm -rf /var/lib/apt/lists/*

# Copy WasmEdge from builder
COPY --from=builder /root/.wasmedge /root/.wasmedge

# Set environment for WasmEdge libraries
ENV PATH="/root/.wasmedge/bin:${PATH}"
ENV LD_LIBRARY_PATH="/root/.wasmedge/lib:${LD_LIBRARY_PATH}"

WORKDIR /app

# Copy binary
COPY --from=builder /app/target/release/secure-gateway /app/secure-gateway

# Run
EXPOSE 8080
CMD ["/app/secure-gateway"]
