BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> ace48b94f7c9

CREATE TABLE interactions (
    id UUID NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources JSONB NOT NULL,
    latency_ms FLOAT NOT NULL,
    model_used VARCHAR(100) NOT NULL,
    cache_hit BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id)
);

CREATE INDEX ix_interactions_created_at ON interactions (created_at);

CREATE TABLE feedback (
    id UUID NOT NULL,
    interaction_id UUID NOT NULL,
    rating INTEGER NOT NULL,
    comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_feedback_rating CHECK (rating IN (-1, 1)),
    FOREIGN KEY(interaction_id) REFERENCES interactions (id) ON DELETE CASCADE,
    UNIQUE (interaction_id)
);

INSERT INTO alembic_version (version_num) VALUES ('ace48b94f7c9') RETURNING alembic_version.version_num;

-- Running upgrade ace48b94f7c9 -> b72e9c41a603

CREATE TABLE documents (
    id UUID NOT NULL,
    owner_id VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    size_bytes INTEGER NOT NULL,
    content BYTEA NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_document_owner_hash_mime UNIQUE (owner_id, sha256, mime_type)
);

CREATE INDEX ix_documents_owner_id ON documents (owner_id);

CREATE TABLE document_chunks (
    id UUID NOT NULL,
    document_id UUID NOT NULL,
    position INTEGER NOT NULL,
    section VARCHAR(100) NOT NULL,
    content TEXT NOT NULL,
    embedding_model VARCHAR(100) NOT NULL,
    embedding JSON NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_chunk_model_position UNIQUE (document_id, embedding_model, position),
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE
);

CREATE INDEX ix_document_chunks_document_id ON document_chunks (document_id);

ALTER TABLE interactions ADD COLUMN owner_id VARCHAR(100) DEFAULT 'local' NOT NULL;

ALTER TABLE interactions ADD COLUMN document_id UUID;

ALTER TABLE interactions ADD COLUMN cache_key VARCHAR(64);

ALTER TABLE interactions ADD COLUMN mode VARCHAR(10) DEFAULT 'direct' NOT NULL;

ALTER TABLE interactions ADD COLUMN input_tokens INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE interactions ADD COLUMN output_tokens INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE interactions ADD CONSTRAINT fk_interactions_document_id FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE SET NULL;

CREATE INDEX ix_interactions_owner_id ON interactions (owner_id);

CREATE INDEX ix_interactions_document_id ON interactions (document_id);

CREATE INDEX ix_interactions_cache_key ON interactions (cache_key);

UPDATE alembic_version SET version_num='b72e9c41a603' WHERE alembic_version.version_num = 'ace48b94f7c9';

-- Running upgrade b72e9c41a603 -> c83f0d52b714

CREATE TABLE conversations (
    id UUID NOT NULL,
    owner_id VARCHAR(100) NOT NULL,
    document_id UUID,
    title VARCHAR(200) NOT NULL,
    version INTEGER DEFAULT '0' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE SET NULL
);

CREATE INDEX ix_conversations_owner_id ON conversations (owner_id);

ALTER TABLE interactions ADD COLUMN conversation_id UUID;

ALTER TABLE interactions ADD COLUMN turn_number INTEGER;

ALTER TABLE interactions ADD CONSTRAINT fk_interactions_conversation FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE SET NULL;

CREATE INDEX ix_interactions_conversation_id ON interactions (conversation_id);

UPDATE alembic_version SET version_num='c83f0d52b714' WHERE alembic_version.version_num = 'b72e9c41a603';

-- Running upgrade c83f0d52b714 -> d94a1e63c825

ALTER TABLE conversations ADD COLUMN document_ids JSON;

UPDATE alembic_version SET version_num='d94a1e63c825' WHERE alembic_version.version_num = 'c83f0d52b714';

-- Running upgrade d94a1e63c825 -> e05b2f74d936

ALTER TABLE documents ADD COLUMN category VARCHAR(100);

ALTER TABLE documents ADD COLUMN processing_status VARCHAR(20) DEFAULT 'pending' NOT NULL;

ALTER TABLE documents ADD COLUMN processing_progress INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE documents ADD COLUMN processing_attempts INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE documents ADD COLUMN processing_error VARCHAR(255);

ALTER TABLE documents ADD COLUMN processing_available_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE documents ADD COLUMN processing_token VARCHAR(36);

UPDATE alembic_version SET version_num='e05b2f74d936' WHERE alembic_version.version_num = 'd94a1e63c825';

-- Running upgrade e05b2f74d936 -> f16c3085ea47

ALTER TABLE conversations ADD COLUMN parent_conversation_id UUID;

ALTER TABLE conversations ADD COLUMN parent_turn INTEGER;

ALTER TABLE conversations ADD CONSTRAINT fk_conversation_parent FOREIGN KEY(parent_conversation_id) REFERENCES conversations (id) ON DELETE SET NULL;

UPDATE alembic_version SET version_num='f16c3085ea47' WHERE alembic_version.version_num = 'e05b2f74d936';

-- Running upgrade f16c3085ea47 -> a27d4196fb58

CREATE TABLE user_policies (
    owner_id VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL,
    teams JSON NOT NULL,
    daily_queries INTEGER NOT NULL,
    daily_tokens INTEGER NOT NULL,
    storage_bytes INTEGER NOT NULL,
    retention_days INTEGER,
    PRIMARY KEY (owner_id)
);

CREATE TABLE document_grants (
    id UUID NOT NULL,
    document_id UUID NOT NULL,
    kind VARCHAR(10) NOT NULL,
    recipient VARCHAR(100) NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_document_grant UNIQUE (document_id, kind, recipient),
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE
);

CREATE INDEX ix_document_grants_document_id ON document_grants (document_id);

CREATE TABLE audit_events (
    id UUID NOT NULL,
    owner_id VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,
    resource_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id)
);

CREATE INDEX ix_audit_events_owner_id ON audit_events (owner_id);

CREATE INDEX ix_audit_events_created_at ON audit_events (created_at);

CREATE TABLE interaction_documents (
    interaction_id UUID NOT NULL,
    document_id UUID NOT NULL,
    PRIMARY KEY (interaction_id, document_id),
    FOREIGN KEY(interaction_id) REFERENCES interactions (id) ON DELETE CASCADE,
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE
);

INSERT INTO interaction_documents (interaction_id, document_id) SELECT id, document_id FROM interactions WHERE document_id IS NOT NULL;

CREATE TABLE daily_usage (
    owner_id VARCHAR(100) NOT NULL,
    day VARCHAR(10) NOT NULL,
    queries INTEGER NOT NULL,
    tokens INTEGER NOT NULL,
    PRIMARY KEY (owner_id, day)
);

UPDATE alembic_version SET version_num='a27d4196fb58' WHERE alembic_version.version_num = 'f16c3085ea47';

COMMIT;

