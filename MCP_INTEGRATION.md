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

## 实测验证

真实调用验证记录见 workbuddy.md（开发对话上下文导出）。
