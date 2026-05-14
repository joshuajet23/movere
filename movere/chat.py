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

    return f"""You are Movere's assistant — a personal project OS inspired by Brian Little's personal projects theory.

The user manages a set of personal projects they want to track in their daily life. Your job is to understand what they want and call the right tool.

Current active projects:
{proj_lines}

Guidelines:
- If the user wants to track something new, call add_project. Infer a sensible goal from context if they mention a frequency or target (e.g. "every day", "30 minutes", "5 pages").
- If the user wants to stop tracking something, call remove_project.
- If the user is reporting progress or what they did, call log_progress.
- If the user wants to change a goal, call update_goal.
- If the user just wants to know what they're tracking, call list_projects.
- After calling a tool, give a short, warm confirmation. No bullet points. One or two sentences max."""


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


def run(message: str, cfg: dict) -> None:
    client = anthropic.Anthropic(api_key=cfg["anthropic"]["api_key"])
    projects = proj_store.all_active()

    response = client.messages.create(
        model=cfg["anthropic"]["model"],
        max_tokens=512,
        system=_system_prompt(projects),
        tools=_TOOLS,
        messages=[{"role": "user", "content": message}],
    )

    # Execute any tool calls, then get Claude's final reply
    messages = [{"role": "user", "content": message}]
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
        reply = next((b.text for b in followup.content if hasattr(b, "text")), "Done.")
    else:
        reply = next((b.text for b in response.content if hasattr(b, "text")), "Done.")

    print(f"\nMovere: {reply}\n")
