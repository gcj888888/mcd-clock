# MCP_INTEGRATION.md — 麦当劳 MCP 集成说明

## 使用的 MCP Server

麦当劳中国官方 MCP Server（远程托管，官方仓库：github.com/M-China/mcd-mcp-server）

| 项 | 值 |
|---|---|
| 接入地址 | https://mcp.mcd.cn |
| 传输协议 | Streamable HTTP |
| 认证方式 | 请求头 Authorization: Bearer <MCD_MCP_TOKEN> |
| 限流 | 600 次/分钟/Token（draw-lottery 另限 1 次/秒） |
| Token 申请 | open.mcd.cn/mcp（手机号登录 → 控制台 → 激活） |

## MCP 能力与本地功能的边界（重要，如实区分）

| 功能 | 数据来源 |
|---|---|
| 当前时间、活动日历、附近门店、实时在售菜单、餐品详情 | **麦当劳 MCP 真实调用** |
| 营养数据（能量/蛋白质/脂肪/碳水/钠/钙） | **麦当劳 MCP**（list-nutrition-foods，TOON 紧凑格式） |
| 优惠券查询/一键领取、价格试算 | **麦当劳 MCP** |
| 门店每日销量、分时段销量、历史趋势 | **本地数据**（店长每日录入 POS/手工汇总，存 CSV）——麦当劳 MCP 不提供门店销量接口 |
| 销量对比分析、备货建议、促销候选方案 | **本地脚本** tools/sales_analysis.py（纯 Python 标准库） |

## 使用的 Tool 及用途

| Tool | 在本项目中的用途 |
|---|---|
| now-time-info | 获取当前真实时间，时段判断的第一步（不猜时间） |
| campaign-calendar | 当月营销活动日历（Markdown 返回）；店长确认促销前核对官方排期避免撞车 |
| query-nearby-stores | 按城市+位置查附近门店；店长不知道 storeCode 时也用它查 |
| query-meals | 当前门店实时在售菜单（推荐的唯一数据来源） |
| query-meal-detail | 餐品套餐组成与替换选项 |
| list-nutrition-foods | 餐品营养数据（TOON 格式），用于食客方案的营养备注 |
| available-coupons | 麦麦省可领券列表（Markdown 返回） |
| query-store-coupons | 当前门店可用优惠券 |
| query-my-coupons | 我的卡包券（Markdown 返回） |
| auto-bind-coupons | 一键领取所有可领券（用户/店长确认后） |
| calculate-price | 对推荐组合做含券价格试算（单位：分，展示 ÷100） |

## 调用流程

```
【食客模式】
用户提问"现在吃啥"（可带人数/预算/口味/饮食偏好）
  → now-time-info            拿真实当前时间，粗分时段
  → campaign-calendar        查当月活动
  → query-nearby-stores      定位附近门店（用户未提供位置时先询问）
  → query-meals              拉当前门店实时在售列表（推荐的硬依据）
  → list-nutrition-foods     拿营养数据（TOON 格式）
  → query-store-coupons + available-coupons   看券；[确认] auto-bind-coupons 领券
  → calculate-price ×3       三个方案分别算券后价
  → 输出 3 方案 + 推荐理由 + 营养备注 + 合规声明

【店长模式】
店主粘贴当日销量 → 规范化写入 data/sales_<storeCode>.csv（storeCode 可经 query-nearby-stores 查）
  → tools/sales_analysis.py  本地分析：日报(环比/同期)/星期分布/Top餐品/高峰时段/备货建议/促销候选
  → 店长确认促销 → campaign-calendar 核对官方排期 → 记入 data/promotions.csv
```

## 业务价值

**食客侧**："到饭点不知道吃啥"是每天发生的高频决策。把时间感知、实时在售、活动、优惠券、营养五类信息一次串完，按人数/预算/口味输出现在就可执行的 3 个方案。

**店长侧**：小店店长普遍靠感觉备货、凭经验做活动。本 Skill 把"每天录一次销量"的低成本动作，变成日/周/节假日对比、偏弱日识别、促销候选与确认台账——促销必须店长点头才执行，避免 AI 擅自做经营决策。

## 实测验证

### 2026-10-24 14:28 脚本链路（Python 直连 MCP，到店自取，北京中关村）

| 步骤 | 工具 | 实测结果 |
|---|---|---|
| 1 | now-time-info | 返回 2026-10-24 14:28:50 (SATURDAY)，标准 JSON |
| 2 | campaign-calendar | 返回当月活动 Markdown（麦当劳 X PEACEMINUSONE 联名） |
| 3 | query-nearby-stores | 返回 5 家门店；首选善缘街店（storeCode=1950640，07:00-22:00 营业中） |
| 4 | query-meals | 返回 14 个在售分类（含「500 大卡套餐」6 款） |
| 5 | query-store-coupons + available-coupons | 门店可用：麦辣鸡腿堡三件套；可领：免费脆薯饼、11.9 元麦辣鸡腿堡 |
| 6 | calculate-price | 麦辣鸡腿汉堡三件套 x1 = 3350 分（¥33.5） |

### 2026-10-24 15:47 WorkBuddy 连接器链路

经 WorkBuddy 自定义连接器 mcd-mcp 调用：now-time-info（15:47:23 SATURDAY）、query-nearby-stores（中关村 5 店，含今日可约时段：下午茶 14:44-16:45、夜市 17:14-21:45）均真实返回。

### 2026-10-24 店长模式分析脚本（虚构演示数据 sales_sample.csv，6 周）

- 星期分布：周三均值 108.2 份/天，低于整体均值 38.5%（最偏弱）
- 促销候选：脚本输出「周三会员日」为首选（连续 3 周偏弱触发），周二为备选
- 高峰时段：12:00-12:59 销量最高（1426 份）
- 备货建议：按明天星期几的历史均值生成

### 实测中发现的关键事实（已写入 SKILL.md）

- 响应格式三种：标准 JSON（多数字具，文本内嵌 Markdown 说明需提取）、Markdown 直返（campaign-calendar / available-coupons / query-my-coupons / auto-bind-coupons）、TOON 紧凑格式（list-nutrition-foods）；
- query-nearby-stores 按位置搜索时 city+keyword 必填；到店自取（beType=1）不传 beCode；
- calculate-price 等交易类工具金额单位为"分"；
- 门店预约时段返回官方时段名（早餐/午餐/下午茶/夜市/宵夜），是时段划分的一手依据。

### 节日数据来源

data/holidays_2026.csv 中 2026 年农历节日公历日期经两个独立来源交叉核对：百度百科"2026年"词条（春节 2/17、清明 4/5、端午 6/19、中秋 9/25、重阳 10/18）与黄历网万年历（2026 年 10 月月历标注 18 日重阳节）。

完整测试脚本与输出见仓库 tools/ 目录；开发对话上下文见 workbuddy.md。
