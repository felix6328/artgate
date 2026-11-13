# ArtGate 离线评测结果

评测脚本：`eval/measure.py` 的入口为 `scripts/run_eval.py`。
所有数字均由本次运行实测，没有手工填写。

**金标状态：** 检索金标为 `auto_drafted_needs_review`，须经作者审阅后才能作为面试口径。
审阅说明见 `eval/GOLD_QUERIES_README.md`。

## 1. 检索

- 文本查询条数：全部 87（中文 54，英文 33）；以图搜图 8。

| 分组 | n | Recall@5 | Recall@10 | nDCG@10 | MRR |
| --- | --- | --- | --- | --- | --- |
| 语义 · 全部文本 | 87 | 0.5304 (n=87) | 0.6086 (n=87) | 0.5824 (n=87) | 0.5962 (n=87) |
| 语义 · 中文 | 54 | 0.4783 (n=54) | 0.5548 (n=54) | 0.5415 (n=54) | 0.5559 (n=54) |
| 语义 · 英文 | 33 | 0.6158 (n=33) | 0.6967 (n=33) | 0.6493 (n=33) | 0.6621 (n=33) |
| 语义 · 以图搜图 | 8 | 0.9375 (n=8) | 1.0000 (n=8) | 0.9738 (n=8) | 1.0000 (n=8) |
| 文件名基线 · 全部文本 | 87 | 0.4894 (n=87) | 0.5195 (n=87) | 0.5435 (n=87) | 0.5776 (n=87) |
| 文件名基线 · 中文 | 54 | 0.3262 (n=54) | 0.3355 (n=54) | 0.3354 (n=54) | 0.3750 (n=54) |
| 文件名基线 · 英文 | 33 | 0.7564 (n=33) | 0.8206 (n=33) | 0.8841 (n=33) | 0.9091 (n=33) |

### 检索时延（含本次进程内已加载模型后的查询）

- 样本 n=95：mean=47.01 ms，P50=48.99 ms，**P95=58.34 ms**，max=71.01 ms。
- 机器：见下方「环境」。第一次加载模型的时间不计入上述 P95（已先 warmup 一次）。

### 和文件名基线的对比（实测，必须一起讲）

- 中文文本：语义 Recall@10 = 0.5548，文件名基线 = 0.3355。中文查询对上英文文件名本来就弱，这是多模态检索真正要补的增量。
- 英文文本：语义 Recall@10 = 0.6967，文件名基线 = 0.8206。英文查询经常直接出现在 Kenney 英文文件名里（apple、pistol、wheelchair），精确词匹配会赢；不能把语义检索说成「全面优于文件名」。
- 以图搜图 8 条 Recall@10 = 1.0，其中查询图就是库内预览，偏乐观，单独不能当产品效果宣传。
- 一批中文兵器查询（「一把剑」「圆形盾牌」「长矛」等）和英文 `a sword` Recall@10 = 0：返回的往往是刀或其它近形物体。3D 用的是软件等轴测预览，不是官方渲染图；金标把「剑」和「刀」分开，这是有意识的难点，不是事后改题。


## 2. 预检（规则层）

视觉层（VLM）本次默认未调用，不报告视觉精确率 / 召回率，简历该项保持占位。

- 金标条数 18，实际评测 18。
- 宏平均 Precision=1.0000，Recall=1.0000，F1=1.0000（对各检查项简单平均，检查项样本量很小）。
- **误拦率**（should_block=false 却 overall=block）：0 / 9 = 0.0000。
- **漏放率**（should_block=true 却 overall≠block）：0 / 8 = 0.0000。
- 单资产规则预检耗时 n=18：mean=102.33 ms，P50=149.43 ms，**P95=198.72 ms**，max=237.41 ms。

| 检查项 | TP | FP | FN | TN | Precision | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `file_size` | 1 | 0 | 0 | 5 | 1.0000 | 1.0000 | 1.0000 |
| `format` | 1 | 0 | 0 | 6 | 1.0000 | 1.0000 | 1.0000 |
| `gltf_valid` | 1 | 0 | 0 | 8 | 1.0000 | 1.0000 | 1.0000 |
| `image_max_side` | 1 | 0 | 0 | 3 | 1.0000 | 1.0000 | 1.0000 |
| `image_power_of_two` | 1 | 0 | 0 | 3 | 1.0000 | 1.0000 | 1.0000 |
| `naming` | 2 | 0 | 0 | 14 | 1.0000 | 1.0000 | 1.0000 |
| `poly_budget` | 1 | 0 | 0 | 6 | 1.0000 | 1.0000 | 1.0000 |
| `texture_power_of_two_3d` | 1 | 0 | 0 | 5 | 1.0000 | 1.0000 | 1.0000 |

