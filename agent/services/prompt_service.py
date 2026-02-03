"""
Prompt Service
===============
Loads prompts from Supabase prompt_templates table on startup.
Falls back to static PROMPTS dict from prompts.py if table doesn't exist or is empty.
Caches in memory; provides reload method for runtime updates.

SQL to create the table (run manually):

  CREATE TABLE prompt_templates (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      prompt_key VARCHAR NOT NULL,
      version INTEGER NOT NULL DEFAULT 1,
      template TEXT NOT NULL,
      is_active BOOLEAN NOT NULL DEFAULT true,
      created_at TIMESTAMPTZ DEFAULT NOW(),
      updated_at TIMESTAMPTZ DEFAULT NOW(),
      created_by VARCHAR DEFAULT 'system',
      notes TEXT,
      UNIQUE(prompt_key, version)
  );

  CREATE INDEX idx_prompt_templates_active
      ON prompt_templates(prompt_key, is_active)
      WHERE is_active = true;
"""

from config import supabase, logger
from prompts import PROMPTS as DEFAULT_PROMPTS


class PromptService:
    """In-memory cache of prompt templates with DB fallback."""

    _prompts: dict[str, str] = {}
    _versions: dict[str, int] = {}

    @classmethod
    def load(cls):
        """Load active prompts from DB. Fall back to defaults on any failure."""
        cls._prompts = dict(DEFAULT_PROMPTS)
        cls._versions = {k: 0 for k in DEFAULT_PROMPTS}

        try:
            result = supabase.table("prompt_templates") \
                .select("prompt_key, template, version") \
                .eq("is_active", True) \
                .execute()

            if result.data:
                for row in result.data:
                    key = row["prompt_key"]
                    if key in cls._prompts:
                        cls._prompts[key] = row["template"]
                        cls._versions[key] = row["version"]
                        logger.info(f"Prompt '{key}' loaded from DB (v{row['version']})")

            logger.info(f"Prompt versions: {cls._versions}")
        except Exception as e:
            logger.warning(f"Could not load prompts from DB (using defaults): {e}")

    @classmethod
    def get(cls, key: str) -> str:
        """Get a prompt template by key. Returns default if not loaded."""
        if not cls._prompts:
            cls._prompts = dict(DEFAULT_PROMPTS)
            cls._versions = {k: 0 for k in DEFAULT_PROMPTS}
        return cls._prompts.get(key, DEFAULT_PROMPTS.get(key, ""))

    @classmethod
    def get_version(cls, key: str) -> int:
        """Get the version number for a prompt key (0 = static default)."""
        return cls._versions.get(key, 0)

    @classmethod
    def reload(cls):
        """Re-fetch prompts from DB. Can be called from admin endpoint."""
        logger.info("Reloading prompts from database...")
        cls.load()
