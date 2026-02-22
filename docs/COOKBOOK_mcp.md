# Cookbook: Using Tooli with MCP

## Goal

Expose Tooli commands as MCP tools with discovery-first workflows.

## Run server

```bash
mytool mcp serve --transport stdio
```

HTTP example:

```bash
mytool mcp serve --transport http --host 127.0.0.1 --port 8080
```

## Recommended flow

1. discover tools/resources
2. inspect command schema
3. invoke with strict JSON contracts
4. branch on envelope `ok/error`
