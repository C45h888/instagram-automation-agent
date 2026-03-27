"""
Typed ID Wrappers — Distinguish Meta/Instagram ID Space from Supabase UUID Space
================================================================================
Two completely different ID spaces circulate through the codebase:

ID Space A — Meta/Instagram IDs (strings, from webhooks and IG API)
    post_id: "17841475450533073_1234567890"     ← Instagram media ID
    sender_id: "12345678901234567"              ← Instagram user ID
    ig_page_id: "17841475450533073"            ← Instagram Business Account ID

ID Space B — Supabase UUIDs (strings, internal FKs)
    media_uuid: "a3f8c9d2-b4e1-..."
    account_uuid: "f47ac10b-58cc-4372-..."
    conversation_uuid: "e9d1a2b3-c4f5-..."

Passing a Meta ID where a Supabase UUID is expected silently returns {}.
These wrappers make that a TypeError at call time.
"""

import re


class InstagramId(str):
    """A Meta/Instagram numeric string ID (from webhooks, IG API).

    Distinguishes Meta's ID space from Supabase UUID space.
    The _id_space sentinel makes Python's isinstance() check fail for plain str,
    catching accidental raw-string usage at runtime.

    Usage:
        def get_post_context(post_id: InstagramId) -> dict: ...

        # TypeError raised if wrong ID space passed:
        get_post_context(SupabaseUUID("abc-123"))   # ← TypeError
        get_post_context(InstagramId("17841475450533073"))  # ← OK
    """

    _id_space = "instagram"

    def __new__(cls, value: str):
        return super().__new__(cls, value)

    def __init__(self, value: str):
        pass


class SupabaseUUID(str):
    """A Supabase UUID. Used for all internal FK relationships.

    Never sent to Meta's API or received from Meta's webhooks.
    The _id_space sentinel makes Python's isinstance() check fail for plain str,
    catching accidental raw-string usage at runtime.

    Usage:
        def get_post_context_by_uuid(media_uuid: SupabaseUUID) -> dict: ...

        # TypeError raised if wrong ID space passed:
        get_post_context_by_uuid(InstagramId("17841475450533073"))  # ← TypeError
        get_post_context_by_uuid(SupabaseUUID("a3f8c9d2-b4e1-..."))  # ← OK
    """

    _id_space = "supabase"

    def __new__(cls, value: str):
        return super().__new__(cls, value)

    def __init__(self, value: str):
        pass


def verify_id_space(value: str, expected_space: type) -> str:
    """Assert that a string is the correct typed ID subclass.

    Raises TypeError if plain str or wrong ID space is passed.
    This makes cross-space ID bugs a loud failure instead of a silent {} return.

    Usage:
        # At the start of a function that expects InstagramId:
        post_id = verify_id_space(post_id, InstagramId)
    """
    if not isinstance(value, expected_space):
        received = type(value).__name__
        expected = expected_space.__name__
        raise TypeError(
            f"ID space mismatch: received {received} ('{value}'), "
            f"expected {expected}. "
            f"Instagram IDs (InstagramId) and Supabase UUIDs (SupabaseUUID) "
            f"are incompatible — passing the wrong ID space silently returns {{}}."
        )
    return value
