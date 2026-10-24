# MCP_INTEGRATION.md — 麦当劳 MCP 集成说明

## 使用的 MCP Server

麦当劳中国官方 MCP Server（远程托管，官方仓库：github.com/M-China/mcd-mcp-server）

| 项 | 值 |
|---|---|
| 接入地址 | https://mcp.mcd.cn |
| 传输协议 | Streamable HTTP |
| 认证方式 | 请求头 Authorization: Bearer <MCD_MCP_TOKEN> |
| 限流 | 600 次/分钟/Token |
| Token 申请 | open.mcd.cn/mcp（手机号登录 → 控制台 → 激活） |

## 使用的 Tool 及用途

| Tool | 在本项目中的用途 |
|---|---|
| now-time-info | 获取当前真实时间，时段判断的第一步（不猜时间） |
| campaign-calendar | 当月营销活动日历，推荐时带上进行中的活动 |
| query-nearby-stores | 按用户地址查询附近可参与门店 |
| query-meals | 查询当前门店实时在售菜单（推荐的唯一数据来源） |
| query-meal-detail | 查询餐品套餐组成与可替换选项 |
| available-coupons | 麦麦省可领取优惠券列表 |
| query-my-coupons | 我的可用优惠券 |
| auto-bind-coupons | 一键领取所有可领券（用户确认后执行） |
| calculate-price | 对推荐组合做含券价格试算（原价/优惠/实付） |

## 调用流程

```
用户提问"现在吃啥"
  → now-time-info            拿真实当前时间，粗分时段
  → campaign-calendar        查当月活动
  → query-nearby-stores      定位附近门店（用户未提供地址时先询问）
  → query-meals              拉当前门店实时在售列表（时段推荐的硬依据）
  → [可选] query-meal-detail 展开套餐组成
  → available-coupons + query-my-coupons   看券
  → [用户确认] auto-bind-coupons           一键领券
  → calculate-price          算券后价
  → 输出推荐 + 合规声明
```

## 业务价值

"到饭点不知道吃啥"是一个每天发生、决策成本高的真实问题。本项目把**时间感知、实时在售、活动日历、优惠券**四类分散的信息在一次对话里串完，输出"现在这一刻就可执行"的点餐组合——而不是一份脱离实时库存的静态推荐。

## 实测验证（2026-10-24 14:28，真实调用记录）

测试场景：到店自取（beType=1, orderType=1），测试位置北京市中关村。全链路 6 步全部跑通：

| 步骤 | 工具 | 实测结果 |
|---|---|---|
| 1 | now-time-info | 返回 2026-10-24 14:28:50 (SATURDAY)，标准 JSON |
| 2 | campaign-calendar | 返回当月活动 Markdown（含"麦当劳 X PEACEMINUSONE"联名活动，10/20 往期回顾） |
| 3 | query-nearby-stores | 返回 5 家附近门店；首选"麦当劳北京善缘街(中关村5号)餐厅"（storeCode=1950640，营业 07:00-22:00，营业中） |
| 4 | query-meals | 返回 14 个在售分类（人气热卖/鸡肉汉堡/巨无霸/安格斯MAX/麦咖啡/500大卡套餐/饮品等），含餐品 code 与现价 |
| 5 | query-store-coupons + available-coupons | 门店可用券：麦辣鸡腿堡三件套（couponId=B7A9CFE8...）；麦麦省可领：免费脆薯饼、11.9元麦辣鸡腿堡 |
| 6 | calculate-price | 麦辣鸡腿汉堡三件套 x1 = 3350 分（¥33.5），单位"分"需 ÷100 |

**实测中发现并已写入 SKILL.md 的关键事实**：
- 响应格式有三种：标准 JSON（多数工具）、Markdown 文本（campaign-calendar / available-coupons / query-my-coupons / auto-bind-coupons）、TOON 紧凑格式（list-nutrition-foods）；
- query-nearby-stores 按位置搜索时 city+keyword 必填；到店自取（beType=1）不需要 beCode，只有得来速/外送/团餐才需要；
- calculate-price 等交易类工具金额单位为"分"；
- 门店预约时段返回官方时段名（早餐/午餐/下午茶/夜市/宵夜），是"麦门时钟"时段划分的一手依据。

完整测试脚本与输出见仓库 tools/ 目录（chain_test.py / chain_test_result.txt）。开发对话上下文见 workbuddy.md。
