# 动画语法参数

本文保留花叔 huashu-art-motion 的八种参数化语法接口说明（MIT；署名和原许可见根目录 THIRD_PARTY_NOTICES.md）。只在选择某一种语法时阅读对应小节。IvanVideo 已内置运行时，不需要另装该 Skill。

先阅读 animation-production.md 了解使用入口、通用字段、safe 限制与口播 cue。所有片段经 scripts/render_animation.py 校验并渲染；示例时间仅作参数说明，实际按旁白和阅读时间安排。

#### t1_3b1b（3b1b / manim 讲解：公式、曲线、要点）

spec 级 data：无。

| kind | 字段 | 说明 | 示例 |
|---|---|---|---|
| `title` | `text`，`data.color`，`dur` | at 起 Write；再来一个 title 时旧标题上移淡出；太长先缩字号、再折两行 | `{"at":0,"kind":"title","text":"注意力就是加权平均"}` |
| `equation` | `data.tokens` 或 `text`，`dur`（首个 1.2s，之后 1.5s） | token：`{s, it?, col?, gap?, sub?, sup?, size?}`，`col` 写 manim 色名（`BLUE_C` `YELLOW` `GREEN_C` `TEAL_C` `RED_C`…）或 #hex。只给 text 时自动拆：单个字母斜体、连续字母（softmax）正体。第二个起从上一个 Transform 过来 | `{"at":1,"kind":"equation","text":"softmax(QK)V"}` |
| `point` | `text`，`dur` | 一句一行 Write，新的出来时旧的变灰。放不下时先让曲线让位（竖屏 50%→30%）、再缩字号（≥0.6 倍），还不够就新要点出来时整块上卷、最早的淡出（会告警） | `{"at":3,"kind":"point","text":"先算相似度"}` |
| `line` | `data.values`（等距 y）或 `data.points`（`[[x,y],…]`），`text`＝曲线标签，`data.color`，`dur` | 坐标系先 Create 再画曲线；第二条起从上一条形变过来。有 line 时横屏左文右图、竖屏上图下文 | `{"at":2,"kind":"line","text":"损失","data":{"values":[9,5,3,2,1.5]}}` |
| `highlight` | `data.index`（第几个 point，从 0 起，默认最新）或 `data.target:"equation"` | Indicate＋黄框留住 | `{"at":5,"kind":"highlight","data":{"index":0}}` |

最小 spec：
```json
{"grammar":"t1_3b1b","duration":6,"cues":[
  {"at":0,"kind":"title","text":"注意力就是加权平均"},
  {"at":1.2,"kind":"equation","text":"softmax(QK)V"},
  {"at":3,"kind":"point","text":"先算每个词和我有多像"},
  {"at":4.2,"kind":"point","text":"再按像的程度把信息加起来"}]}
```

#### t2_keynote_ui（发布会界面：功能卡、截图卡、大数字）

spec 级 data：`eyebrow`（标题上方小字）、`title`、`subtitle`、`accent`（强调色，默认 `#3d6bff`）。

| kind | 字段 | 说明 | 示例 |
|---|---|---|---|
| `title` | `text`/`sub` 覆盖 data.title/subtitle | at 起从模糊里浮出 | `{"at":0,"kind":"title"}` |
| `card` / `step` / `image`（同义） | `text` 卡标题，`sub` 说明，`image` 截图；`data.step` 指定编号；无图卡可加 `data.icon`（`wave memory agent clock phone layers chart code check play bolt lock`）、`data.value/prefix/suffix/decimals/label`（卡上计数） | 有图：一屏一张，截图等比 contain；无图：连着的最多 3 张并排一屏 | `{"at":2,"kind":"card","text":"一句话出图","sub":"不用写提示词","data":{"icon":"bolt"}}` |
| `highlight` | `data.rect=[x,y,w,h]`（相对截图 0..1），`text` 可选标签 | 框出当前截图卡的一块并压暗其余 | `{"at":5,"kind":"highlight","data":{"rect":[0.6,0.2,0.2,0.1]}}` |
| `number` | 见上方 number 口径 | 单独一屏 | `{"at":4,"kind":"number","text":"每月活跃用户","data":{"value":1.2,"decimals":1,"suffix":" 亿"}}` |

