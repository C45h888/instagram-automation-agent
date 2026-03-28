-- Migration: 002_scheduled_posts_ugc_content_id
-- Adds ugc_content_id FK to scheduled_posts for UGC repost tracking.
-- This enables the content_scheduler to link a scheduled_post back to its
-- ugc_content source when repurposing granted UGC as a scheduled post.

BEGIN;

-- Add ugc_content_id column (nullable, no constraint initially to avoid blocking)
ALTER TABLE scheduled_posts
ADD COLUMN ugc_content_id UUID;

-- Add FK constraint after column exists
ALTER TABLE scheduled_posts
ADD CONSTRAINT scheduled_posts_ugc_content_id_fkey
FOREIGN KEY (ugc_content_id) REFERENCES ugc_content(id);

-- Index for fast lookups when finding UGC-sourced scheduled posts
CREATE INDEX idx_scheduled_posts_ugc_content_id
ON scheduled_posts(ugc_content_id)
WHERE ugc_content_id IS NOT NULL;

COMMIT;
