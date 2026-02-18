//! Telegram adaptor for secure gateway.

use redis::{AsyncCommands, Client};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tracing::{debug, error, info, warn};
use uuid::Uuid;

/// Telegram bot token from environment
const TELEGRAM_API_BASE: &str = "https://api.telegram.org/bot";

/// Telegram update response
#[derive(Debug, Deserialize)]
struct TelegramUpdates {
    ok: bool,
    result: Vec<Update>,
}

/// Single Telegram update
#[derive(Debug, Deserialize)]
struct Update {
    #[serde(rename = "update_id")]
    update_id: i64,
    message: Option<Message>,
}

/// Telegram message
#[derive(Debug, Deserialize)]
struct Message {
    #[serde(rename = "message_id")]
    message_id: i64,
    #[serde(rename = "from")]
    from: Option<User>,
    #[serde(rename = "chat")]
    chat: Chat,
    #[serde(default)]
    text: String,
}

/// Telegram user
#[derive(Debug, Deserialize, Serialize)]
struct User {
    #[serde(rename = "id")]
    id: i64,
    #[serde(rename = "first_name")]
    first_name: String,
    #[serde(default)]
    #[serde(rename = "last_name")]
    last_name: String,
    #[serde(default)]
    username: String,
}

/// Telegram chat
#[derive(Debug, Deserialize, Serialize)]
struct Chat {
    #[serde(rename = "id")]
    id: i64,
    #[serde(rename = "type")]
    chat_type: String,
}

/// Telegram API response for sendMessage
#[derive(Debug, Serialize, Deserialize)]
struct TelegramResponse {
    ok: bool,
    result: Option<MessageResult>,
    description: Option<String>,
}

/// Result of sendMessage
#[derive(Debug, Deserialize, Serialize)]
struct MessageResult {
    #[serde(rename = "message_id")]
    message_id: i64,
    #[serde(rename = "from")]
    from: User,
    #[serde(rename = "chat")]
    chat: Chat,
    #[serde(default)]
    date: i64,
}

/// Payload for sendMessage
#[derive(Debug, Serialize)]
struct SendMessagePayload {
    #[serde(rename = "chat_id")]
    chat_id: i64,
    text: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[serde(rename = "parse_mode")]
    parse_mode: Option<String>,
}

/// Pending task awaiting agent response
struct PendingTask {
    chat_id: i64,
}

/// Telegram adaptor that polls for messages and handles responses
pub struct TelegramAdaptor {
    redis_client: Arc<Client>,
    bot_token: String,
    offset: i64,
    pending_tasks: Arc<tokio::sync::Mutex<std::collections::HashMap<String, PendingTask>>>,
}

impl TelegramAdaptor {
    /// Create a new Telegram adaptor
    pub fn new(redis_client: Arc<Client>, bot_token: String) -> Self {
        Self {
            redis_client,
            bot_token,
            offset: 0,
            pending_tasks: Arc::new(tokio::sync::Mutex::new(std::collections::HashMap::new())),
        }
    }

    /// Get updates from Telegram API
    async fn get_updates(&self) -> anyhow::Result<Vec<Update>> {
        let url = format!(
            "{}getUpdates?offset={}&timeout=30",
            self.get_base_url(),
            self.offset
        );

        debug!("Calling Telegram API: {}", &url);

        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(35))
            .build()?;

        let response = client.get(&url).send().await?;

        // Get response status and body for debugging
        let status = response.status();
        let body_text = response.text().await?;

        debug!("Telegram API response status: {}", status);
        debug!("Telegram API response body: {}", body_text);

        let updates: TelegramUpdates = serde_json::from_str(&body_text)?;

        if !updates.ok {
            return Err(anyhow::anyhow!("Telegram API returned ok=false: {}", body_text));
        }

