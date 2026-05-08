"""Synchronous wrapper around the lexbeam EU AI Act MCP server."""
import asyncio
import json

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


_SERVER_PARAMS = StdioServerParameters(
    command="npx",
    args=["-y", "@lexbeam-software/eu-ai-act-mcp"],
)


async def _call_tools(question: str) -> dict:
    async with stdio_client(_SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            faq = await session.call_tool("euaiact_answer_question", {"question": question})
            deadlines = await session.call_tool("euaiact_check_deadlines", {"only_upcoming": True})

    def _parse(result) -> dict | None:
        for block in result.content:
            if hasattr(block, "text"):
                try:
                    return json.loads(block.text)
                except json.JSONDecodeError:
                    return {"raw": block.text}
        return None

    return {"faq": _parse(faq), "deadlines": _parse(deadlines)}


def _format_faq(data: dict) -> str:
    lines = [f"**Q:** {data.get('question', '')}", f"**A:** {data.get('answer', '')}"]
    refs = data.get("article_references", [])
    if refs:
        lines.append(f"**References:** {', '.join(refs)}")
    return "\n".join(lines)


def _format_deadlines(data: dict) -> str:
    milestones = data.get("milestones", [])
    lines = []
    for m in milestones:
        days = m.get("days_remaining", "?")
        lines.append(f"• **{m['date']}** — {m['name']} ({days} days away)")
        lines.append(f"  {m.get('description', '')[:200]}")
    return "\n".join(lines)


def get_structured_context(question: str) -> tuple[str, str]:
    """Return (display_text, prompt_context) from lexbeam MCP."""
    try:
        results = asyncio.run(_call_tools(question))
        display_parts, prompt_parts = [], []

        if results["faq"]:
            display_parts.append(_format_faq(results["faq"]))
            d = results["faq"]
            prompt_parts.append(
                f"Curated guidance: {d.get('answer', '')} "
                f"(refs: {', '.join(d.get('article_references', []))})"
            )

        if results["deadlines"]:
            dl = _format_deadlines(results["deadlines"])
            display_parts.append(dl)
            milestones = results["deadlines"].get("milestones", [])
            prompt_parts.append(
                "Upcoming deadlines: " +
                "; ".join(f"{m['date']}: {m['name']}" for m in milestones)
            )

        return "\n\n".join(display_parts), "\n".join(prompt_parts)
    except Exception as e:
        msg = f"Structured context unavailable: {e}"
        return msg, ""
