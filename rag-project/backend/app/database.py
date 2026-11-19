from contextlib import asynccontextmanager

import asyncpg


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    role text NOT NULL CHECK (role IN ('admin', 'user'))
);

CREATE TABLE IF NOT EXISTS login_sessions (
    token_hash bytea PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS login_sessions_expiry ON login_sessions(expires_at);

CREATE TABLE IF NOT EXISTS conversations (
    id uuid PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title text NOT NULL DEFAULT '새 채팅',
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS conversations_user_updated ON conversations(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('user', 'assistant')),
    content text NOT NULL,
    sources jsonb NOT NULL DEFAULT '[]',
    interrupted boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS messages_conversation_id ON messages(conversation_id, id);

CREATE TABLE IF NOT EXISTS pdf_documents (
    id uuid PRIMARY KEY,
    filename text NOT NULL UNIQUE,
    collection text NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    status text NOT NULL CHECK (status IN ('indexing', 'ready', 'deleting')),
    legacy boolean NOT NULL DEFAULT false,
    uploaded_at timestamptz NOT NULL DEFAULT now(),
    uploaded_by bigint REFERENCES users(id) ON DELETE SET NULL,
    chunk_count integer CHECK (chunk_count >= 0)
);
"""


async def initialize(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute("SELECT pg_advisory_xact_lock(81347601)")
        await connection.execute(SCHEMA)


@asynccontextmanager
async def operation(pool: asyncpg.Pool, key: str):
    """Serialize requests that update the same document or conversation."""
    async with pool.acquire() as connection:
        acquired = await connection.fetchval("SELECT pg_try_advisory_lock(hashtextextended($1, 0))", key)
        try:
            yield connection if acquired else None
        finally:
            if acquired:
                await connection.execute("SELECT pg_advisory_unlock(hashtextextended($1, 0))", key)