最小 spec：
```json
{"grammar":"t2_keynote_ui","duration":6,"data":{"title":"三个新功能"},"cues":[
  {"at":0,"kind":"title"},
  {"at":1.8,"kind":"card","text":"语音输入","sub":"说完就转成文字","data":{"icon":"wave"}},
  {"at":2.6,"kind":"card","text":"长期记忆","sub":"记得你上次说过什么","data":{"icon":"memory"}},
  {"at":3.4,"kind":"card","text":"自动执行","sub":"替你点完剩下的按钮","data":{"icon":"agent"}}]}
```

#### t3_finance_chart（经济学人式数据图）

spec 级 data：`title`、`unit`（副标题：指标与单位；放不下先缩再折两行）、`source`（左下来源；同上，并让开右下角标）、`badge?`（只有写了才画右下角标，如「示意数据」；真实数据别写）、`chart: "bar"|"line"|"candle"`、`series: [{label, value, color?}]` 或 K 线 `[{label, o, h, l, c}]`、`decimals`（柱/点标签，默认 1）、`prefix`、`suffix`、`highlight: {index, text, sub}`、`colors: {main, accent, dim}`、`upDown: "cn"`（红涨绿跌，默认）`|"us"`、`xAxis: "category"|"time"`（柱默认按类目每根写名字，折线/K 线默认按时间抽稀）。

| kind | 字段 | 说明 | 示例 |
|---|---|---|---|
| `title` | — | 版式先出（标题、副标题、来源） | `{"at":0,"kind":"title"}` |
| `bar` / `line` / `candle` | `dur`（默认按根数）；柱状图可写多个 bar，各带 `data.index`（数或数组）＝这几根在这一刻才长 | 坐标系→数据长出。柱一律从 0 起；折线/K 线纵轴不从 0 时副标题自动加「纵轴未从 0 开始」；负数柱的数值写在柱底下方、标注往下走；类目名放不下先缩字再错成两行，被标注的那根永远有名字；刻度按步长取小数位 | `{"at":1.2,"kind":"bar"}` |
| `highlight` | `text`/`sub` 覆盖 data.highlight，`data.index` 第几根 | at 这一帧标注圆点弹出，引线＋文字；斜向放会压到别的柱子或数值时改放这根正上方，顶上不够就自动加一档刻度 | `{"at":4,"kind":"highlight","data":{"index":2},"text":"最高"}` |
| `number` | 见上方 number 口径 | 图区上方专留一条，不压折线线头 | `{"at":5,"kind":"number","text":"最新收盘","data":{"value":259.97,"prefix":"¥","decimals":2}}` |

最小 spec：
```json
{"grammar":"t3_finance_chart","duration":6,"data":{"title":"三家公司的研发投入","unit":"2024 年，亿元","source":"来源：示意数据","badge":"示意数据","chart":"bar",
  "series":[{"label":"甲","value":120},{"label":"乙","value":86},{"label":"丙","value":43}]},"cues":[
  {"at":0,"kind":"title"},{"at":1,"kind":"bar"},{"at":3.5,"kind":"highlight","data":{"index":0},"text":"最多"}]}
```

#### y1_kurzgesagt（扁平科普：星球＋卫星节点＋尺度穿行）

spec 级 data：`center`（第一层中心星球的名字）、`flow: true`（节点串成一条链、信号依次流过、带序号，讲「先后」时用）。

