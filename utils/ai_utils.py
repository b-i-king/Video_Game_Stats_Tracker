"""
utils/ai_utils.py
Google Gemini AI agent — foundation for natural language stat queries.
Connect to Supabase after migration to enable live stat context.
"""
import os
from google import genai
from google.genai import types


def get_gemini_client() -> genai.Client:
    """Configure and return a Gemini client instance."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY env var not set")
    return genai.Client(api_key=api_key)


def ask_agent(prompt: str, context: str = "", model: str = "gemini-2.0-flash") -> str:
    """
    Send a prompt to Gemini with optional stat context.

    Args:
        prompt:  The user's question or request.
        context: Optional stat data as a formatted string to ground the response.
        model:   Gemini model ID. Trusted/Premium → gemini-2.0-flash,
                 Free → gemini-2.0-flash-lite.

    Returns:
        The agent's text response.    
    """
    client = get_gemini_client()
    system_prompt = (
        "You are a personal gaming performance assistant. "
        "You have access to the user's game stats and help them analyze performance, "
        "write captions, and identify trends. Be concise and conversational."
    )
    full_prompt = f"{system_prompt}\n\n{context}\n\n{prompt}" if context else f"{system_prompt}\n\n{prompt}"
    response = client.models.generate_content(
        model=model,
        contents=full_prompt,
    )
    return response.text


def build_stats_context(player_name: str, game_name: str, stats: list[dict]) -> str:
    """
    Format a list of stat dicts into a readable string for Gemini context.
    Pass this as the `context` argument to ask_agent().

    Args:
        player_name: Player's display name.
        game_name:   Game name/installment.
        stats:       List of dicts with keys: stat_type, stat_value, played_at.

    Returns:
        A formatted string summarizing the stats.
    """
    if not stats:
        return ""
    lines = [f"Player: {player_name}", f"Game: {game_name}", "Recent stats:"]
    for s in stats:
        lines.append(f"  - {s.get('stat_type')}: {s.get('stat_value')} (played {s.get('played_at', 'unknown')})")
    return "\n".join(lines)
