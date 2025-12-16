-- pgvector Migration Script
-- Run this AFTER the pgvector image is deployed and the pod is ready

-- Step 1: Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Step 2: Migrate product_embeddings table
-- 2a. Add new vector column
ALTER TABLE product_embeddings 
ADD COLUMN IF NOT EXISTS embedding_vec vector(1536);

-- 2b. Copy data from JSONB to vector format
UPDATE product_embeddings 
SET embedding_vec = embedding::vector
WHERE embedding IS NOT NULL AND embedding_vec IS NULL;

-- 2c. Verify migration (should return 0)
DO $$
DECLARE
    unmigrated_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO unmigrated_count 
    FROM product_embeddings 
    WHERE embedding IS NOT NULL AND embedding_vec IS NULL;
    
    IF unmigrated_count > 0 THEN
        RAISE EXCEPTION 'Migration incomplete: % rows not migrated in product_embeddings', unmigrated_count;
    END IF;
    RAISE NOTICE 'product_embeddings migration verified: all rows migrated successfully';
END $$;

-- 2d. Drop old column and rename new one
ALTER TABLE product_embeddings DROP COLUMN IF EXISTS embedding;
ALTER TABLE product_embeddings RENAME COLUMN embedding_vec TO embedding;

-- 2e. Create HNSW index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS idx_product_embeddings_hnsw 
ON product_embeddings USING hnsw (embedding vector_cosine_ops);

-- Step 3: Migrate email_embeddings table
-- 3a. Add new vector column
ALTER TABLE email_embeddings 
ADD COLUMN IF NOT EXISTS embedding_vec vector(1536);

-- 3b. Copy data from JSONB to vector format
UPDATE email_embeddings 
SET embedding_vec = embedding::vector
WHERE embedding IS NOT NULL AND embedding_vec IS NULL;

-- 3c. Verify migration (should return 0)
DO $$
DECLARE
    unmigrated_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO unmigrated_count 
    FROM email_embeddings 
    WHERE embedding IS NOT NULL AND embedding_vec IS NULL;
    
    IF unmigrated_count > 0 THEN
        RAISE EXCEPTION 'Migration incomplete: % rows not migrated in email_embeddings', unmigrated_count;
    END IF;
    RAISE NOTICE 'email_embeddings migration verified: all rows migrated successfully';
END $$;

-- 3d. Drop old column and rename new one
ALTER TABLE email_embeddings DROP COLUMN IF EXISTS embedding;
ALTER TABLE email_embeddings RENAME COLUMN embedding_vec TO embedding;

-- 3e. Create HNSW index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS idx_email_embeddings_hnsw 
ON email_embeddings USING hnsw (embedding vector_cosine_ops);

-- Step 4: Verify final state
DO $$
DECLARE
    product_count INTEGER;
    email_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO product_count FROM product_embeddings WHERE embedding IS NOT NULL;
    SELECT COUNT(*) INTO email_count FROM email_embeddings WHERE embedding IS NOT NULL;
    
    RAISE NOTICE 'Migration complete!';
    RAISE NOTICE 'product_embeddings: % rows with embeddings', product_count;
    RAISE NOTICE 'email_embeddings: % rows with embeddings', email_count;
END $$;

-- Verify indexes exist
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename IN ('product_embeddings', 'email_embeddings') 
AND indexname LIKE '%hnsw%';
