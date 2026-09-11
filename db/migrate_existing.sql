BEGIN;

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

COMMIT;

