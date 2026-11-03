#![allow(dead_code)]

use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Motivo pelo qual um post aparece no feed.
/// Neutro de produto — não contém nome de marca.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum FeedReason {
    /// Post de alguém que o usuário segue.
    Following,
    /// Post em destaque no algoritmo (Fase 1+).
    Recommended,
    /// Post fixado no topo do perfil.
    Pinned,
}

/// Um item individual retornado pelo serviço de feed.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FeedItem {
    /// Identificador do post (UUID7 gerado pelo backend Django).
    pub post_id: Uuid,
    /// Motivo de exibição.
    pub reason: FeedReason,
    /// Cursor opaco para paginação keyset. None no último item.
    pub cursor: Option<String>,
}

/// Resposta completa do endpoint de feed.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FeedResponse {
    pub items: Vec<FeedItem>,
    /// Cursor para a próxima página. None quando não há mais itens.
    pub next_cursor: Option<String>,
}
