"""麦门时钟 · 门店销量分析脚本（店长模式核心）

用法：
    python sales_analysis.py --data data/sales_<storeCode>.csv [--days 14] [--top 10]

数据文件格式（CSV，UTF-8）：
    date,hour,item_code,item_name,quantity,amount
    - date: YYYY-MM-DD（必填）
    - hour: 0-23（选填；填了才能算高峰时段）
    - item_code/item_name: 餐品编码/名称（item_code 可与麦当劳 MCP 的餐品 code 对应）
    - quantity: 销售份数（必填）
    - amount: 销售金额，单位元（必填）

输出：
    1. 最近 N 天日报：销量、环比（vs 上一日）、同期（vs 上周同一天）
    2. 星期几分布：每周 7 天平均销量，标出偏弱日
    3. 销量 Top 餐品（卖得最多）；有 hour 列时给高峰时段（卖得最快的时段）
    4. 备货建议：基于近 7 天趋势 + 星期效应
    5. 促销建议：节日前 7 天提醒 + 连续淡季日触发（需店长确认后才执行）

说明：销量数据由店长每日录入（POS 导出或手工汇总）。
      麦当劳 MCP 不提供门店历史销量接口，本脚本处理的是本地数据。
"""
import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def load_sales(path):
    if not os.path.exists(path):
        print("数据文件不存在: %s" % path)
        print("请先按模板创建（见 data/sales_template.csv），或让店长粘贴当日销量由 AI 代录。")
        sys.exit(1)
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if not r.get("date"):
                continue
            try:
                d = datetime.strptime(r["date"].strip(), "%Y-%m-%d").date()
                qty = int(float(r.get("quantity") or 0))
                amt = float(r.get("amount") or 0)
            except ValueError:
                continue
            hour = r.get("hour", "").strip()
            rows.append({
                "date": d,
                "hour": int(hour) if hour.isdigit() else None,
                "item_code": (r.get("item_code") or "").strip(),
                "item_name": (r.get("item_name") or "").strip(),
                "quantity": qty,
                "amount": amt,
            })
    if not rows:
        print("数据文件为空或格式不符: %s" % path)
        sys.exit(1)
    return rows


def load_holidays(path):
    """节日表：name,date,type,note。date 为 YYYY-MM-DD。"""
    holidays = []
    if not os.path.exists(path):
        return holidays
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("date"):
                try:
                    holidays.append({
                        "name": r["name"].strip(),
                        "date": datetime.strptime(r["date"].strip(), "%Y-%m-%d").date(),
                        "type": (r.get("type") or "").strip(),
                        "note": (r.get("note") or "").strip(),
                    })
                except ValueError:
                    continue
    return holidays


def pct(cur, base):
    if base == 0:
        return None
    return (cur - base) / base * 100.0


