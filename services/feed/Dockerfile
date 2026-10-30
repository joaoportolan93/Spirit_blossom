# Rust multi-stage — target: aarch64-unknown-linux-gnu (Oracle ARM)
# Nota: build cruzado em x86 requer configuração adicional de toolchain.
# Em CI ARM64 nativo, remover o target explícito.

FROM rust:1.77-slim AS builder

# Dependências de sistema para compilação cruzada e curl (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cache de dependências: copiar manifests antes do fonte
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo 'fn main() {}' > src/main.rs
RUN cargo build --release
RUN rm src/main.rs

# Build real
COPY src ./src
RUN touch src/main.rs && cargo build --release

# Imagem de runtime mínima
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
  && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/feed-service /usr/local/bin/feed-service

ENV FEED_PORT=3000
EXPOSE 3000

CMD ["feed-service"]

