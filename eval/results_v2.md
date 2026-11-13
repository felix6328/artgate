# ArtGate v2 离线评测（与 v1 对比）

评测时间：2026-11-13 21:04 CST（Asia/Shanghai）。
评测脚本：`scripts/run_eval_v2.py`。所有数字均由本次运行实测，没有手工填写。

**金标文件未改动。** `eval/gold_queries.yaml` SHA256 = `8a019ae5a03e0ff3b0b69041d884861bda634905b12515839da020ed27d13f48`，与 v1 评测时一致。
金标状态仍为 `auto_drafted_needs_review`，须经人工审阅后才能作为正式面试口径。

## 方法（评测前冻结，未按本轮数字回改）

- **v1**：仅 OpenCLIP 多语言语义检索（`retriever=semantic`），与 v1 标签提交行为一致。
- **v2**：语义一路（原查询，不扩展）+ BM25 一路（文件名 / 路径 / 标签 / 类型，查询经手写同义词扩展）→ **RRF 融合**（k=60）。
  选择 RRF 是因为 CLIP 展示分与 BM25 分数量纲不同，直接加权要引入归一化超参，更容易过拟合。
- **查询类型路由**：含中文或较长英文描述 → 两路等权（1.0/1.0）；标识符或 1–2 个英文实词（如 `a sword`）→ BM25 权重 1.5、语义 1.0。先验来自 v1 已发布的观察（英文短查询与英文文件名高度重叠），不是本轮网格搜索的结果。
- **消融**：BM25 + 同义词扩展、不融合语义；以及 v1 的纯文件名重叠基线（逻辑未改）。
- **以图搜图**：仍走纯语义，本轮方法不变。
- **同义词表**：`configs/synonyms_game_art.yaml`，手写领域词表。「剑」扩展为 sword/blade，**不**扩展为 knife。
  **泄漏风险**：词表写于 v1 评测之后，作者已经见过全量金标与坏例，不能声称完全看不见金标。dev/test 切分用于事后检验，**本轮没有根据 dev 结果增补词条或改权重**。

## dev / test 切分

- 名称：`artgate-v2-split-seed42-stratified-lang-50-50`。只切文本查询；以图搜图不参与切分。
- 按 `lang` 分层，组内对 query id 排序后用 `random.Random(42)` 打乱，各取约 50% 为 dev，其余为 test。
- 各语言条数：{"en": {"n": 33, "dev": 16, "test": 17}, "zh": {"n": 54, "dev": 27, "test": 27}}。
- 详细分配见 `eval/split_v2.json`。

## 1. 主对比表（全量文本金标，与 v1 同一套题）

| 系统 | 分组 | Recall@5 | Recall@10 | nDCG@10 | MRR |
| --- | --- | --- | --- | --- | --- |
| v1 语义 | 全部文本 | 0.5304 (n=87) | 0.6086 (n=87) | 0.5824 (n=87) | 0.5962 (n=87) |
| v1 语义 | 中文 | 0.4783 (n=54) | 0.5548 (n=54) | 0.5415 (n=54) | 0.5559 (n=54) |
| v1 语义 | 英文 | 0.6158 (n=33) | 0.6967 (n=33) | 0.6493 (n=33) | 0.6621 (n=33) |
| v2 混合（RRF + 扩展） | 全部文本 | 0.7442 (n=87) | 0.8248 (n=87) | 0.8190 (n=87) | 0.8316 (n=87) |
| v2 混合（RRF + 扩展） | 中文 | 0.7244 (n=54) | 0.7973 (n=54) | 0.7664 (n=54) | 0.7789 (n=54) |
| v2 混合（RRF + 扩展） | 英文 | 0.7766 (n=33) | 0.8699 (n=33) | 0.9051 (n=33) | 0.9179 (n=33) |
| BM25 + 扩展（消融） | 全部文本 | 0.7090 (n=87) | 0.7629 (n=87) | 0.8004 (n=87) | 0.8170 (n=87) |
| BM25 + 扩展（消融） | 中文 | 0.6823 (n=54) | 0.7338 (n=54) | 0.7511 (n=54) | 0.7608 (n=54) |
| BM25 + 扩展（消融） | 英文 | 0.7526 (n=33) | 0.8105 (n=33) | 0.8810 (n=33) | 0.9091 (n=33) |
| 文件名基线（v1 逻辑） | 全部文本 | 0.4894 (n=87) | 0.5195 (n=87) | 0.5435 (n=87) | 0.5776 (n=87) |
| 文件名基线（v1 逻辑） | 中文 | 0.3262 (n=54) | 0.3355 (n=54) | 0.3354 (n=54) | 0.3750 (n=54) |
| 文件名基线（v1 逻辑） | 英文 | 0.7564 (n=33) | 0.8206 (n=33) | 0.8841 (n=33) | 0.9091 (n=33) |

