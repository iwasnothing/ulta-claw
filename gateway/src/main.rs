use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::Json,
    routing::{get, post},
    Router,
};
use redis::{AsyncCommands, Client};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::net::TcpListener;
use tower_http::cors::CorsLayer;
use tracing::{error, info};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod telegram;

// Configuration
#[derive(Clone)]
struct AppState {
    redis_client: Arc<Client>,
}

// Request/Response types
#[derive(Debug, Deserialize)]
struct AgentRequest {
    task_id: String,
    input: serde_json::Value,
    config: Option<serde_json::Value>,
}

#[derive(Debug, Serialize)]
struct AgentResponse {
    task_id: String,
    status: String,
    result: Option<serde_json::Value>,
    error: Option<String>,
}

#[derive(Debug, Serialize)]
struct HealthResponse {
    status: String,
    redis: bool,
}

// Health check endpoint
async fn health_check(State(state): State<AppState>) -> Json<HealthResponse> {
    let redis_status = check_redis_connection(&state.redis_client).await;
    Json(HealthResponse {
        status: if redis_status { "healthy".to_string() } else { "degraded".to_string() },
        redis: redis_status,
    })
}

// Submit task to agent
async fn submit_task(
    State(state): State<AppState>,
    Json(req): Json<AgentRequest>,
) -> Result<Json<AgentResponse>, StatusCode> {
    // Validate request
    if let Err(e) = validate_request(&req).await {
        error!("Request validation failed: {}", e);
        return Err(StatusCode::BAD_REQUEST);
    }

    // Get config from Redis
    let config = match get_config(&state.redis_client, &req.config).await {
        Ok(cfg) => cfg,
        Err(e) => {
            error!("Failed to get config: {}", e);
            return Err(StatusCode::INTERNAL_SERVER_ERROR);
        }
    };

    // Create task in Redis
    let task_key = format!("task:{}", req.task_id);
    let task_value = serde_json::to_string(&serde_json::json!({
        "input": req.input,
        "config": config,
        "status": "pending",
        "created_at": chrono::Utc::now().to_rfc3339(),
    }))
    .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    let mut conn = state
        .redis_client
        .get_async_connection()
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    conn.set::<_, _, ()>(&task_key, task_value)
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Push to agent queue
    conn.lpush::<_, _, ()>("agent:queue", req.task_id.clone())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    info!("Task {} submitted", req.task_id);

    Ok(Json(AgentResponse {
        task_id: req.task_id,
        status: "submitted".to_string(),
        result: None,
        error: None,
    }))
}

// Get task result
async fn get_result(
    State(state): State<AppState>,
    Path(task_id): Path<String>,
) -> Result<Json<AgentResponse>, StatusCode> {
    let result_key = format!("result:{}", task_id);
    let task_key = format!("task:{}", task_id);

    let mut conn = state
        .redis_client
        .get_async_connection()
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    // Check if result exists
    if let Some(result) = conn.get::<_, String>(&result_key).await.ok() {
        let value: serde_json::Value =
            serde_json::from_str(&result).map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        return Ok(Json(AgentResponse {
            task_id,
            status: "completed".to_string(),
            result: Some(value),
            error: None,
        }));
    }

    // Check if task exists
    if let Some(task) = conn.get::<_, String>(&task_key).await.ok() {
        let value: serde_json::Value =
            serde_json::from_str(&task).map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        let status = value["status"].as_str().unwrap_or("unknown").to_string();
        return Ok(Json(AgentResponse {
            task_id,
            status,
            result: None,
            error: None,
        }));
    }

    Err(StatusCode::NOT_FOUND)
}

// Helper functions
async fn check_redis_connection(redis_client: &Client) -> bool {
    match redis_client.get_async_connection().await {
        Ok(mut conn) => redis::cmd("PING").query_async::<_, String>(&mut conn).await.is_ok(),
        Err(_) => false,
    }
}

async fn validate_request(req: &AgentRequest) -> Result<(), String> {
    // Validate task_id format
    if req.task_id.is_empty() {
        return Err("task_id cannot be empty".to_string());
    }

    // Validate input
    if req.input.is_null() {
        return Err("input cannot be null".to_string());
    }

    Ok(())
}

async fn get_config(
    redis_client: &Client,
    user_config: &Option<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    let mut conn = redis_client
        .get_async_connection()
        .await
        .map_err(|e| format!("Redis connection error: {}", e))?;

    // Get default config
    let default_config: String = conn
        .get("config:default")
        .await
        .unwrap_or_else(|_| "{}".to_string());
    let mut config: serde_json::Value =
        serde_json::from_str(&default_config).unwrap_or_else(|_| serde_json::json!({}));

    // Merge with user config
    if let Some(user_cfg) = user_config {
        merge_json(&mut config, user_cfg);
    }

    Ok(config)
}

fn merge_json(target: &mut serde_json::Value, source: &serde_json::Value) {
    if let (Some(t_obj), Some(s_obj)) = (target.as_object_mut(), source.as_object()) {
        for (key, value) in s_obj {
            if t_obj.contains_key(key) {
                if t_obj[key].is_object() && value.is_object() {
                    merge_json(&mut t_obj[key], value);
                } else {
                    t_obj[key] = value.clone();
                }
            }
        }
    }
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize tracing
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "secure_gateway=debug,tower_http=debug".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    // Load environment variables
    let redis_host = std::env::var("REDIS_HOST").unwrap_or_else(|_| "redis".to_string());
    let redis_port = std::env::var("REDIS_PORT").unwrap_or_else(|_| "6379".to_string());
    let redis_password = std::env::var("REDIS_PASSWORD").unwrap_or_else(|_| "default".to_string());
    let telegram_bot_token = std::env::var("TELEGRAM_BOT_TOKEN").ok();

    // Create Redis client
    let redis_url = format!(
        "redis://:{}@{}:{}",
        redis_password, redis_host, redis_port
    );
    let redis_client = Arc::new(Client::open(redis_url)?);

    // Start Telegram adaptor if bot token is provided
    if let Some(_) = telegram_bot_token {
        info!("Starting Telegram adaptor");
        telegram::start_telegram_adaptor(redis_client.clone());
    } else {
        info!("TELEGRAM_BOT_TOKEN not set, Telegram adaptor disabled");
    }

    // Create app state
    let state = AppState { redis_client };

    // Build router
    let app = Router::new()
        .route("/health", get(health_check))
        .route("/task", post(submit_task))
        .route("/task/:task_id", get(get_result))
        .layer(CorsLayer::permissive())
        .with_state(state);

    // Start server
    let listener = TcpListener::bind("0.0.0.0:8080").await?;
    info!("Secure Gateway listening on 0.0.0.0:8080");

    axum::serve(listener, app).await?;

    Ok(())
}
