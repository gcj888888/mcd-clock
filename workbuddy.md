# workbuddy.md — 麦门时钟开发对话记录

> 本文件记录「麦门时钟 mcd-clock」的完整开发过程。开发工具：腾讯 WorkBuddy（本会话即开发现场）。
> 参赛者：高中生，零基础。本文按"学习者实录"原则撰写：踩坑、决策、实测数据全部如实记录，不美化。

## 2026-10-24 13:46 — 读题

用户发来两个链接，要求精读后给出理解和三个方案。读取内容：
- WaytoAGI 1024 切磋大会「用餐」赛道（https://1024.waytoagi.com/tracks/dine）
- 麦当劳程序员创意开发大赛 GitHub 仓库（README、activityGuidelines.md、RANKING.md、CONTEST_DECLARATION.md）
- 麦当劳 MCP Server 工具清单（github.com/M-China/mcd-mcp-server，35 个工具）

分析结论（向用户输出）：
1. 这是"一个作品、两个奖池"的结构：WaytoAGI 侧人工评审（前三 3072/2048/1024 元，须用 WorkBuddy 制作），麦当劳侧按 GitHub Star 排名（前三巨无霸券+10240 积分，前 100 有周边+3000 积分）。
2. 时间极紧：WaytoAGI 10/25 16:00 截止，麦当劳 10/25 23:59 报名截止。
3. 竞争格局（按 100 个已报名项目名粗分类，推测数据）：省钱类约 21 个、整活类约 30 个最拥挤；派对类仅 5 个但出过第 3 名；「时间×餐品」方向几乎空白。
4. 给出三方案：A 考前补给站（学生营养推荐）、B 麦门团建王（派对五连链路）、C 麦门时钟（时段感知推荐）。

**用户决策：方案 C「麦门时钟」。**

## 14:03–14:10 — 搭骨架

- E 盘建项目目录 `E:\mcd-clock`，写 PROJECT.md 项目管控文件（目标/边界/计划/进展）。
- GitHub 连接器无建仓库权限（403），改用本机 gh CLI（已登录 gcj888888）创建公开仓库 `mcd-clock` 并推送 5 个规定文件：README.md、CONTEST_DECLARATION.md（官方原文未改）、MCP_INTEGRATION.md、mcp-config.example.json（环境变量占位符）、mcd-clock/SKILL.md。
- 探测 MCP 服务器连通性：无凭证 POST 返回 403（服务可达，拒绝未授权，符合预期）。

## 14:17 — 一次小插曲

用户截图询问"你说的是这个吗"——画面是「WaytoAGI 1024 超能 Coding 周末」的 API Key 控制台（$300 大模型额度）。澄清：那不是麦当劳 MCP 控制台，需要的是 open.mcd.cn/mcp 用手机号申请的 MCP Token。

## 14:19 — Token 到手，开始实测

- Token 写入 `~/.workbuddy/mcp.json`（mcd-mcp，streamablehttp，https://mcp.mcd.cn）。
- 写 `tools/list_tools.py` 实测 tools/list：HTTP 200，35 个工具全部拉到，schema 快照存档。

## 14:23–14:28 — 踩坑与修复（本文件最值得看的部分）

**坑 1：想当然地以为工具返回纯 JSON。** 第一次全链路测试，6 步里 4 步解析失败。看原始返回才发现：麦当劳 MCP 的响应有三种格式（后查官方文档 https://open.mcd.cn/mcp/doc 证实）：
- 多数工具：标准 JSON（success/code/message/data 外层），但文本里带 Markdown 说明前缀和尾巴，真实 JSON 嵌在中间；
- campaign-calendar / available-coupons / query-my-coupons / auto-bind-coupons：直接返回 Markdown 文本；
- list-nutrition-foods：TOON 紧凑格式（表头+数据行）。

**修复**：用 `json.JSONDecoder().raw_decode()` 从文本中 `{"success"` 起点解析第一个完整 JSON 对象，忽略前后缀。

**坑 2：到店自取场景的 beCode 规则。** 实测+官方文档确认：beType=1（到店自取）不传 beCode；只有得来速(5)/外送(2)/团餐(6)才需要。第一版 SKILL.md 没写清，已按实测修正。

**实测通过的全链路（2026-10-24 14:28，北京中关村，到店自取）**：
1. now-time-info → 2026-10-24 14:28:50 SATURDAY
2. campaign-calendar → 麦当劳 X PEACEMINUSONE 联名活动（Markdown）
3. query-nearby-stores → 5 家门店，首选善缘街店（storeCode=1950640，07:00-22:00 营业中）；预约时段返回官方时段名：早餐/午餐/下午茶/夜市/宵夜
4. query-meals → 14 个在售分类，含「500 大卡套餐」（6 款）
5. query-store-coupons → 麦辣鸡腿堡三件套可用券；available-coupons → 免费脆薯饼、11.9 元麦辣鸡腿堡可领
6. calculate-price → 麦辣鸡腿汉堡三件套 ¥33.5（3350 分，单位是分需 ÷100）