以图搜图（方法与 v1 相同，n 见下）：
- Recall@5=0.9375 (n=8)，Recall@10=1.0000 (n=8)，nDCG@10=0.9738 (n=8)，MRR=1.0000 (n=8)。查询图仍是库内预览，偏乐观。

### 检索时延（模型已加载后的查询，已 warmup）

| 系统 | n | mean (ms) | P50 | **P95** | max |
| --- | --- | --- | --- | --- | --- |
| v1 语义 | 87 | 59.19 | 57.14 | **76.78** | 82.09 |
| v2 混合 | 87 | 75.04 | 73.77 | **86.31** | 104.86 |
| BM25 + 扩展 | 87 | 14.75 | 14.14 | **19.25** | 22.17 |

机器：OS=Linux-6.12.113+-x86_64-with-glibc2.41 Python=3.13.5 CPU=x86_64 nproc=8 MemTotal:       16386416 kB
第一次加载模型的时间不计入上述 P95。

## 2. dev / test 分组（事后检验，本轮未在上面调参）

| 系统 | 分组 | Recall@5 | Recall@10 | nDCG@10 | MRR |
| --- | --- | --- | --- | --- | --- |
| v1 语义 | dev 全部 | 0.4924 (n=43) | 0.5844 (n=43) | 0.5684 (n=43) | 0.5926 (n=43) |
| v1 语义 | test 全部 | 0.5676 (n=44) | 0.6323 (n=44) | 0.5960 (n=44) | 0.5997 (n=44) |
| v1 语义 | dev 中文 | 0.3841 (n=27) | 0.4767 (n=27) | 0.4753 (n=27) | 0.5000 (n=27) |
| v1 语义 | test 中文 | 0.5726 (n=27) | 0.6329 (n=27) | 0.6077 (n=27) | 0.6118 (n=27) |
| v1 语义 | dev 英文 | 0.6753 (n=16) | 0.7660 (n=16) | 0.7254 (n=16) | 0.7490 (n=16) |
| v1 语义 | test 英文 | 0.5597 (n=17) | 0.6315 (n=17) | 0.5776 (n=17) | 0.5804 (n=17) |
| v2 混合 | dev 全部 | 0.6672 (n=43) | 0.7817 (n=43) | 0.7739 (n=43) | 0.7749 (n=43) |
| v2 混合 | test 全部 | 0.8195 (n=44) | 0.8670 (n=44) | 0.8630 (n=44) | 0.8871 (n=44) |
| v2 混合 | dev 中文 | 0.6328 (n=27) | 0.7206 (n=27) | 0.6990 (n=27) | 0.7047 (n=27) |
| v2 混合 | test 中文 | 0.8161 (n=27) | 0.8740 (n=27) | 0.8337 (n=27) | 0.8531 (n=27) |
| v2 混合 | dev 英文 | 0.7252 (n=16) | 0.8848 (n=16) | 0.9003 (n=16) | 0.8932 (n=16) |
| v2 混合 | test 英文 | 0.8250 (n=17) | 0.8559 (n=17) | 0.9096 (n=17) | 0.9412 (n=17) |
| BM25 + 扩展 | dev 全部 | 0.6996 (n=43) | 0.7644 (n=43) | 0.7859 (n=43) | 0.7810 (n=43) |
| BM25 + 扩展 | test 全部 | 0.7182 (n=44) | 0.7614 (n=44) | 0.8144 (n=44) | 0.8523 (n=44) |
| BM25 + 扩展 | dev 中文 | 0.6890 (n=27) | 0.7533 (n=27) | 0.7439 (n=27) | 0.7253 (n=27) |
| BM25 + 扩展 | test 中文 | 0.6756 (n=27) | 0.7143 (n=27) | 0.7584 (n=27) | 0.7963 (n=27) |
| BM25 + 扩展 | dev 英文 | 0.7174 (n=16) | 0.7831 (n=16) | 0.8570 (n=16) | 0.8750 (n=16) |
| BM25 + 扩展 | test 英文 | 0.7858 (n=17) | 0.8363 (n=17) | 0.9035 (n=17) | 0.9412 (n=17) |