| kind | 字段 | 说明 | 示例 |
|---|---|---|---|
| `title` | `text` | 顶部标题逐字上浮；第一个 highlight 或 enter 的 at 起 0.5s 淡出 | `{"at":0,"kind":"title","text":"一次搜索经历了什么"}` |
| `point` | `text`，`data.color` | 当前这一层的一个卫星节点＋标签胶囊。≤3 个排上半圈，≥4 个绕一整圈。标签按当前镜头夹在画内，长标签先缩字 | `{"at":1.4,"kind":"point","text":"分词"}` |
| `highlight` | `data.index`（只数当前层的 point，从 0 起，默认最新） | 相机推近那个节点，其余变暗，1.2s 推完 | `{"at":5,"kind":"highlight","data":{"index":1}}` |
| `enter` | `data.index`（钻进哪个节点，默认最新），`text`（新中心的名字，默认用节点名），`dur`（默认 1.6） | 尺度穿行：at 这一帧开始推进，约 at＋0.55×dur 满屏同色、切到新一层，at＋dur 新中心星球拉出完毕；之后的 point 都属于新一层（第一个新 point 的 at 写在 at＋dur 之后） | `{"at":4,"kind":"enter","data":{"index":0},"text":"分词器"}` |

最小 spec：
```json
{"grammar":"y1_kurzgesagt","duration":6,"data":{"center":"搜索引擎","flow":true},"cues":[
  {"at":0,"kind":"title","text":"一次搜索经历了什么"},
  {"at":1.2,"kind":"point","text":"抓取"},{"at":2,"kind":"point","text":"索引"},{"at":2.8,"kind":"point","text":"排序"},
  {"at":4.2,"kind":"highlight","data":{"index":2}}]}
```

#### y2_vox（拼贴桌面：截图、剪报、红线、荧光笔）

spec 级 data：无。

| kind | 字段 | 说明 | 示例 |
|---|---|---|---|
| `image` / `clip`（同义） | `image`，`text`＝下方黑底标签，`data.halftone: true` 转灰度网点 | at 起滑入桌面；等比放、不裁，加纸白边和胶带。横屏左→右排、竖屏上→下排，红线连起来 | `{"at":1,"kind":"image","image":"截图.png","text":"官网首页"}` |
| `title` | `text`（空的或纯空格会告警并跳过） | 黑底白字标签条，打字 13 字/秒 | `{"at":0,"kind":"title","text":"这件事有三条线索"}` |
| `point` | `text` | 横线索引卡，打字（间隔短会提速到最多 40 字/秒） | `{"at":4,"kind":"point","text":"发布时间比公告早一天"}` |
| `highlight` | `data.rect=[x,y,w,h]`（相对**当前这张图** 0..1） | 荧光笔扫过→红圈→相机推近。rect 目测常偏 20–30%，先 `--stills` 核 | `{"at":2.5,"kind":"highlight","data":{"rect":[0.1,0.2,0.3,0.1]}}` |

最小 spec（不需要截图也能用：标题＋索引卡）：
```json
{"grammar":"y2_vox","duration":6,"cues":[
  {"at":0,"kind":"title","text":"这次涨价的三条线索"},
  {"at":1.6,"kind":"point","text":"供应商先发了通知"},
  {"at":3.4,"kind":"point","text":"两周后官网改了价格"}]}
```

#### y3_whiteboard（白板手绘：说一句写一句、画图标、圈重点）

spec 级 data：无。

| kind | 字段 | 说明 | 示例 |
|---|---|---|---|
| `title` | `text` | 7.5 字/秒起，赶不上下一个 cue 自动提速 | `{"at":0,"kind":"title","text":"为什么要写测试"}` |
| `point` | `text` | 先画小圈当项目符号再写，16 字/秒起 | `{"at":1.5,"kind":"point","text":"改代码时有人替你盯着"}` |
| `draw` | `data.icon`（`person cat network doc chat bulb check cross screen stack gear target clock chart`；写错会告警、只写说明字），`text`＝图标下的说明（放不下先缩字号），`data.arrow: false` 不画箭头 | 和刚写的那条字并排；连续的 draw 用橙箭头连起来 | `{"at":2.5,"kind":"draw","text":"自动检查","data":{"icon":"check"}}` |
| `image` | `image` | 之字形揭开＋手绘框，等比不裁 | `{"at":4,"kind":"image","image":"草图.png"}` |
| `highlight` | `data.index`（第几个，从 0 起），`data.target`: `"title"` / `"draw"` / `"image"`（默认数 point），`data.style: "underline"` | 橙圈圈住或划线；不写 index = 最新写出的那一条 | `{"at":5,"kind":"highlight","data":{"index":0,"style":"underline"}}` |

