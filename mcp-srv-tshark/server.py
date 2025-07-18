from fastapi import FastAPI, Request
from pydantic import BaseModel
import uuid, json
from tools import TOOL_DEFS, call_tool

app = FastAPI(title="TShark MCP Server")

# ----------------- 1) INITIALIZE -----------------
PROTOCOL = "2025-03-26"

@app.post("/mcp")
async def mcp_entry(request: Request):
    payload = await request.json()

    # batch ou single ?
    if isinstance(payload, list):
        return [await handle(msg) for msg in payload]
    return await handle(payload)

async def handle(msg):
    if msg["method"] == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg["id"],
            "result": {
                "protocolVersion": PROTOCOL,
                "capabilities": { "tools": { "listChanged": False } },
                "serverInfo": { "name": "SK-Tshark-Mcp", "version": "0.1.0" }
            }
        }

    if msg["method"] == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg["id"],
            "result": { "tools": TOOL_DEFS }     # défini dans tools.py
        }

    if msg["method"] == "tools/call":
        name    = msg["params"]["name"]
        args    = msg["params"].get("arguments", {})
        result  = await call_tool(name, args)
        return {
            "jsonrpc": "2.0",
            "id": msg["id"],
            "result": { "content": [{ "type":"text", "text": result }], "isError": False }
        }

    # fallback erreur standard JSON-RPC
    return {
        "jsonrpc": "2.0",
        "id": msg.get("id"),
        "error": { "code": -32601, "message": f"Unknown method {msg['method']}" }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)