## 3. 环境与成本

- 嵌入模型：OpenCLIP `xlm-roberta-base-ViT-B-32` / `laion5b_s13b_b90k`，device=cpu。
- OS=Linux-6.12.113+-x86_64-with-glibc2.41 Python=3.13.5 CPU=x86_64 nproc=8 MemTotal:       16386416 kB
- 本地嵌入 API 费用为 0。VLM 未配置时费用为 0。
- 费用日志汇总：`{"by_kind": [{"kind": "embed_image", "n": 239, "total_ms": 17688.424612990275, "avg_ms": 74.0101448242271, "total_cny": 0.0, "n_ok": 239}, {"kind": "embed_load", "n": 3, "total_ms": 21544.253089999984, "avg_ms": 7181.417696666661, "total_cny": 0.0, "n_ok": 3}, {"kind": "embed_text", "n": 89, "total_ms": 3057.2689339951467, "avg_ms": 34.35133633702412, "total_cny": 0.0, "n_ok": 89}, {"kind": "vlm_mock", "n": 2, "total_ms": 0.06417799886548892, "avg_ms": 0.03208899943274446, "total_cny": 0.0, "n_ok": 2}], "note": "estimated_cny 对本地嵌入为 0；VLM 若未实际调用则为 0。不要把假设单价写成实测账单。"}`

## 4. 限制（必须和数字一起讲）

- 检索金标是自动起草、**未经作者审阅**的；相关集可能过宽或过窄。
- 样本规模小（检索几十条查询、预检几十个注入样本），区间波动会很大，不能外推到生产库。
- 资产来自公开 CC0 / 按模型许可的样本，风格以 Kenney 低模和 Poly Haven 写实为主，不能代表二次元或项目组私有风格。
- 3D 检索用的是本仓库软件渲染的等轴测预览，不是引擎内截图或美术官方预览，域偏移会影响效果。
- 以图搜图的若干条用库内预览搜自己，偏乐观。
- 没有真实项目组用户的线上指标（点击率、申诉率）。
- 未测真实 VLM，视觉层数字不得填写。

## 5. 逐条检索结果摘要