        Ok(updates.result)
    }

    /// Send message to Telegram
    async fn send_message(&self, chat_id: i64, text: String) -> anyhow::Result<()> {
        let url = format!("{}sendMessage", self.get_base_url());
        let payload = SendMessagePayload {
            chat_id,
            text,
            parse_mode: None,
        };

        let client = reqwest::Client::new();
        let response = client
            .post(&url)
            .json(&payload)
            .send()
            .await?;

        let telegram_response: TelegramResponse = response.json().await?;

        if !telegram_response.ok {
            return Err(anyhow::anyhow!(format!(
                "Telegram sendMessage failed: {:?}",
                telegram_response.description
            )));
        }

        Ok(())
    }

    /// Get the base URL for Telegram API
    fn get_base_url(&self) -> String {
        format!("{}{}/", TELEGRAM_API_BASE, self.bot_token)
    }

    /// Create task in Redis for agent processing
    async fn create_task(
        &self,
        message: &Message,
    ) -> anyhow::Result<String> {
        let task_id = Uuid::new_v4().to_string();

        // Store pending task info
        let pending = PendingTask {
            chat_id: message.chat.id,
        };
        self.pending_tasks
            .lock()
            .await
            .insert(task_id.clone(), pending);

        // Create task in Redis with Telegram metadata
        let task_key = format!("task:{}", task_id);
        let task_value = serde_json::to_string(&serde_json::json!({
            "input": message.text.clone(),
            "config": {
                "telegram_chat_id": message.chat.id,
                "telegram_message_id": message.message_id,
                "telegram_user_id": message.from.as_ref().map(|u| u.id),
                "telegram_username": message.from.as_ref().map(|u| u.username.clone()).filter(|s| !s.is_empty()),
            },
            "status": "pending",
            "created_at": chrono::Utc::now().to_rfc3339(),
        }))?;

        let mut conn = self.redis_client.get_async_connection().await?;
        conn.set::<_, _, ()>(&task_key, task_value).await?;

        // Push to agent queue
        conn.lpush::<_, _, ()>("agent:queue", &task_id).await?;

        info!("Created task {} for Telegram chat {}", task_id, message.chat.id);

        Ok(task_id)
    }

    /// Check for agent response and send to Telegram
    async fn check_and_send_responses(&self) -> anyhow::Result<()> {
        let pending = self.pending_tasks.lock().await;
        let task_ids: Vec<String> = pending.keys().cloned().collect();
        drop(pending);

        for task_id in task_ids {
            let result_key = format!("result:{}", task_id);

            let mut conn = self.redis_client.get_async_connection().await?;

            if let Some(result_json) = conn.get::<_, String>(&result_key).await.ok() {
                let result: serde_json::Value = serde_json::from_str(&result_json)?;

                // Get the result text
                if let Some(result_text) = result.get("result").and_then(|r| r.as_str()) {
                    // Get the pending task info
                    let pending = self.pending_tasks.lock().await;
                    if let Some(task) = pending.get(&task_id) {
                        let chat_id = task.chat_id;
                        drop(pending);

                        // Send response to Telegram
                        if let Err(e) = self.send_message(chat_id, result_text.to_string()).await {
                            error!("Failed to send message to Telegram: {}", e);
                        } else {
                            info!("Sent response to Telegram chat {}", chat_id);

                            // Remove from pending tasks
                            self.pending_tasks.lock().await.remove(&task_id);

                            // Clean up result from Redis
                            let _: Result<i64, _> = conn.del(&result_key).await;
                        }
                    } else {
                        drop(pending);
                    }
                }
            }
        }

        Ok(())
    }

    /// Run the adaptor loop
    pub async fn run(&mut self) -> anyhow::Result<()> {
        info!("Telegram adaptor started");

        loop {
            match self.run_once().await {
                Ok(_) => {}
                Err(e) => {
                    error!("Error in Telegram adaptor loop: {}", e);
                }
            }

            // Sleep 15 seconds if no messages
            tokio::time::sleep(tokio::time::Duration::from_secs(15)).await;
        }
    }

    /// Run one iteration of the adaptor loop
    async fn run_once(&mut self) -> anyhow::Result<bool> {
        // Check for agent responses and send to Telegram
        if let Err(e) = self.check_and_send_responses().await {
            warn!("Failed to check responses: {}", e);
        }

        // Get updates from Telegram
        let updates = self.get_updates().await?;

        if updates.is_empty() {
            debug!("No new Telegram messages");
            return Ok(false);
        }

        info!("Received {} Telegram updates", updates.len());

        for update in updates {
            // Update offset to mark this update as processed
            self.offset = update.update_id + 1;

            if let Some(message) = update.message {
                if !message.text.is_empty() {
                    // Create task for agent processing
                    if let Err(e) = self.create_task(&message).await {
                        error!("Failed to create task: {}", e);
                    }
                }
            }
        }

        Ok(true)
    }
}

/// Start the Telegram adaptor in a background task
pub fn start_telegram_adaptor(redis_client: Arc<Client>) {
    let bot_token = std::env::var("TELEGRAM_BOT_TOKEN")
        .expect("TELEGRAM_BOT_TOKEN must be set");

    tokio::spawn(async move {
        let mut adaptor = TelegramAdaptor::new(redis_client, bot_token);
        if let Err(e) = adaptor.run().await {
            error!("Telegram adaptor crashed: {}", e);
        }
    });
}