若 test 相对 dev 没有明显塌陷，说明提升不只是记牢了某一半题目；即便如此，因作者见过 v1 全量坏例，仍不能排除词表覆盖与金标重叠带来的乐观。

## 3. 相对 v1 的逐条变化（文本）

### 已修复：v1 Recall@10 = 0，v2 > 0（17 条）

| id | 查询 | 语言 | 分组 | v1 R@10 | v2 R@10 | Δ | 扩展词 | v2 前 3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| en-001 | a sword | en | test | 0.0000 | 1.0000 | +1.0000 | — | `stylized_mobile:kenney:mini-dungeon/weapon-sword.glb, stylized_mobile:kenney:weapon/knifeRound_sharp.glb, stylized_mobile:kenney:weapon/knife_sharp.glb` |
| en-008 | treasure chest | en | test | 0.0000 | 1.0000 | +1.0000 | — | `stylized_mobile:kenney:platformer/chest.glb, stylized_mobile:kenney:mini-dungeon/chest.glb, stylized_mobile:kenney:platformer/lock.glb` |
| en-013 | bow and arrow | en | dev | 0.0000 | 1.0000 | +1.0000 | — | `stylized_mobile:kenney:icons/Game Icons/arrowLeft.png, stylized_mobile:kenney:icons/Game Icons/arrowRight.png, stylized_mobile:kenney:ui/UI Pack/arrow_decorative_w_small.png` |
| en-019 | avocado | en | test | 0.0000 | 0.5000 | +0.5000 | — | `stylized_mobile:kenney:food/avocado.glb, stylized_mobile:kenney:food/pear-half.glb, stylized_mobile:kenney:food/pear.glb` |
| en-024 | a spear | en | test | 0.0000 | 1.0000 | +1.0000 | — | `stylized_mobile:kenney:mini-dungeon/weapon-spear.glb, stylized_mobile:kenney:food/corn-dog.glb, stylized_mobile:kenney:food/cooking-knife.glb` |
| zh-001 | 一把剑 | zh | dev | 0.0000 | 1.0000 | +1.0000 | sword, blade | `stylized_mobile:kenney:mini-dungeon/weapon-sword.glb, stylized_mobile:kenney:weapon/knife_sharp.glb, stylized_mobile:kenney:weapon/knife_smooth.glb` |
| zh-002 | 圆形盾牌 | zh | test | 0.0000 | 1.0000 | +1.0000 | round, circular, circle, shield | `stylized_mobile:kenney:mini-dungeon/shield-round.glb, stylized_mobile:kenney:food/cutting-board-round.glb, stylized_mobile:kenney:ui/UI Pack/check_round_grey.png` |
| zh-004 | 长矛 | zh | dev | 0.0000 | 1.0000 | +1.0000 | spear, pike | `stylized_mobile:kenney:mini-dungeon/weapon-spear.glb, stylized_mobile:kenney:food/cooking-knife.glb, stylized_mobile:kenney:food/chopstic-decorative.glb` |
| zh-005 | 一把弓 | zh | dev | 0.0000 | 0.5000 | +0.5000 | bow | `stylized_mobile:kenney:mini-forest/weapon-bow.glb, stylized_mobile:kenney:mini-forest/target.glb, stylized_mobile:kenney:castle/siege-ballista-demolished.glb` |
| zh-006 | 一支箭 | zh | test | 0.0000 | 1.0000 | +1.0000 | arrow | `stylized_mobile:kenney:platformer/arrow.glb, stylized_mobile:kenney:mini-forest/weapon-arrow.glb, stylized_mobile:kenney:icons/Game Icons/arrowLeft.png` |
| zh-007 | 兽人角色 | zh | test | 0.0000 | 1.0000 | +1.0000 | orc, character | `stylized_mobile:kenney:mini-dungeon/character-human.glb, stylized_mobile:kenney:mini-dungeon/character-orc.glb, stylized_mobile:kenney:mini-characters/character-male-b.glb` |
| zh-008 | 人类角色 | zh | test | 0.0000 | 1.0000 | +1.0000 | human, character | `stylized_mobile:kenney:mini-dungeon/character-human.glb, stylized_mobile:kenney:mini-characters/character-male-b.glb, stylized_mobile:kenney:mini-characters/character-male-f.glb` |
| zh-012 | 宝箱 | zh | dev | 0.0000 | 1.0000 | +1.0000 | chest, treasure | `stylized_mobile:kenney:mini-dungeon/chest.glb, stylized_mobile:kenney:platformer/chest.glb, stylized_mobile:kenney:platformer/lock.glb` |
| zh-021 | 弓箭手 | zh | dev | 0.0000 | 1.0000 | +1.0000 | archer | `stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_attack2.png, stylized_mobile:kenney:mini-forest/character-archer.glb, stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_climb1.png` |
| zh-022 | 攻城投石机 | zh | dev | 0.0000 | 0.7500 | +0.7500 | catapult, trebuchet, siege | `stylized_mobile:kenney:castle/siege-tower.glb, stylized_mobile:kenney:castle/siege-ram-demolished.glb, stylized_mobile:kenney:castle/siege-ballista.glb` |
| zh-023 | 攻城槌 | zh | dev | 0.0000 | 1.0000 | +1.0000 | siege | `stylized_mobile:kenney:castle/siege-ballista-demolished.glb, stylized_mobile:kenney:castle/siege-catapult-demolished.glb, stylized_mobile:kenney:castle/siege-ram-demolished.glb` |
| zh-039 | 吊桥 | zh | test | 0.0000 | 1.0000 | +1.0000 | bridge | `stylized_mobile:kenney:castle/bridge-straight.glb, stylized_mobile:kenney:mini-forest/bridge.glb, stylized_mobile:kenney:castle/bridge-draw.glb` |

