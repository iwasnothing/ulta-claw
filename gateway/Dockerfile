# Build stage
FROM rust:1.88-bookworm AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config libssl-dev curl ca-certificates clang libclang-dev \
    wget && rm -rf /var/lib/apt/lists/*

# Install WasmEdge Runtime (0.13.5 to match wasmedge-sdk 0.13)
RUN wget -qO- https://raw.githubusercontent.com/WasmEdge/WasmEdge/master/utils/install.sh | \
    bash -s -- -v 0.13.5 -D && \
    rm -rf /root/.wasmedge/share/wasmedge/examples

# Set WasmEdge environment variables for build
ENV PATH="/root/.wasmedge/bin:${PATH}"
ENV WASMEDGE_DIR="/root/.wasmedge"
ENV WASMEDGE_INCLUDE_DIR="/root/.wasmedge/include"
ENV WASMEDGE_LIB_DIR="/root/.wasmedge/lib"
ENV LD_LIBRARY_PATH="/root/.wasmedge/lib"

# Copy source
COPY Cargo.toml ./
COPY src ./src

# Set clang include path for bindgen
RUN export CLANG_INCLUDE_PATH=$(find /usr/lib/clang -name "include" -type d | head -n 1) && \
    export BINDGEN_EXTRA_CLANG_ARGS="-I${CLANG_INCLUDE_PATH}" && \
    cargo build --release

# Runtime stage
FROM debian:bookworm-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates tzdata libgcc1 libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# Copy WasmEdge from builder
COPY --from=builder /root/.wasmedge /root/.wasmedge

# Set environment for WasmEdge libraries
ENV PATH="/root/.wasmedge/bin:${PATH}"
ENV WASMEDGE_DIR="/root/.wasmedge"
ENV LD_LIBRARY_PATH="/root/.wasmedge/lib"

WORKDIR /app

# Copy binary
COPY --from=builder /app/target/release/secure-gateway /app/secure-gateway

# Run
EXPOSE 8080
CMD ["/app/secure-gateway"]