## 关键设计决策

1. **默认走"到店自取"链路**：不碰配送地址和下单，演示安全，查询类工具足够展示"真调用、能跑通"。
2. **时段划分不写死**：SKILL.md 里的时段分桶只是推荐框架，最终以 query-meals 实时在售和门店返回的官方时段名为准——这是从"预约时段接口返回官方时段名"这个实测发现得来的。
3. **合规红线写进 SKILL.md**：不贬低品牌、不与其他品牌对比、不做营养建议断言、默认不创建订单。
4. **店长模式不虚构 MCP 能力**：麦当劳 MCP 没有门店销量接口，销量数据明确设计为"店长每日录入本地 CSV + 本地脚本分析"，并在 README/MCP_INTEGRATION 里如实标注边界——宁可少吹能力，不让评委核验时发现货不对板。

## 2026-10-24 16:00 — 功能扩展：双模式升级

用户提出两类新需求（原文要求）：店长侧——每日销量记录与保存、节假日/每周 7 天销量动态分析、同期与环比对比、备货建议、淡季时段与节日前 7 天促销建议（店长确认后执行）、爆款清单；食客侧——语音/文字输入收集人数/预算/口味/饮食偏好、3 个下单推荐方案含推荐理由、每项热量营养备注。

实现过程：
1. **先查证再动手**：确认 MCP 35 个工具无销量接口后，确定"本地数据+本地分析"架构；2026 年农历节日日期（重阳节 10-18 等）经百度百科与黄历网两个独立来源交叉核对后才写入 holidays_2026.csv。
2. **写 tools/sales_analysis.py**（纯标准库）：日报（环比+上周同期）、星期分布、Top 餐品、高峰时段、备货建议、促销候选（节日前 7 天 + 连续 3 周偏弱日触发）。
3. **第一版跑出来发现设计缺陷**：4 个偏弱日全部被提议设会员日，不实用。改为按偏弱程度排序只给"首选+备选"，其余一句带过——周三（-38%）首选，正好命中用户举的场景。
4. **用 6 周虚构演示数据验证**（周三均值 108 份 vs 整体 176 份，偏弱 38.5%，触发会员日建议；高峰时段 12 点）。
5. SKILL.md 重写为双模式结构，README/MCP_INTEGRATION 同步更新；promotions.csv 台账模板就位；Skill 重新安装。

## 2026-10-24 16:12 — 食客模式全链路真实演示（补交演示材料）

用户授权"没有的数据合理模拟"，选择用**真实执行**代替虚构录屏（更经得起核验）。经 WorkBuddy 连接器完整跑了一遍食客模式，共 9 次真实调用：

now-time-info（16:12 周六）→ campaign-calendar（今日麦金喜抽奖/韩式蘸酱上新/明日龙焰堡预告）→ query-nearby-stores（善缘街店 1950640，183 米）→ query-meals（14 分类+实时价）→ query-store-coupons + available-coupons → calculate-price ×4 → list-nutrition-foods。

三个方案真实算价：① 麦辣鸡腿堡三件套×2 = ¥67（用券单份 ¥46→¥22.9，立减 ¥23.1）② 龙焰鸡腿堡三件套×2+芝士条 = ¥64.8（新品促销）③ 麦辣鸡腿堡+板烧+玉米杯+苹果片 = ¥66（热量约为①一半）。全部写进 demo/demo_transcript.md 和 demo/使用说明.md。

**自检结论（对照两份赛事规则）**：
- 麦当劳大赛：仓库 5 规定文件齐全✓ 公开✓ 创建时间在窗口内✓ 报名 Issue #1229 已官方回复"成功参赛"✓ **唯一缺口：Star=0，进排行榜需至少 1 个外部 Star（自己不能 star 自己）**
- WaytoAGI：作品链接✓ 使用说明✓（录屏选填）workbuddy.md 在仓库✓ 使用工具 WorkBuddy✓ **缺口：作品站提交需用户本人账号操作（10/25 16:00 截止）**

## 待办（交卷前）

- [x] WorkBuddy 连接器启用 mcd-mcp（15:47 已点信任，实测通过）
- [x] 麦当劳大赛报名 Issue（#1229，官方已回复成功参赛）
- [x] 演示材料（真实执行实录 + 使用说明，demo/ 目录）
- [ ] **用户操作：WaytoAGI 作品站提交（10/25 16:00 截止）**
- [ ] **用户操作：拉 1 个外部 Star（找同学/朋友点一下仓库）**
- [ ] 可选：真人录屏补充进 demo/