### 明显提升：v2 − v1 Recall@10 ≥ 0.15（且 v1 不是 0）（7 条）

| id | 查询 | 语言 | 分组 | v1 R@10 | v2 R@10 | Δ | 扩展词 | v2 前 3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| en-014 | siege catapult | en | test | 0.7000 | 1.0000 | +0.3000 | — | `stylized_mobile:kenney:castle/siege-catapult.glb, stylized_mobile:kenney:castle/siege-trebuchet.glb, stylized_mobile:kenney:castle/siege-ballista.glb` |
| en-015 | gold uzi | en | dev | 0.6250 | 1.0000 | +0.3750 | — | `stylized_mobile:kenney:weapon/uziGold.glb, stylized_mobile:kenney:weapon/uziLongSilencerGold.glb, stylized_mobile:kenney:weapon/uziLongGold.glb` |
| en-025 | checkpoint flag | en | dev | 0.2857 | 1.0000 | +0.7143 | — | `stylized_mobile:kenney:castle/flag.glb, stylized_mobile:kenney:platformer/flag.glb, stylized_mobile:kenney:castle/flag-pennant.glb` |
| zh-014 | 木桶 | zh | test | 0.3333 | 1.0000 | +0.6667 | barrel | `stylized_mobile:kenney:platformer/barrel.glb, stylized_mobile:kenney:food/barrel.glb, stylized_mobile:kenney:mini-dungeon/barrel.glb` |
| zh-026 | 火箭筒 | zh | dev | 0.6667 | 1.0000 | +0.3333 | rocketlauncher, rocket | `stylized_mobile:kenney:weapon/ammo_rocketModern.glb, stylized_mobile:kenney:weapon/rocketlauncherModern.glb, stylized_mobile:kenney:weapon/rocketlauncher.glb` |
| zh-027 | 手榴弹 | zh | test | 0.5000 | 1.0000 | +0.5000 | grenade | `stylized_mobile:kenney:weapon/grenadeSmoke.glb, stylized_mobile:kenney:weapon/grenade.glb, stylized_mobile:kenney:weapon/ammo_machinegunLauncher.glb` |
| zh-028 | 金色冲锋枪 | zh | test | 0.5000 | 1.0000 | +0.5000 | uzi, smg, submachine, gold, golden | `stylized_mobile:kenney:weapon/uziGold.glb, stylized_mobile:kenney:weapon/uziLongSilencerGold.glb, stylized_mobile:kenney:weapon/uziSilencerGold.glb` |

