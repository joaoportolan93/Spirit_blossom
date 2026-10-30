mod types;

use axum::{routing::get, Json, Router};
use serde_json::{json, Value};
use std::net::SocketAddr;
use tracing::info;

/// GET /health — verifica que o serviço está vivo.
/// Stub M0: nenhuma lógica de ranking ou acesso ao banco.
async fn health() -> Json<Value> {
    Json(json!({
        "status": "ok",
        "service": "feed-service",
        "version": env!("CARGO_PKG_VERSION"),
    }))
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            std::env::var("RUST_LOG")
                .unwrap_or_else(|_| "info".to_string()),
        )
        .init();

    let port: u16 = std::env::var("FEED_PORT")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(3000);

    let app = Router::new().route("/health", get(health));

    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    info!("feed-service ouvindo em {addr}");

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

