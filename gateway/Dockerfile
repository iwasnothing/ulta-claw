# Build stage
FROM rust:1.75-alpine AS builder

WORKDIR /app

# Install build dependencies
RUN apk add --no-cache musl-dev pkgconfig openssl-dev

# Copy source
COPY Cargo.toml ./
COPY src ./src

# Build
RUN cargo build --release

# Runtime stage
FROM alpine:3.19

# Install runtime dependencies
RUN apk add --no-cache ca-certificates tzdata

WORKDIR /app

# Copy binary
COPY --from=builder /app/target/release/secure-gateway /app/secure-gateway

# Run
EXPOSE 8080
CMD ["/app/secure-gateway"]