### 仍未召回：v1 与 v2 的 Recall@10 都是 0（6 条）

| id | 查询 | 语言 | 分组 | v1 R@10 | v2 R@10 | Δ | 扩展词 | v2 前 3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| en-022 | drawbridge | en | test | 0.0000 | 0.0000 | +0.0000 | — | `stylized_mobile:kenney:castle/flag-wide.glb, stylized_mobile:kenney:castle/bridge-straight.glb, stylized_mobile:kenney:mini-dungeon/banner.glb` |
| zh-003 | 长方形盾牌 | zh | test | 0.0000 | 0.0000 | +0.0000 | rectangle, rectangular, shield | `stylized_mobile:kenney:ui/UI Pack/input_outline_rectangle.png, stylized_mobile:kenney:ui/UI Pack/button_rectangle_gradient.png, stylized_mobile:kenney:ui/UI Pack/button_rectangle_depth_border.png` |
| zh-010 | 男性角色 | zh | dev | 0.0000 | 0.0000 | +0.0000 | male, man, character | `stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_interact.png, stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_talk.png, stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_hold.png` |
| zh-031 | 横向滑动条 | zh | dev | 0.0000 | 0.0000 | +0.0000 | — | `stylized_mobile:kenney:food/bacon-raw.glb, stylized_mobile:kenney:food/bacon.glb, stylized_mobile:kenney:platformer/spike-block-wide.glb` |
| zh-037 | 牛油果 | zh | dev | 0.0000 | 0.0000 | +0.0000 | — | `stylized_mobile:kenney:food/pear.glb, stylized_mobile:kenney:food/pear-half.glb, stylized_mobile:kenney:food/pineapple.glb` |
| zh-042 | 地牢里的陷阱 | zh | dev | 0.0000 | 0.0000 | +0.0000 | — | `stylized_mobile:kenney:mini-dungeon/wall.glb, stylized_mobile:kenney:mini-dungeon/wall-narrow.glb, stylized_mobile:kenney:food/bowl-broth.glb` |

### 回退：v1 Recall@10 > 0，v2 = 0（0 条）

（无）

### 明显下降：v1 − v2 Recall@10 ≥ 0.15（v2 未到 0）（2 条）

| id | 查询 | 语言 | 分组 | v1 R@10 | v2 R@10 | Δ | 扩展词 | v2 前 3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| en-020 | rocket launcher | en | dev | 1.0000 | 0.6667 | -0.3333 | — | `stylized_mobile:kenney:weapon/ammo_rocketModern.glb, stylized_mobile:kenney:weapon/machinegunLauncher.glb, stylized_mobile:kenney:weapon/ammo_machinegunLauncher.glb` |
| zh-035 | 游戏手柄图标 | zh | test | 0.4000 | 0.2000 | -0.2000 | icon | `stylized_mobile:kenney:icons/Game Icons/gamepad.png, stylized_mobile:kenney:icons/Game Icons/exitLeft.png, stylized_mobile:kenney:icons/Game Icons/exitRight.png` |

### 兵器类查询专题

识别规则：查询文本含剑/盾/矛/弓/箭/枪/sword/shield/spear 等武器词，用于分组展示，**没有**据此改模型或词表。