| id | 查询 | 语言 | R@10 | nDCG@10 | n_rel | 前 3 个结果 |
| --- | --- | --- | --- | --- | --- | --- |
| zh-001 | 一把剑 | zh | 0.0000 | 0.0000 | 1 | `stylized_mobile:kenney:weapon/knife_sharp.glb, stylized_mobile:kenney:weapon/knife_smooth.glb, stylized_mobile:kenney:weapon/knifeRound_sharp.glb` |
| zh-002 | 圆形盾牌 | zh | 0.0000 | 0.0000 | 1 | `stylized_mobile:kenney:food/pot-stew-lid.glb, stylized_mobile:kenney:mini-forest/target.glb, stylized_mobile:kenney:food/pot-lid.glb` |
| zh-003 | 长方形盾牌 | zh | 0.0000 | 0.0000 | 1 | `stylized_mobile:kenney:food/cutting-board.glb, stylized_mobile:kenney:food/popsicle-stick.glb, stylized_mobile:kenney:ui/UI Pack/button_rectangle_depth_line.png` |
| zh-004 | 长矛 | zh | 0.0000 | 0.0000 | 1 | `stylized_mobile:kenney:food/cooking-knife.glb, stylized_mobile:kenney:food/chopstic-decorative.glb, stylized_mobile:kenney:weapon/knife_sharp.glb` |
| zh-005 | 一把弓 | zh | 0.0000 | 0.0000 | 2 | `stylized_mobile:kenney:mini-forest/target.glb, stylized_mobile:kenney:castle/siege-ballista-demolished.glb, stylized_mobile:kenney:mini-forest/fence.glb` |
| zh-006 | 一支箭 | zh | 0.0000 | 0.0000 | 2 | `stylized_mobile:kenney:food/cooking-knife.glb, stylized_mobile:kenney:food/corn-dog.glb, stylized_mobile:kenney:food/whole-ham.glb` |
| zh-007 | 兽人角色 | zh | 0.0000 | 0.0000 | 1 | `stylized_mobile:kenney:2d/Toon Characters/character_zombie_attack0.png, stylized_mobile:kenney:mini-dungeon/character-human.glb, stylized_mobile:kenney:2d/Toon Characters/character_zombie_talk.png` |
| zh-008 | 人类角色 | zh | 0.0000 | 0.0000 | 1 | `stylized_mobile:kenney:2d/Toon Characters/character_femaleAdventurer_hurt.png, stylized_mobile:kenney:2d/Toon Characters/character_femaleAdventurer_show.png, stylized_mobile:kenney:2d/Toon Characters/character_femaleAdventurer_attack0.png` |
| zh-009 | 女性角色 | zh | 0.1765 | 0.9266 | 51 | `stylized_mobile:kenney:2d/Toon Characters/character_femaleAdventurer_walk7.png, stylized_mobile:kenney:2d/Toon Characters/character_femaleAdventurer_walk3.png, stylized_mobile:kenney:2d/Toon Characters/character_femaleAdventurer_walk4.png` |
| zh-010 | 男性角色 | zh | 0.0000 | 0.0000 | 6 | `stylized_mobile:kenney:2d/Toon Characters/character_femaleAdventurer_attack0.png, stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_attack2.png, stylized_mobile:kenney:2d/Toon Characters/character_femaleAdventurer_walk4.png` |
| zh-011 | 轮椅 | zh | 1.0000 | 1.0000 | 4 | `stylized_mobile:kenney:mini-characters/wheelchair.glb, stylized_mobile:kenney:mini-characters/wheelchair-deluxe.glb, stylized_mobile:kenney:mini-characters/wheelchair-power.glb` |
| zh-012 | 宝箱 | zh | 0.0000 | 0.0000 | 2 | `stylized_mobile:kenney:platformer/lock.glb, stylized_mobile:kenney:mini-characters/aid-defibrillator-red.glb, stylized_mobile:kenney:castle/tower-square.glb` |
| zh-013 | 金币 | zh | 1.0000 | 0.4307 | 1 | `stylized_mobile:kenney:food/egg-cooked.glb, stylized_mobile:kenney:food/cheese.glb, stylized_mobile:kenney:platformer/coin-gold.glb` |
| zh-014 | 木桶 | zh | 0.3333 | 0.1480 | 3 | `stylized_mobile:kenney:castle/wall-corner-half-tower.glb, stylized_mobile:kenney:castle/tower-base.glb, stylized_mobile:kenney:food/steamer.glb` |
| zh-015 | 苹果 | zh | 1.0000 | 1.0000 | 2 | `stylized_mobile:kenney:food/apple.glb, stylized_mobile:kenney:food/apple-half.glb, stylized_mobile:kenney:food/tomato.glb` |
| zh-016 | 香蕉 | zh | 1.0000 | 1.0000 | 1 | `stylized_mobile:kenney:food/banana.glb, stylized_mobile:kenney:food/corn.glb, stylized_mobile:kenney:food/popsicle.glb` |
| zh-017 | 汉堡 | zh | 1.0000 | 0.9829 | 4 | `stylized_mobile:kenney:food/burger-cheese-double.glb, stylized_mobile:kenney:food/burger.glb, stylized_mobile:kenney:food/burger-cheese.glb` |
| zh-018 | 生日蛋糕 | zh | 1.0000 | 0.9779 | 3 | `stylized_mobile:kenney:food/cake-birthday.glb, stylized_mobile:kenney:food/cake.glb, stylized_mobile:kenney:food/sub.glb` |
| zh-019 | 一棵树 | zh | 1.0000 | 0.9469 | 3 | `stylized_mobile:kenney:mini-forest/tree-high.glb, stylized_mobile:kenney:platformer/tree.glb, stylized_mobile:kenney:castle/tree-large.glb` |
| zh-020 | 帐篷 | zh | 1.0000 | 0.3562 | 1 | `stylized_mobile:kenney:castle/tower-hexagon-roof-secondary.glb, stylized_mobile:kenney:ui/UI Pack/slide_hangle.png, stylized_mobile:kenney:food/rice-ball.glb` |
| zh-021 | 弓箭手 | zh | 0.0000 | 0.0000 | 1 | `stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_attack2.png, stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_climb1.png, stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_switch0.png` |
| zh-022 | 攻城投石机 | zh | 0.0000 | 0.0000 | 4 | `stylized_mobile:kenney:platformer/lever.glb, stylized_mobile:kenney:castle/siege-tower.glb, stylized_mobile:kenney:castle/wall-narrow-stairs-rail.glb` |
| zh-023 | 攻城槌 | zh | 0.0000 | 0.0000 | 2 | `stylized_mobile:kenney:mini-forest/flag.glb, stylized_mobile:kenney:castle/flag-pennant.glb, stylized_mobile:kenney:castle/flag.glb` |
| zh-024 | 手枪 | zh | 1.0000 | 1.0000 | 2 | `stylized_mobile:kenney:weapon/pistol.glb, stylized_mobile:kenney:weapon/pistolSilencer.glb, stylized_mobile:kenney:weapon/shotgun.glb` |
| zh-025 | 狙击枪 | zh | 1.0000 | 1.0000 | 2 | `stylized_mobile:kenney:weapon/sniperSand.glb, stylized_mobile:kenney:weapon/sniper.glb, stylized_mobile:kenney:weapon/machinegunLauncher.glb` |
| zh-026 | 火箭筒 | zh | 0.6667 | 0.4525 | 3 | `stylized_mobile:kenney:weapon/ammo_rocketModern.glb, stylized_mobile:kenney:weapon/rocketlauncherModern.glb, stylized_mobile:kenney:weapon/ammo_shotgun.glb` |
| zh-027 | 手榴弹 | zh | 0.5000 | 0.3183 | 4 | `stylized_mobile:kenney:weapon/ammo_machinegunLauncher.glb, stylized_mobile:kenney:weapon/ammo_uzi.glb, stylized_mobile:kenney:weapon/grenadeSmoke.glb` |
| zh-028 | 金色冲锋枪 | zh | 0.5000 | 0.7114 | 8 | `stylized_mobile:kenney:weapon/uziLongSilencerGold.glb, stylized_mobile:kenney:weapon/sniperSand.glb, stylized_mobile:kenney:weapon/uziSilencerGold.glb` |
| zh-029 | 矩形按钮 | zh | 1.0000 | 1.0000 | 10 | `stylized_mobile:kenney:ui/UI Pack/button_rectangle_depth_gradient.png, stylized_mobile:kenney:ui/UI Pack/button_rectangle_depth_gloss.png, stylized_mobile:kenney:ui/UI Pack/button_rectangle_gloss.png` |
| zh-030 | 圆形按钮 | zh | 0.8000 | 0.7949 | 10 | `stylized_mobile:kenney:ui/UI Pack/button_round_depth_gradient.png, stylized_mobile:kenney:platformer/spring.glb, stylized_mobile:kenney:ui/UI Pack/button_round_depth_border.png` |
| zh-031 | 横向滑动条 | zh | 0.0000 | 0.0000 | 6 | `stylized_mobile:kenney:food/bacon-raw.glb, stylized_mobile:kenney:food/bacon.glb, stylized_mobile:kenney:platformer/spike-block-wide.glb` |
| zh-032 | 勾选框 | zh | 0.1667 | 0.2048 | 12 | `stylized_mobile:kenney:ui/UI Pack/button_rectangle_border.png, stylized_mobile:kenney:ui/UI Pack/icon_square.png, stylized_mobile:kenney:ui/UI Pack/check_square_color_cross.png` |
| zh-033 | 奖杯图标 | zh | 1.0000 | 1.0000 | 1 | `stylized_mobile:kenney:icons/Game Icons/trophy.png, stylized_mobile:kenney:food/cocktail.glb, stylized_mobile:kenney:icons/Game Icons/joystickUp.png` |
| zh-034 | 星星图标 | zh | 1.0000 | 1.0000 | 2 | `stylized_mobile:kenney:ui/UI Pack/star.png, stylized_mobile:kenney:icons/Game Icons/star.png, stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_duck.png` |
| zh-035 | 游戏手柄图标 | zh | 0.4000 | 0.2001 | 5 | `stylized_mobile:kenney:icons/Game Icons/exitLeft.png, stylized_mobile:kenney:icons/Game Icons/exitRight.png, stylized_mobile:kenney:icons/Game Icons/leaderboardsSimple.png` |
| zh-036 | 纸杯蛋糕 | zh | 1.0000 | 1.0000 | 1 | `stylized_mobile:kenney:food/cupcake.glb, stylized_mobile:kenney:food/frappe.glb, stylized_mobile:kenney:icons/Game Icons/basket.png` |
| zh-037 | 牛油果 | zh | 0.0000 | 0.0000 | 2 | `stylized_mobile:kenney:food/pear.glb, stylized_mobile:kenney:food/pear-half.glb, stylized_mobile:kenney:food/pineapple.glb` |
| zh-038 | 西瓜 | zh | 1.0000 | 0.3869 | 1 | `stylized_mobile:kenney:food/pear.glb, stylized_mobile:kenney:food/strawberry.glb, stylized_mobile:kenney:food/tomato.glb` |
| zh-039 | 吊桥 | zh | 0.0000 | 0.0000 | 4 | `stylized_mobile:kenney:castle/flag-wide.glb, stylized_mobile:kenney:platformer/fence-rope.glb, stylized_mobile:kenney:mini-forest/fence.glb` |
| zh-040 | 城堡旗帜 | zh | 0.6000 | 0.6552 | 5 | `stylized_mobile:kenney:castle/flag.glb, stylized_mobile:kenney:castle/flag-wide.glb, stylized_mobile:kenney:platformer/flag.glb` |
| zh-041 | 梯子 | zh | 1.0000 | 0.8066 | 2 | `stylized_mobile:kenney:platformer/ladder.glb, stylized_mobile:kenney:platformer/ladder-long.glb, stylized_mobile:kenney:castle/siege-tower.glb` |
| zh-042 | 地牢里的陷阱 | zh | 0.0000 | 0.0000 | 1 | `stylized_mobile:kenney:mini-dungeon/wall.glb, stylized_mobile:kenney:mini-dungeon/wall-narrow.glb, stylized_mobile:kenney:food/bowl-broth.glb` |
| zh-043 | 火焰喷射器 | zh | 1.0000 | 0.6934 | 2 | `stylized_mobile:kenney:weapon/rocketlauncherModern.glb, stylized_mobile:kenney:weapon/flamethrower_long.glb, stylized_mobile:kenney:weapon/flamethrower_short.glb` |
| zh-044 | 卡通风格的女性冒险者 | zh | 0.1778 | 0.8604 | 45 | `stylized_mobile:kenney:2d/Toon Characters/character_femaleAdventurer_walk3.png, stylized_mobile:kenney:2d/Toon Characters/character_femaleAdventurer_walk4.png, stylized_mobile:kenney:2d/Toon Characters/character_femaleAdventurer_walk7.png` |
| zh-045 | 音乐开关图标 | zh | 0.5000 | 0.3869 | 2 | `stylized_mobile:kenney:icons/Game Icons/exitLeft.png, stylized_mobile:kenney:icons/Game Icons/musicOn.png, stylized_mobile:kenney:icons/Game Icons/exitRight.png` |
| en-001 | a sword | en | 0.0000 | 0.0000 | 1 | `stylized_mobile:kenney:weapon/knifeRound_sharp.glb, stylized_mobile:kenney:weapon/knife_sharp.glb, stylized_mobile:kenney:weapon/knife_smooth.glb` |
| en-002 | a round shield | en | 1.0000 | 0.3869 | 1 | `stylized_mobile:kenney:food/pot-lid.glb, stylized_mobile:kenney:mini-forest/target.glb, stylized_mobile:kenney:food/pot-stew-lid.glb` |
| en-003 | an orc character | en | 1.0000 | 0.3562 | 1 | `stylized_mobile:kenney:2d/Toon Characters/character_zombie_switch0.png, stylized_mobile:kenney:2d/Toon Characters/character_zombie_attack0.png, stylized_mobile:kenney:mini-characters/character-male-f.glb` |
| en-004 | birthday cake | en | 1.0000 | 0.9779 | 3 | `stylized_mobile:kenney:food/cake-birthday.glb, stylized_mobile:kenney:food/cake.glb, stylized_mobile:kenney:food/sub.glb` |
| en-005 | a pistol | en | 1.0000 | 0.8772 | 2 | `stylized_mobile:kenney:weapon/pistol.glb, stylized_mobile:kenney:weapon/machinegunLauncher.glb, stylized_mobile:kenney:weapon/shotgun.glb` |
| en-006 | sniper rifle | en | 1.0000 | 1.0000 | 2 | `stylized_mobile:kenney:weapon/sniperSand.glb, stylized_mobile:kenney:weapon/sniper.glb, stylized_mobile:kenney:weapon/uziLongSilencer.glb` |
| en-007 | wooden barrel | en | 1.0000 | 0.5193 | 3 | `stylized_mobile:kenney:castle/wall-corner-half-tower.glb, stylized_mobile:kenney:castle/tower-base.glb, stylized_mobile:kenney:food/steamer.glb` |
| en-008 | treasure chest | en | 0.0000 | 0.0000 | 2 | `stylized_mobile:kenney:platformer/lock.glb, stylized_mobile:kenney:castle/wall-corner-half-tower.glb, stylized_mobile:kenney:mini-characters/aid-defibrillator-red.glb` |
| en-009 | a cartoon tree | en | 1.0000 | 0.8855 | 3 | `stylized_mobile:kenney:mini-forest/tree-high.glb, stylized_mobile:kenney:castle/tree-large.glb, stylized_mobile:kenney:platformer/tree.glb` |
| en-010 | wheelchair | en | 1.0000 | 1.0000 | 4 | `stylized_mobile:kenney:mini-characters/wheelchair.glb, stylized_mobile:kenney:mini-characters/wheelchair-power.glb, stylized_mobile:kenney:mini-characters/wheelchair-power-deluxe.glb` |
| en-011 | UI button | en | 0.2667 | 0.8482 | 30 | `stylized_mobile:kenney:ui/UI Pack/button_rectangle_gloss.png, stylized_mobile:kenney:ui/UI Pack/button_rectangle_depth_gradient.png, stylized_mobile:kenney:ui/UI Pack/button_rectangle_depth_gloss.png` |
| en-012 | hamburger | en | 1.0000 | 0.9829 | 4 | `stylized_mobile:kenney:food/burger.glb, stylized_mobile:kenney:food/burger-cheese-double.glb, stylized_mobile:kenney:food/burger-cheese.glb` |
| en-013 | bow and arrow | en | 0.0000 | 0.0000 | 2 | `stylized_mobile:kenney:castle/siege-ballista-demolished.glb, stylized_mobile:kenney:icons/Game Icons/upRight.png, stylized_mobile:kenney:icons/Game Icons/upLeft.png` |
| en-014 | siege catapult | en | 0.7000 | 0.7343 | 10 | `stylized_mobile:kenney:castle/siege-tower-demolished.glb, stylized_mobile:kenney:castle/siege-trebuchet.glb, stylized_mobile:kenney:castle/siege-catapult.glb` |
| en-015 | gold uzi | en | 0.6250 | 0.8348 | 8 | `stylized_mobile:kenney:weapon/uziLongSilencerGold.glb, stylized_mobile:kenney:weapon/uziGold.glb, stylized_mobile:kenney:weapon/uziSilencerGold.glb` |
| en-016 | female character | en | 0.0784 | 0.3063 | 51 | `stylized_mobile:kenney:2d/Toon Characters/character_zombie_think.png, stylized_mobile:kenney:2d/Toon Characters/character_zombie_walk1.png, stylized_mobile:kenney:2d/Toon Characters/character_zombie_walk5.png` |
| en-017 | a tent | en | 1.0000 | 0.3869 | 1 | `stylized_mobile:kenney:castle/tower-hexagon-roof-secondary.glb, stylized_mobile:kenney:castle/tree-trunk.glb, stylized_mobile:kenney:food/rice-ball.glb` |
| en-018 | apple | en | 1.0000 | 1.0000 | 2 | `stylized_mobile:kenney:food/apple.glb, stylized_mobile:kenney:food/apple-half.glb, stylized_mobile:kenney:food/tomato.glb` |
| en-019 | avocado | en | 0.0000 | 0.0000 | 2 | `stylized_mobile:kenney:food/pear-half.glb, stylized_mobile:kenney:food/pear.glb, stylized_mobile:kenney:food/cauliflower.glb` |
| en-020 | rocket launcher | en | 1.0000 | 0.8520 | 3 | `stylized_mobile:kenney:weapon/rocketlauncherModern.glb, stylized_mobile:kenney:weapon/ammo_rocketModern.glb, stylized_mobile:kenney:weapon/rocketlauncher.glb` |
| en-021 | trophy icon | en | 1.0000 | 1.0000 | 1 | `stylized_mobile:kenney:icons/Game Icons/trophy.png, stylized_mobile:kenney:food/cocktail.glb, stylized_mobile:kenney:icons/Game Icons/zoomOut.png` |
| en-022 | drawbridge | en | 0.0000 | 0.0000 | 1 | `stylized_mobile:kenney:castle/flag-wide.glb, stylized_mobile:kenney:castle/bridge-straight.glb, stylized_mobile:kenney:mini-dungeon/banner.glb` |
| en-023 | flamethrower | en | 1.0000 | 0.5250 | 2 | `stylized_mobile:kenney:weapon/uziSilencerGold.glb, stylized_mobile:kenney:weapon/rocketlauncherModern.glb, stylized_mobile:kenney:weapon/flamethrower_short.glb` |
| en-024 | a spear | en | 0.0000 | 0.0000 | 1 | `stylized_mobile:kenney:food/corn-dog.glb, stylized_mobile:kenney:food/cooking-knife.glb, stylized_mobile:kenney:weapon/knife_sharp.glb` |
| en-025 | checkpoint flag | en | 0.2857 | 0.3516 | 7 | `stylized_mobile:kenney:platformer/flag.glb, stylized_mobile:kenney:castle/flag.glb, stylized_mobile:kenney:ui/UI Pack/icon_outline_checkmark.png` |
| zh-046 | 一台复古相机 | zh | 1.0000 | 1.0000 | 1 | `realistic:polyhaven:polyhaven-model:Camera_01/Camera_01_1k.gltf, realistic:polyhaven:polyhaven-model:Television_01/Television_01_1k.gltf, realistic:polyhaven:polyhaven-model:classic_laptop/classic_laptop_1k.gltf` |
| zh-047 | 写实风格的手枪 | zh | 1.0000 | 1.0000 | 1 | `realistic:polyhaven:polyhaven-model:service_pistol/service_pistol_1k.gltf, realistic:polyhaven:polyhaven-model:bolt_action_rifle_7_62/bolt_action_rifle_7_62_1k.gltf, realistic:polyhaven:polyhaven-model:Camera_01/Camera_01_1k.gltf` |
| zh-048 | 皮沙发 | zh | 1.0000 | 1.0000 | 1 | `realistic:polyhaven:polyhaven-model:sofa_02/sofa_02_1k.gltf, realistic:polyhaven:polyhaven-texture:leather_red_02/leather_red_02_ao_1k.jpg, realistic:polyhaven:polyhaven-texture:rusty_metal_03/rusty_metal_03_albedo_1k.jpg` |
| zh-049 | 红酒瓶 | zh | 1.0000 | 1.0000 | 1 | `realistic:polyhaven:polyhaven-model:wine_bottles_01/wine_bottles_01_1k.gltf, realistic:polyhaven:polyhaven-model:ceramic_vase_01/ceramic_vase_01_1k.gltf, realistic:polyhaven:polyhaven-model:Lantern_01/Lantern_01_1k.gltf` |
| zh-050 | 砖墙贴图 | zh | 1.0000 | 1.0000 | 1 | `realistic:polyhaven:polyhaven-texture:brick_wall_001/brick_wall_001_albedo_1k.jpg, realistic:polyhaven:polyhaven-texture:roof_07/roof_07_albedo_1k.jpg, realistic:polyhaven:polyhaven-texture:rock_wall_02/rock_wall_02_albedo_1k.jpg` |
| en-026 | vintage camera | en | 1.0000 | 1.0000 | 1 | `realistic:polyhaven:polyhaven-model:Camera_01/Camera_01_1k.gltf, realistic:polyhaven:polyhaven-model:Television_01/Television_01_1k.gltf, realistic:polyhaven:polyhaven-model:classic_laptop/classic_laptop_1k.gltf` |
| en-027 | a realistic pistol | en | 1.0000 | 1.0000 | 1 | `realistic:polyhaven:polyhaven-model:service_pistol/service_pistol_1k.gltf, realistic:polyhaven:polyhaven-model:bolt_action_rifle_7_62/bolt_action_rifle_7_62_1k.gltf, realistic:polyhaven:polyhaven-model:Camera_01/Camera_01_1k.gltf` |
| en-028 | wooden table | en | 1.0000 | 1.0000 | 1 | `realistic:polyhaven:polyhaven-model:wooden_table_02/wooden_table_02_1k.gltf, realistic:polyhaven:polyhaven-texture:wood_floor_deck/wood_floor_deck_albedo_1k.jpg, realistic:polyhaven:polyhaven-texture:plywood/plywood_albedo_1k.jpg` |
| en-029 | rusty metal texture | en | 1.0000 | 1.0000 | 1 | `realistic:polyhaven:polyhaven-texture:rusty_metal_03/rusty_metal_03_albedo_1k.jpg, realistic:polyhaven:polyhaven-texture:rock_wall_02/rock_wall_02_albedo_1k.jpg, realistic:polyhaven:polyhaven-texture:brown_mud_leaves_01/brown_mud_leaves_01_albedo_1k.jpg` |
| en-030 | horse statue | en | 1.0000 | 1.0000 | 1 | `realistic:polyhaven:polyhaven-model:horse_statue_01/horse_statue_01_1k.gltf, realistic:polyhaven:polyhaven-model:Lantern_01/Lantern_01_1k.gltf, realistic:polyhaven:polyhaven-texture:coast_sand_rocks_02/coast_sand_rocks_02_albedo_1k.jpg` |
| zh-051 | 办公桌 | zh | 1.0000 | 1.0000 | 1 | `realistic:polyhaven:polyhaven-model:metal_office_desk/metal_office_desk_1k.gltf, realistic:polyhaven:polyhaven-model:wooden_table_02/wooden_table_02_1k.gltf, realistic:polyhaven:polyhaven-texture:plywood/plywood_albedo_1k.jpg` |
| zh-052 | 墙上的钟 | zh | 1.0000 | 1.0000 | 1 | `realistic:polyhaven:polyhaven-model:wall_clock/wall_clock_1k.gltf, realistic:polyhaven:polyhaven-texture:rusty_metal_03/rusty_metal_03_albedo_1k.jpg, realistic:polyhaven:polyhaven-model:Lantern_01/Lantern_01_1k.gltf` |
| en-031 | ceramic vase | en | 1.0000 | 1.0000 | 1 | `realistic:polyhaven:polyhaven-model:ceramic_vase_01/ceramic_vase_01_1k.gltf, realistic:polyhaven:polyhaven-model:horse_statue_01/horse_statue_01_1k.gltf, realistic:polyhaven:polyhaven-model:Lantern_01/Lantern_01_1k.gltf` |
| en-032 | leather texture | en | 1.0000 | 1.0000 | 1 | `realistic:polyhaven:polyhaven-texture:leather_red_02/leather_red_02_ao_1k.jpg, realistic:polyhaven:polyhaven-texture:rusty_metal_03/rusty_metal_03_albedo_1k.jpg, realistic:polyhaven:polyhaven-model:sofa_02/sofa_02_1k.gltf` |
| zh-053 | 螺栓步枪 | zh | 1.0000 | 1.0000 | 1 | `realistic:polyhaven:polyhaven-model:bolt_action_rifle_7_62/bolt_action_rifle_7_62_1k.gltf, realistic:polyhaven:polyhaven-model:service_pistol/service_pistol_1k.gltf, realistic:polyhaven:polyhaven-texture:rusty_metal_03/rusty_metal_03_albedo_1k.jpg` |
| zh-054 | 武器 | zh | 0.1389 | 1.0000 | 72 | `stylized_mobile:kenney:weapon/pistolSilencer.glb, stylized_mobile:kenney:weapon/shotgun.glb, stylized_mobile:kenney:weapon/machinegunLauncher.glb` |
| en-033 | food | en | 0.0350 | 0.6004 | 200 | `stylized_mobile:kenney:icons/Game Icons/basket.png, stylized_mobile:kenney:food/taco.glb, stylized_mobile:kenney:platformer/block-moving.glb` |
| img-001 | [image:weapon-sword.glb] | zh | 1.0000 | 1.0000 | 1 | `stylized_mobile:kenney:mini-dungeon/weapon-sword.glb, stylized_mobile:kenney:mini-dungeon/weapon-spear.glb, stylized_mobile:kenney:food/mortar-pestle.glb` |
| img-002 | [image:apple.glb] | zh | 1.0000 | 0.7904 | 2 | `stylized_mobile:kenney:food/apple.glb, stylized_mobile:kenney:food/tomato.glb, stylized_mobile:kenney:food/orange.glb` |
| img-003 | [image:character-orc.glb] | en | 1.0000 | 1.0000 | 1 | `stylized_mobile:kenney:mini-dungeon/character-orc.glb, stylized_mobile:kenney:mini-forest/character-archer.glb, stylized_mobile:kenney:mini-characters/character-male-f.glb` |
| img-004 | [image:Camera_01] | en | 1.0000 | 1.0000 | 1 | `realistic:polyhaven:polyhaven-model:Camera_01/Camera_01_1k.gltf, realistic:polyhaven:polyhaven-model:sofa_02/sofa_02_1k.gltf, realistic:polyhaven:polyhaven-model:Television_01/Television_01_1k.gltf` |
| img-005 | [image:button_rectangle_flat.png] | zh | 1.0000 | 1.0000 | 1 | `stylized_mobile:kenney:ui/UI Pack/button_rectangle_flat.png, stylized_mobile:kenney:ui/UI Pack/button_rectangle_depth_flat.png, stylized_mobile:kenney:ui/UI Pack/button_rectangle_gradient.png` |
| img-006 | [image:shield-round.glb] | zh | 1.0000 | 1.0000 | 1 | `stylized_mobile:kenney:mini-dungeon/shield-round.glb, stylized_mobile:kenney:platformer/coin-silver.glb, stylized_mobile:kenney:platformer/coin-gold.glb` |
| img-007 | [image:trophy.png] | en | 1.0000 | 1.0000 | 1 | `stylized_mobile:kenney:icons/Game Icons/trophy.png, stylized_mobile:kenney:icons/Game Icons/gamepad.png, stylized_mobile:kenney:icons/Game Icons/import.png` |
| img-008 | [image:service_pistol] | en | 1.0000 | 1.0000 | 1 | `realistic:polyhaven:polyhaven-model:service_pistol/service_pistol_1k.gltf, realistic:polyhaven:polyhaven-model:bolt_action_rifle_7_62/bolt_action_rifle_7_62_1k.gltf, realistic:polyhaven:polyhaven-model:Television_01/Television_01_1k.gltf` |
