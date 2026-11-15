---
name: godot-mcp
description: "Model Context Protocol (MCP) server for Godot Engine. Enables AI agents to interact directly with Godot projects: launching scenes headlessly, capturing console logs, instantiating 2D/3D sprites, and verifying gameplay state."
---

# Godot MCP Skill

Enables AI agents to execute and inspect Godot projects via standard MCP JSON-RPC protocol.
Located at `libraries\com.github.coding-solo.godot-mcp`.

## Server Launch Command

```powershell
node "libraries\com.github.coding-solo.godot-mcp\build\index.js"
```

## Agent MCP Client Configuration (JSON)

Add the following to your agent MCP configuration (e.g. `claude_desktop_config.json` or Antigravity MCP settings):

```json
{
  "mcpServers": {
    "godot": {
      "command": "node",
      "args": ["libraries/com.github.coding-solo.godot-mcp/build/index.js"],
      "env": {
        "GODOT_PATH": "C:/Program Files/Godot/Godot.exe"
      }
    }
  }
}
```

## Available Operations
- Launch project scenes headlessly
- Read engine stdout/stderr debug logs
- Verify resource loading and shader compilation