| id | 查询 | 分组 | v1 R@10 | v2 R@10 | BM25 R@10 | 文件名基线 | 扩展词 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| zh-001 | 一把剑 | dev | 0.0000 | 1.0000 | 1.0000 | 0.0000 | sword, blade |
| zh-002 | 圆形盾牌 | test | 0.0000 | 1.0000 | 1.0000 | 0.0000 | round, circular, circle, shield |
| zh-003 | 长方形盾牌 | test | 0.0000 | 0.0000 | 1.0000 | 0.0000 | rectangle, rectangular, shield |
| zh-004 | 长矛 | dev | 0.0000 | 1.0000 | 1.0000 | 0.0000 | spear, pike |
| zh-005 | 一把弓 | dev | 0.0000 | 0.5000 | 0.5000 | 0.0000 | bow |
| zh-006 | 一支箭 | test | 0.0000 | 1.0000 | 1.0000 | 0.0000 | arrow |
| zh-021 | 弓箭手 | dev | 0.0000 | 1.0000 | 1.0000 | 1.0000 | archer |
| zh-024 | 手枪 | dev | 1.0000 | 1.0000 | 1.0000 | 0.5000 | pistol, handgun |
| zh-025 | 狙击枪 | dev | 1.0000 | 1.0000 | 1.0000 | 0.5000 | sniper |
| zh-026 | 火箭筒 | dev | 0.6667 | 1.0000 | 1.0000 | 0.0000 | rocketlauncher, rocket |
| zh-028 | 金色冲锋枪 | test | 0.5000 | 1.0000 | 1.0000 | 0.0000 | uzi, smg, submachine, gold, golden |
| en-001 | a sword | test | 0.0000 | 1.0000 | 1.0000 | 1.0000 | — |
| en-002 | a round shield | test | 1.0000 | 1.0000 | 1.0000 | 1.0000 | — |
| en-005 | a pistol | test | 1.0000 | 1.0000 | 1.0000 | 1.0000 | — |
| en-006 | sniper rifle | dev | 1.0000 | 1.0000 | 1.0000 | 1.0000 | — |
| en-013 | bow and arrow | dev | 0.0000 | 1.0000 | 1.0000 | 0.0000 | — |
| en-015 | gold uzi | dev | 0.6250 | 1.0000 | 1.0000 | 1.0000 | — |
| en-024 | a spear | test | 0.0000 | 1.0000 | 1.0000 | 1.0000 | — |
| zh-047 | 写实风格的手枪 | test | 1.0000 | 1.0000 | 1.0000 | 1.0000 | pistol, handgun |
| en-027 | a realistic pistol | dev | 1.0000 | 1.0000 | 1.0000 | 1.0000 | — |
| zh-053 | 螺栓步枪 | test | 1.0000 | 1.0000 | 1.0000 | 1.0000 | rifle |


### 融合的已知失败模式（实测，未在本轮回改）

- 「长方形盾牌」（test）与「男性角色」（dev）：**BM25 一路 Recall@10 已是 1.0，但混合检索仍是 0**。
  原因：相关资产在语义前 50 里很靠后或不在，RRF 只有词法一路的贡献 `1/(60+1)≈0.016`；
  同时出现在两路里的干扰项（例如带 rectangle 的 UI 按钮，语义第 9、BM25 第 5）RRF 约 `0.030`，把真正的盾牌挤出前 10。
  这是「两路都命中的干扰项压过只在词法一路命中的正确答案」。本轮不改并列规则、不改权重，留给后续，避免看完测试集再调。
- 英文 v2 Recall@10 = 0.8699，**高于**本轮文件名基线 0.8206，也高于 v1 语义 0.6967。中文从 0.5548 到 0.7973。这是本轮的主要结果。
- 本轮配对重测的 v1 检索指标与 v1 发布稿（`eval/results.md`）完全一致（文本 Recall@10 0.6086 等）；时延因进程与是否计入以图搜图而不同，对比请用本表同一轮的 v1 P95=76.78 ms 与 v2 P95=86.31 ms，不要和发布稿里 n=95 的 58.34 ms 混用。

## 4. 限制（必须和数字一起讲）

- 金标仍为自动起草、未经人工审阅。
- 同义词表的作者见过 v1 全量坏例，存在泄漏风险；dev/test 是缓解而不是消除。
- 样本仍然很小，区间波动会很大。
- 3D 预览仍是软件等轴测，语义一路的近形混淆（剑 vs 刀）并没有从模型上被「治好」，只是被词法一路托上来。换预览或做重排是后续，不是本轮声称已解决的事。
- 形状/颜色扩展（圆形→round、金色→gold）可能把 UI 圆钮、金色枪皮也拉进来，属于过度扩展风险。
- 以图搜图、规则预检本轮方法未改；预检数字仍以 `eval/results.md` 为准，未重跑。
- 有两条查询（长方形盾牌、男性角色）BM25 单独已经能召回，混合后反而为 0，见上文「融合的已知失败模式」。消融表必须一起讲，不能只报混合检索的平均值。

## 5. 环境

- OS=Linux-6.12.113+-x86_64-with-glibc2.41 Python=3.13.5 CPU=x86_64 nproc=8 MemTotal:       16386416 kB
- 嵌入模型仍为 OpenCLIP `xlm-roberta-base-ViT-B-32` / `laion5b_s13b_b90k`，CPU。

