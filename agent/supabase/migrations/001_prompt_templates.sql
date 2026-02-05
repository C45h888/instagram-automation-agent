-- Migration: Create prompt_templates table for DB-backed prompt versioning
-- This table allows A/B testing and runtime prompt updates without redeployment.
-- The PromptService loads from this table on startup, falling back to static defaults.

CREATE TABLE IF NOT EXISTS prompt_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_key VARCHAR(50) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    template TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    -- Only one active prompt per key
    CONSTRAINT unique_active_prompt_key UNIQUE (prompt_key, is_active)
        DEFERRABLE INITIALLY DEFERRED
);

-- Fast lookup for active prompts by key
CREATE INDEX IF NOT EXISTS idx_prompt_templates_key_active
    ON prompt_templates(prompt_key)
    WHERE is_active = true;

-- Auto-update updated_at on row changes
CREATE OR REPLACE FUNCTION update_prompt_templates_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS prompt_templates_updated_at ON prompt_templates;
CREATE TRIGGER prompt_templates_updated_at
    BEFORE UPDATE ON prompt_templates
    FOR EACH ROW
    EXECUTE FUNCTION update_prompt_templates_updated_at();

-- Enable RLS but allow service role full access
ALTER TABLE prompt_templates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role has full access to prompt_templates"
    ON prompt_templates
    FOR ALL
    USING (true)
    WITH CHECK (true);

COMMENT ON TABLE prompt_templates IS 'Stores versioned prompt templates for the oversight agent. PromptService loads active prompts on startup.';
COMMENT ON COLUMN prompt_templates.prompt_key IS 'Unique key: comment, dm, post';
COMMENT ON COLUMN prompt_templates.version IS 'Incrementing version number for audit trail';
COMMENT ON COLUMN prompt_templates.is_active IS 'Only one active prompt per key at a time';
