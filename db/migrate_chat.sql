BEGIN;

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

COMMIT;

