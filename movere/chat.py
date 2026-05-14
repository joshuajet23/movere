"""Natural language interface — Claude parses intent and calls project/log tools."""

import json
import anthropic

from . import projects as proj_store
from . import logger


_TOOLS = [
    {
        "name": "add_project",
        "description": "Add a new personal project to track in Movere.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Human-readable project name"},
                "goal": {"type": "string", "description": "Optional daily/weekly goal, e.g. '5 pages/day' or '30 min/day'"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "remove_project",
        "description": "Archive a project the user no longer wants to track.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name of the project to archive"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "update_goal",
        "description": "Update the daily or weekly goal for an existing project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "goal": {"type": "string", "description": "New goal string, e.g. '10 pages/day'"},
            },
            "required": ["name", "goal"],
        },
    },
    {
        "name": "log_progress",
        "description": "Log a progress note against a project for today.",
        "input_schema": {
            "type": "object",
            "properties": {
                "note": {"type": "string", "description": "What the user did"},
                "project_id": {"type": "string", "description": "Project ID slug (optional — omit to auto-detect)"},
            },
            "required": ["note"],
        },
    },
    {
        "name": "list_projects",
        "description": "Return the current list of active projects (read-only, no side effects).",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def _system_prompt(projects: list[dict]) -> str:
    proj_lines = "\n".join(
        f"  - {p['name']} (id: {p['id']}, goal: {p.get('goal') or 'none'})"
        for p in projects
    ) or "  (none yet)"

    return f"""You are the voice of Movere — a personal project OS built on Brian Little's idea that what makes life meaningful is what we're trying to do. You're the user's coach and thinking partner, not a task manager.

The user's active projects:
{proj_lines}

Your job is to listen like a coach, not parse commands. Most messages need a real response before (or instead of) any tool call.

How to respond:
- When someone shares life context — a big night out, a stressful week, a job starting Monday, a rough day — acknowledge it genuinely first. That comes before anything else.
- Adapt your expectations to what they've told you. If they mention they'll have poor sleep tomorrow, don't push hard on goals for that day. If something big is coming, name it.
- Ask a follow-up when it would move the conversation forward — but only one, and only if it's natural.
- Use tools when there's a clear action to take (logging progress, updating a goal, adding a project). Don't reach for a tool when the right response is just to be present.
- After a tool call, weave the confirmation into a natural sentence — don't announce it like a system message.
- Be warm, direct, and human. No bullet points. Responses should feel like a short message from someone who actually knows you, not a chatbot output. 2-4 sentences is usually right."""


def _execute_tool(name: str, inputs: dict) -> str:
    if name == "add_project":
        try:
            p = proj_store.add(inputs["name"], goal=inputs.get("goal"))
            goal_str = f" (goal: {p['goal']})" if p.get("goal") else ""
            return f"Added: {p['name']}{goal_str}"
        except ValueError as e:
            return f"Error: {e}"

    elif name == "remove_project":
        try:
            p = proj_store.remove(inputs["name"])
            return f"Archived: {p['name']}"
        except ValueError as e:
            return f"Error: {e}"

    elif name == "update_goal":
        data = proj_store._load()
        slug = proj_store._slug(inputs["name"])
        project = next((p for p in data["projects"] if p["id"] == slug or p["name"].lower() == inputs["name"].lower()), None)
        if not project:
            return f"Error: project '{inputs['name']}' not found."
        project["goal"] = inputs["goal"]
        proj_store._save(data)
        return f"Updated goal for {project['name']}: {inputs['goal']}"

    elif name == "log_progress":
        entry = logger.add_entry(inputs["note"], project_id=inputs.get("project_id"))
        proj = entry.get("project") or "general"
        return f"Logged [{proj}]: {inputs['note']}"

    elif name == "list_projects":
        projects = proj_store.all_active()
        if not projects:
            return "No active projects yet."
        return "\n".join(f"- {p['name']} (goal: {p.get('goal') or 'none'})" for p in projects)

    return f"Unknown tool: {name}"


def process(message: str, cfg: dict, history: list[dict] | None = None) -> str:
    """Process a message and return Claude's reply. history is a list of prior {role, content} turns."""
    client = anthropic.Anthropic(api_key=cfg["anthropic"]["api_key"])
    projects = proj_store.all_active()

    messages = list(history or []) + [{"role": "user", "content": message}]

    response = client.messages.create(
        model=cfg["anthropic"]["model"],
        max_tokens=512,
        system=_system_prompt(projects),
        tools=_TOOLS,
        messages=messages,
    )

    tool_results = []
    for block in response.content:
        if block.type == "tool_use":
            result = _execute_tool(block.name, block.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })

    if tool_results:
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        followup = client.messages.create(
            model=cfg["anthropic"]["model"],
            max_tokens=256,
            system=_system_prompt(proj_store.all_active()),
            tools=_TOOLS,
            messages=messages,
        )
        return next((b.text for b in followup.content if hasattr(b, "text")), "Done.")

    return next((b.text for b in response.content if hasattr(b, "text")), "Done.")


def run(message: str, cfg: dict) -> None:
    reply = process(message, cfg)
    print(f"\nMovere: {reply}\n")