最小 spec：
```json
{"grammar":"y3_whiteboard","duration":6,"cues":[
  {"at":0,"kind":"title","text":"为什么要写测试"},
  {"at":1.5,"kind":"point","text":"改代码时有人替你盯着"},
  {"at":2.7,"kind":"draw","text":"自动检查","data":{"icon":"check"}},
  {"at":4.4,"kind":"highlight","data":{"index":0}}]}
```

#### y4_storytime（几何角色讲故事：气泡、反应特写、插入镜头）

spec 级 data：无（有 `window.VO_ENV` 就按口播包络对口型，没有就按字数合成）。safe 只让字（气泡、插入镜头的大字）；角色、桌子、反应特写的脸是图形，竖屏下会伸进字幕带——字幕压在身体上读得清，但别指望它们让开。

| kind | 字段 | 说明 | 示例 |
|---|---|---|---|
| `point` / `title`（同义） | `text`＝口播原文（定张嘴时长，≈6.5 字/秒），`sub`＝气泡里实际显示的短句（≤12 字最好；不写才显示 text），`data.pose`: `talk` / `point` / `shrug` / `type` | at 这一帧气泡弹出、开始张嘴 | `{"at":0.1,"kind":"point","text":"我让它帮我改个错别字，","sub":"就改一个字"}` |
| `highlight` | `data.mark`（默认「？」） | 「？」「！」弹出＋摊手担心 | `{"at":4,"kind":"highlight","data":{"mark":"！"}}` |
| `react` | `dur`（从 at 起算，默认到下一个 cue） | 跳到反应大特写：死鱼眼＋汗滴，一言不发 | `{"at":3,"kind":"react"}` |
| `insert` | `sub`＝他在电脑上打的那一行（长了折行，最多 3 行），`text`＝砸出来的大字，`data.hit`（**绝对秒**，默认 at+1.3，没有 sub 时 at+0.4），`data.count`＋`data.unit`（右上计数器在砸出时停在这个数），`data.app`（窗口标题，默认「AI助手」），`dur`（从 at 起算，默认到下一个 cue） | 切到桌上电脑的屏幕特写：打字→回复像代码墙越滚越快→大字砸出 | `{"at":2,"kind":"insert","sub":"改个错别字","text":"改了 40 个文件","data":{"hit":3.4}}` |

最小 spec：
```json
{"grammar":"y4_storytime","duration":6,"cues":[
  {"at":0.1,"kind":"point","text":"我让它帮我改一个错别字，","sub":"就改一个字"},
  {"at":2,"kind":"insert","sub":"把「的」改成「得」","text":"改了 40 个文件","data":{"hit":3.4}},
  {"at":4.4,"kind":"react"}]}
```

#### y5_kinetic_type（动态文字：一个 cue 一页）

spec 级 data：`palette: [[底色, 字色], …]`（按页轮换）。

