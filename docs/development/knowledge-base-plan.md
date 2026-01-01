# Knowledge Base Integration Plan (Qdrant)

This document outlines the strategy for integrating a user-specific knowledge base into the AI Gateway project, enabling long-term memory and RAG (Retrieval-Augmented Generation) capabilities.

## 1. Architectural Decision

**Chosen Engine:** **Qdrant**

### Why Qdrant?
*   **Performance vs. Resources:** Written in Rust, it provides high performance with minimal memory footprint (can run on <256MB RAM), unlike JVM-based solutions like OpenSearch which are resource-heavy.
*   **AI-Native:** Designed specifically for vector search with first-class support for payload filtering (HNSW + Filter).
*   **Go Support:** Excellent official Go SDK with gRPC support for type-safe, high-performance communication.
*   **Multi-tenancy:** Efficient handling of multi-user data via single-collection payload filtering rather than creating separate indices/tables per user.

### Rejected Alternatives
*   **OpenSearch:** Too heavy (JVM based), excessive resource consumption for the current project scale, high maintenance complexity.
*   **PostgreSQL + pgvector:** A viable "all-in-one" alternative, but Qdrant offers specialized performance and features for vector operations that align better with an "AI Native" architecture.

## 2. Integration Strategy: "Core Service + Adapter"

We will adopt a layered architecture to maximize flexibility and user experience.

### Core Layer (Go Backend)
*   **KnowledgeService:** A dedicated service module in the Go backend.
*   **Responsibilities:**
    *   Managing Qdrant connection (gRPC).
    *   **Ingest:** Converting text to embeddings and storing them with metadata.
    *   **Search:** Performing semantic search with strict `user_id` filtering.

### Adapter Layer
1.  **Native Integration (Internal API):**
    *   **Purpose:** Powers the Gateway's own web interface.
    *   **UX:** Enables rich UI elements like "Glassmorphism" cards for citations, source tracking, and interactive feedback loops.
    *   **Flow:** Web UI -> Gateway API -> KnowledgeService -> Qdrant.

2.  **MCP Server (External Interface):**
    *   **Purpose:** Allows external AI tools (Cursor, Claude Desktop) to access the user's knowledge base.
    *   **Mechanism:** The Gateway acts as an MCP Host/Server.
    *   **Flow:** Cursor/Claude -> MCP Protocol -> Gateway Auth -> KnowledgeService -> Qdrant.

## 3. Implementation Details

### 3.1 Deployment (Docker)
Lightweight deployment alongside the gateway.

```bash
docker run -p 6333:6333 -p 6334:6334 \
    -v $(pwd)/qdrant_storage:/qdrant/storage \
    qdrant/qdrant
```

- Port `6333`: HTTP API
- Port `6334`: gRPC API (Used by Go backend)

### 3.2 Data Model
We will use a **Single Collection** strategy with **Payload Filtering** for multi-tenancy.

*   **Collection Name:** `gateway_memory`
*   **Vector Config:** 1536 dimensions (compatible with OpenAI `text-embedding-3-small` or similar).
*   **Distance Metric:** Cosine Similarity.

**Payload Structure (Metadata):**
```json
{
  "user_id": "user_123_uuid",
  "content": "Original text chunk...",
  "type": "chat_history",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### 3.3 Go Implementation Strategy (gRPC)

**Dependencies:**
`go get github.com/qdrant/go-client`

**Key Logic:**
1.  **Connection:** Establish gRPC connection to `:6334`.
2.  **Ingestion (Add Memory):**
    *   Generate embedding for text.
    *   Create a Point with a UUID.
    *   Attach `user_id` in the Payload.
    *   `Upsert` to Qdrant.
3.  **Retrieval (Search Memory):**
    *   Generate embedding for query.
    *   Create a `Filter` condition: `Must match key="user_id", value=currentUserID`.
    *   `Search` with vector + filter.

## 4. Roadmap

1.  **Phase 1: Core & Native Integration (Day 1-7)**
    *   Set up Qdrant Docker container.
    *   Implement `KnowledgeService` in Go.
    *   Integrate RAG flow into the main chat completion logic.
    *   Update Web UI to display retrieved context.

2.  **Phase 2: MCP Interface (Day 8-10)**
    *   Implement MCP protocol handlers in the Gateway.
    *   Expose `search_knowledge_base` as an MCP Tool.
    *   Validate connectivity with Cursor/Claude Desktop.

3.  **Phase 3: Launch**
    *   Roll out "Personal Memory" feature.
    *   Provide documentation for users to connect their external tools via MCP.

