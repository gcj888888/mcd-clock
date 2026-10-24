"""列出麦当劳 MCP Server 的全部工具（用于参赛作品实测验证）。

用法：
    python list_tools.py <MCD_MCP_TOKEN>

原理：MCP over Streamable HTTP 是 JSON-RPC 2.0。
    第一步 POST initialize，从响应头拿 mcp-session-id；
    第二步带 session POST tools/list。
"""
import json
import sys
import urllib.request
import urllib.error

URL = "https://mcp.mcd.cn"


def post(payload, token, session=None):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": "Bearer " + token,
    }
    if session:
        headers["mcp-session-id"] = session
    req = urllib.request.Request(URL, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            sid = resp.headers.get("mcp-session-id")
            return resp.status, sid, body
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("mcp-session-id"), e.read().decode()
    except Exception as e:
        return None, None, "NETWORK_ERROR: %s" % e


def main():
    if len(sys.argv) < 2:
        print("用法: python list_tools.py <MCD_MCP_TOKEN>")
        sys.exit(1)
    token = sys.argv[1]

    status, sid, body = post({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "mcd-clock-test", "version": "0.1.0"},
        },
    }, token)
    print("initialize -> HTTP %s, session=%s" % (status, sid))
    if status != 200:
        print(body[:500])
        sys.exit(1)

    status, sid2, body = post({
        "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
    }, token, sid)
    print("tools/list -> HTTP %s" % status)
    if status != 200:
        print(body[:500])
        sys.exit(1)

    # 响应可能是 SSE 格式（data: 开头）或纯 JSON，两种都兼容
    text = body.strip()
    if text.startswith("data:"):
        text = "\n".join(line[5:].strip() for line in text.splitlines() if line.startswith("data:"))
    data = json.loads(text)
    tools = data.get("result", {}).get("tools", [])
    print("共 %d 个工具：" % len(tools))
    for t in tools:
        print("- %s : %s" % (t.get("name"), (t.get("description") or "")[:80]))
    with open("tools_snapshot.json", "w", encoding="utf-8") as f:
        json.dump(tools, f, ensure_ascii=False, indent=2)
    print("完整 schema 已存 tools_snapshot.json")


if __name__ == "__main__":
    main()