| kind | 字段 | 说明 | 示例 |
|---|---|---|---|
| `title` / `point` | `text` 主词（太长自动缩字号、最多两行），`sub` 辅句，`data.label`（左上小标签），`data.key`（辅句里要着色的那个词），`data.num`（背景巨型序号） | 主词在 at 这一帧砸进来，换页是色带擦除（at 前 0.3s 开始）。两个以上 point = 清单：画进度轨＋背景巨型序号 | `{"at":1.8,"kind":"point","text":"慢","sub":"每次只改一处","data":{"label":"01","key":"一处"}}` |
| `number` | 见上方 number 口径 | 一页大数字 | `{"at":4,"kind":"number","sub":"一次跑通的比例","data":{"value":87.5,"decimals":1,"suffix":"%"}}` |
| `highlight` | `data.word`（主词里的词；不给就刷整个主词） | 荧光笔＋放大一下；荧光笔和字同色（深蓝底黄字页）时笔下的字反白成底色。word 不在主词里会告警、什么都不做（辅句里的词用 `data.key`） | `{"at":3,"kind":"highlight","data":{"word":"慢"}}` |

最小 spec：
```json
{"grammar":"y5_kinetic_type","duration":5,"cues":[
  {"at":0,"kind":"title","text":"慢就是快"},
  {"at":1.8,"kind":"point","text":"慢","sub":"每次只改一处","data":{"key":"一处"}},
  {"at":3.3,"kind":"point","text":"快","sub":"一次就跑通","data":{"key":"跑通"}}]}
```

### 样例（`scripts/engine/examples/`）

```sh
cd <skill>/scripts
uv run --with playwright python engine/render.py --spec engine/examples/t3_finance_chart.json --out t3.mp4   # 英伟达五个财年营收（10-K 真实数据，无示意角标）
uv run --with playwright python engine/render.py --spec engine/examples/t2_keynote_ui.json   --out t2.mp4   # 教程：两张截图进玻璃卡＋框出时间轴
uv run --with playwright python engine/render.py --spec engine/examples/t1_3b1b.json         --out t1.mp4   # 梯度下降：公式＋损失曲线＋三个要点
uv run --with playwright python engine/render.py --spec engine/examples/y2_vox.json          --out y2.mp4   # 横图＋竖图贴桌面、荧光笔＋红圈＋推近到落定的收盘价
uv run --with playwright python engine/render.py --spec engine/examples/y3_whiteboard.json   --out y3.mp4   # 白板：标题＋三条要点＋圈重点＋揭开截图
# 另有 y1_kurzgesagt / y4_storytime / y5_kinetic_type.json；样例素材在 examples/assets/，都是 t3 自己渲出的终帧（数字已落定、无播放条、无路径）
```

### 给管线导演的提醒

- 一段动画别塞太多 cue：按第一节的镜头时长，3–8 秒的片段放 2–5 个 cue 最舒服；cue 太密，写字会被迫提速、相机来不及到位。
- 画面里有字的语法（t1/t3/y3/y5）会和管线的烧录字幕抢视线，叠层时把字幕挪开或这段不烧。
- 透明模式（`--alpha`）只去掉背景层，元素本身的阴影还在；y2 的纸片、t2 的玻璃卡在透明底上读作「浮在画面上的卡片」。t3 是白纸黑字，透明底下字带一圈白色光晕，叠深色画面也读得清；t1 的白字带深色光晕。
- **竖屏里贴截图，要框口播正在念的那半句。** 竖屏桌面上一张截图约 900px 宽，网页里 16px 的正文要推近 2–2.5 倍才看得清；框住整段宽字（框宽接近画宽）时红圈放不下，镜头就推不进去。一句话跨两行就拆成两个 highlight，各对一个关键词（2026-10-04 实测：拆开后推近 2.4 倍，字高约 50px）。rect 目测常偏 20–30%，先 `--stills` 渲一张核。
- **语法文件里的步进动画要从 at 起算。** 「一拍二」之类的步进如果按绝对时间网格取整（`MO.step(t, 12)`），元素会比 at 早最多一格露出（30fps 下早 2 帧）。写成 `MO.step(t − at, 12)`，at 这一帧才是第一帧。y4 的角色帧仍按绝对 24fps 取，cue 落点可能差 1 帧，用前先核。

---
