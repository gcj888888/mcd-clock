"""麦门时钟全链路实测：时间 → 活动 → 门店 → 菜单 → 券 → 算价。

场景：到店自取（beType=1, orderType=1，不传 beCode）。
用法：python chain_test.py <MCD_MCP_TOKEN> [城市] [位置关键词]
"""
import json
import sys
import urllib.request
import urllib.error

URL = "https://mcp.mcp.cn" if False else "https://mcp.mcd.cn"
LINES = []


def log(s=""):
    print(s)
    LINES.append(s)


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
            return resp.status, resp.headers.get("mcp-session-id"), resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("mcp-session-id"), e.read().decode()


def call(session, token, rid, name, args):
    status, _, body = post({
        "jsonrpc": "2.0", "id": rid, "method": "tools/call",
        "params": {"name": name, "arguments": args},
    }, token, session)
    text = body.strip()
    if text.startswith("data:"):
        text = "\n".join(line[5:].strip() for line in text.splitlines() if line.startswith("data:"))
    try:
        data = json.loads(text)
    except Exception:
        log("  [%s] 解析失败: %s" % (name, text[:300]))
        return None
    if "error" in data:
        log("  [%s] RPC错误: %s" % (name, json.dumps(data["error"], ensure_ascii=False)[:300]))
        return None
    result = data.get("result", {})
    if result.get("isError"):
        log("  [%s] 工具返回错误" % name)
    # content[0].text = Markdown 说明前缀 + JSON 数据 + Markdown 尾巴
    # 用 raw_decode 从第一个 { 处解析出一个完整 JSON 对象，忽略前后文本
    content = result.get("content", [])
    payload_text = ""
    for c in content:
        if c.get("type") == "text":
            payload_text += c.get("text", "")
    idx = payload_text.find('{"success"')
    if idx < 0:
        idx = payload_text.find("{")
    if idx >= 0:
        try:
            obj, _ = json.JSONDecoder().raw_decode(payload_text, idx)
            return obj
        except Exception:
            pass
    log("  [%s] 响应: %s" % (name, payload_text[:300]))
    return None


def main():
    token = sys.argv[1]
    city = sys.argv[2] if len(sys.argv) > 2 else "北京市"
    keyword = sys.argv[3] if len(sys.argv) > 3 else "中关村"

    status, sid, body = post({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                   "clientInfo": {"name": "mcd-clock-chain-test", "version": "0.1.0"}},
    }, token)
    if status != 200:
        log("initialize 失败 HTTP %s: %s" % (status, body[:300]))
        sys.exit(1)
    log("=== 麦门时钟全链路实测 %s ===" % ("到店自取场景"))
    log("")

    rid = 2
    log("[1/6] now-time-info 获取真实时间")
    r = call(sid, token, rid, "now-time-info", {}); rid += 1
    if r and r.get("data"):
        d = r["data"]
        log("  当前时间: %s (%s)" % (d.get("formatted"), d.get("dayOfWeek")))
    log("")

    log("[2/6] campaign-calendar 当月活动")
    r = call(sid, token, rid, "campaign-calendar", {}); rid += 1
    if r and r.get("data"):
        for day in r["data"].get("dailyList", [])[:3]:
            for ev in day.get("events", [])[:3]:
                log("  %s %s (type=%s)" % (day.get("date"), ev.get("activityTitle"), ev.get("eventType")))
    log("")

    log("[3/6] query-nearby-stores 附近门店 (%s/%s, 到店自取)" % (city, keyword))
    r = call(sid, token, rid, "query-nearby-stores",
             {"beType": 1, "searchType": 2, "city": city, "keyword": keyword}); rid += 1
    store = None
    if r and r.get("data"):
        stores = r["data"]
        log("  返回 %d 家门店" % len(stores))
        for s in stores[:3]:
            log("  - %s (%s) 营业%s-%s 营业中=%s" % (
                s.get("storeName"), s.get("storeCode"),
                s.get("businessStartTime"), s.get("businessEndTime"), s.get("businessStatus")))
        store = stores[0]
    if not store:
        log("  未取到门店，链路中断")
        sys.exit(1)
    store_code = store["storeCode"]
    log("")

    log("[4/6] query-meals 门店实时在售菜单 (storeCode=%s)" % store_code)
    r = call(sid, token, rid, "query-meals",
             {"storeCode": store_code, "orderType": 1, "beType": 1}); rid += 1
    pick = None
    if r and r.get("data"):
        cats = r["data"].get("categories", [])
        for c in cats:
            names = [m.get("code") for m in c.get("meals", [])][:5]
            log("  分类「%s」%d 个餐品, 示例 code: %s" % (c.get("name"), len(c.get("meals", [])), names))
        # 选一个带价格的餐品用于算价
        meals_map = r["data"].get("meals", {})
        for code, m in meals_map.items():
            if m.get("currentPrice"):
                pick = (code, m)
                break
        if pick:
            log("  选用算样品: code=%s 现价=%s" % (pick[0], pick[1].get("currentPrice")))
    log("")

    log("[5/6] 优惠券（query-store-coupons 门店可用 + available-coupons 可领）")
    r = call(sid, token, rid, "query-store-coupons",
             {"storeCode": store_code, "orderType": 1, "beType": 1}); rid += 1
    if r is not None:
        log("  门店可用券: %s" % json.dumps(r.get("data"), ensure_ascii=False)[:400])
    r = call(sid, token, rid, "available-coupons", {}); rid += 1
    if r and r.get("data") is not None:
        log("  可领券 %d 张: %s" % (len(r["data"]), json.dumps(r["data"][:3], ensure_ascii=False)[:400]))
    log("")

    log("[6/6] calculate-price 算价（单位:分）")
    if pick:
        r = call(sid, token, rid, "calculate-price", {
            "storeCode": store_code, "orderType": 1, "beType": 1,
            "items": [{"productCode": pick[0], "quantity": 1}],
        }); rid += 1
        if r and r.get("data"):
            d = r["data"]
            log("  原价=%s 现价=%s 优惠=%s (均为分, 除以100得元)" % (
                d.get("originalPrice"), d.get("price"), d.get("discount")))
            for p in d.get("productList", []):
                log("  - %s x%d 小计=%s" % (p.get("productName"), p.get("quantity"), p.get("subtotal")))
    log("")
    log("=== 链路实测完成 ===")

    with open("chain_test_result.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(LINES))
    log("完整记录已存 chain_test_result.txt")


if __name__ == "__main__":
    main()