def fmt_pct(p):
    if p is None:
        return "  n/a"
    return "%+5.1f%%" % p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="销量 CSV 路径")
    ap.add_argument("--holidays", default="data/holidays_2026.csv", help="节日表 CSV 路径")
    ap.add_argument("--days", type=int, default=14, help="日报展示最近天数")
    ap.add_argument("--top", type=int, default=10, help="Top 餐品数量")
    ap.add_argument("--promo-threshold", type=float, default=15.0,
                    help="偏弱日阈值：低于整体均值百分之多少算弱")
    ap.add_argument("--promo-weeks", type=int, default=3,
                    help="连续多少周偏弱才触发促销建议")
    args = ap.parse_args()

    rows = load_sales(args.data)
    holidays = load_holidays(args.holidays)
    today = max(r["date"] for r in rows)
    data_start = min(r["date"] for r in rows)

    # ---------- 1. 日报 ----------
    daily = defaultdict(lambda: {"qty": 0, "amt": 0.0})
    for r in rows:
        daily[r["date"]]["qty"] += r["quantity"]
        daily[r["date"]]["amt"] += r["amount"]
    days_sorted = sorted(daily.keys())
    print("=" * 62)
    print("门店销量日报（数据范围 %s ~ %s，共 %d 天）" % (data_start, today, len(days_sorted)))
    print("-" * 62)
    print("%-12s %6s %10s %10s %10s" % ("日期", "星期", "销量", "环比", "同期(上周)"))
    for d in days_sorted[-args.days:]:
        prev = daily.get(d - timedelta(days=1))
        wow = daily.get(d - timedelta(days=7))
        print("%-12s %6s %6d %9s %9s" % (
            d.isoformat(), WEEKDAY_CN[d.weekday()], daily[d]["qty"],
            fmt_pct(pct(daily[d]["qty"], prev["qty"]) if prev else None),
            fmt_pct(pct(daily[d]["qty"], wow["qty"]) if wow else None)))

    # ---------- 2. 星期分布 ----------
    print()
    print("=" * 62)
    print("星期几分布（数据期内每周同一天平均销量）")
    print("-" * 62)
    wd = defaultdict(list)
    for d in days_sorted:
        wd[d.weekday()].append(daily[d]["qty"])
    overall = sum(daily[d]["qty"] for d in days_sorted) / len(days_sorted)
    weak_days = []
    for i in range(7):
        vals = wd.get(i, [])
        if not vals:
            print("%s  无数据" % WEEKDAY_CN[i])
            continue
        avg = sum(vals) / len(vals)
        diff = (avg - overall) / overall * 100 if overall else 0
        flag = ""
        if diff <= -args.promo_threshold:
            flag = "  <-- 偏弱（低于整体均值 %.0f%%）" % abs(diff)
            weak_days.append((i, avg, diff))
        print("%s  平均 %6.1f 份/天  (%s 整体)%s" % (
            WEEKDAY_CN[i], avg, fmt_pct(diff), flag))
    print("整体日均: %.1f 份" % overall)

    # ---------- 3. Top 餐品与高峰时段 ----------
    print()
    print("=" * 62)
    print("销量 Top %d 餐品（卖得最多）" % args.top)
    print("-" * 62)
    item_qty = defaultdict(int)
    item_amt = defaultdict(float)
    hour_qty = defaultdict(int)
    for r in rows:
        item_qty[r["item_name"] or r["item_code"]] += r["quantity"]
        item_amt[r["item_name"] or r["item_code"]] += r["amount"]
        if r["hour"] is not None:
            hour_qty[r["hour"]] += r["quantity"]
    total_qty = sum(item_qty.values())
    for name, q in sorted(item_qty.items(), key=lambda x: -x[1])[:args.top]:
        share = q / total_qty * 100 if total_qty else 0
        print("%-24s %5d 份  占比 %4.1f%%  销售额 %8.1f 元" % (name, q, share, item_amt[name]))
    if hour_qty:
        print()
        print("高峰时段（卖得最快的时段，按小时销量）")
        print("-" * 62)
        peak = sorted(hour_qty.items(), key=lambda x: -x[1])[:5]
        for h, q in peak:
            bar = "#" * int(q / max(hour_qty.values()) * 30)
            print("%02d:00-%02d:59  %5d 份  %s" % (h, h, q, bar))

    # ---------- 4. 备货建议 ----------
    print()
    print("=" * 62)
    print("备货建议")
    print("-" * 62)
    if len(days_sorted) >= 14:
        last7 = sum(daily[d]["qty"] for d in days_sorted[-7:])
        prev7 = sum(daily[d]["qty"] for d in days_sorted[-14:-7])
        trend = pct(last7, prev7)
        print("近 7 天销量 %d 份，前 7 天 %d 份，趋势 %s" % (last7, prev7, fmt_pct(trend)))
        if trend is not None and trend <= -10:
            print("建议：销量下行，下调备货量 10%%-15%%，重点关注鲜活品报废风险。")
        elif trend is not None and trend >= 10:
            print("建议：销量上行，热门单品备货量上调 10%%-20%%，提前确认供应商配送频次。")
        else:
            print("建议：销量平稳，维持现有备货结构。")
    else:
        print("数据不足 14 天，暂不给趋势建议（继续积累数据）。")
    tomorrow = today + timedelta(days=1)
    print("明天是 %s，可按「%s 平均 %.1f 份」安排基础备货。" % (
        tomorrow, WEEKDAY_CN[tomorrow.weekday()],
        (sum(wd.get(tomorrow.weekday(), [0])) / max(1, len(wd.get(tomorrow.weekday(), [0]))) or 0)))

    # ---------- 5. 促销建议 ----------
    print()
    print("=" * 62)
    print("促销建议（需店长确认后执行）")
    print("-" * 62)
    proposals = []
    # 5a. 节日通道：未来 7 天内的节日
    for h in holidays:
        delta = (h["date"] - today).days
        if 0 <= delta <= 7:
            proposals.append(
                "【节日预警】%s（%s，%s）还有 %d 天。建议提前 7 天上线节日主题活"
                "动（如限定套餐/加购礼），并在活动日历核对官方排期避免撞车。" % (
                    h["name"], h["date"].isoformat(), h["type"], delta))
    # 5b. 动态通道：连续 N 周同一偏弱日（按偏弱程度排序，只给首选+备选）
    if weak_days and len(days_sorted) >= args.promo_weeks * 7:
        weak_days.sort(key=lambda x: x[2])  # 偏弱越多越靠前
        recent_counts = []
        for i, avg, diff in weak_days:
            recent = [daily[d]["qty"] for d in days_sorted[-args.promo_weeks * 7:] if d.weekday() == i]
            if len(recent) >= args.promo_weeks:
                recent_counts.append((i, avg, diff))
        for rank, (i, avg, diff) in enumerate(recent_counts[:2]):
            tag = "首选" if rank == 0 else "备选"
            proposals.append(
                "【淡季日·%s】%s 连续 %d 周低于整体均值（均值 %.1f 份 vs 整体 %.1f 份，低 %.0f%%）。"
                "建议把 %s 设为固定会员日，如「%s会员日第二份半价」或「%s午后时段特惠」，"
                "把冷淡时段变成习惯性到店理由。" % (
                    tag, WEEKDAY_CN[i], args.promo_weeks, avg, overall, abs(diff),
                    WEEKDAY_CN[i], WEEKDAY_CN[i], WEEKDAY_CN[i]))
        if len(recent_counts) > 2:
            proposals.append("（其余偏弱日：%s，可视资源情况后续再做，不建议同时铺开多个会员日。）" % (
                "、".join(WEEKDAY_CN[i] for i, _, _ in recent_counts[2:])))
    if not proposals:
        print("当前无触发项：未来 7 天无节日，且未发现连续 %d 周的偏弱日。" % args.promo_weeks)
    else:
        for p in proposals:
            print("* " + p)
        print()
        print("以上仅为建议。店长回复「同意」后，活动才会记入 data/promotions.csv 台账；")
        print("回复「不同意」则记录原因，不执行。")

    print()
    print("=" * 62)
    print("分析完成。数据来源：本地录入销量（%s）" % args.data)


if __name__ == "__main__":
    main()
