# ArtGate 坏例清单（v1 vs v2）

检索部分按同一套金标对比 v1 语义与 v2 混合检索。数字来自 `scripts/run_eval_v2.py`。
预检规则层本轮未重跑，口径与 v1 相同，详见 `eval/results.md` 第 2 节（18 条夹具上宏平均 1.00，样本量小）。
金标未经人工审阅。同义词表作者见过 v1 全量坏例，有泄漏风险。

## 已修复（v1 完全未召回，v2 召回了）（17）

典型机制：中文查询经译名扩展后被 BM25 命中英文文件名，RRF 把词法第一名托到融合列表前面。语义一路本身往往仍把近形物体排在前面。

### en-001　a sword

- 语言 / 分组：en / test
- v1 Recall@10 = 0.0000，v2 Recall@10 = 1.0000（Δ +1.0000）
- v1 前 3：`['stylized_mobile:kenney:weapon/knifeRound_sharp.glb', 'stylized_mobile:kenney:weapon/knife_sharp.glb', 'stylized_mobile:kenney:weapon/knife_smooth.glb']`
- v2 前 3：`['stylized_mobile:kenney:mini-dungeon/weapon-sword.glb', 'stylized_mobile:kenney:weapon/knifeRound_sharp.glb', 'stylized_mobile:kenney:weapon/knife_sharp.glb']`
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:mini-dungeon/weapon-sword.glb', 'ranks': {'semantic': 31, 'bm25': 1}, 'file': 'weapon-sword.glb'}, {'id': 'stylized_mobile:kenney:weapon/knifeRound_sharp.glb', 'ranks': {'semantic': 1}, 'file': 'knifeRound_sharp.glb'}, {'id': 'stylized_mobile:kenney:weapon/knife_sharp.glb', 'ranks': {'semantic': 2}, 'file': 'knife_sharp.glb'}]

### en-008　treasure chest

- 语言 / 分组：en / test
- v1 Recall@10 = 0.0000，v2 Recall@10 = 1.0000（Δ +1.0000）
- v1 前 3：`['stylized_mobile:kenney:platformer/lock.glb', 'stylized_mobile:kenney:castle/wall-corner-half-tower.glb', 'stylized_mobile:kenney:mini-characters/aid-defibrillator-red.glb']`
- v2 前 3：`['stylized_mobile:kenney:platformer/chest.glb', 'stylized_mobile:kenney:mini-dungeon/chest.glb', 'stylized_mobile:kenney:platformer/lock.glb']`
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:platformer/chest.glb', 'ranks': {'semantic': 18, 'bm25': 1}, 'file': 'chest.glb'}, {'id': 'stylized_mobile:kenney:mini-dungeon/chest.glb', 'ranks': {'semantic': 17, 'bm25': 2}, 'file': 'chest.glb'}, {'id': 'stylized_mobile:kenney:platformer/lock.glb', 'ranks': {'semantic': 1}, 'file': 'lock.glb'}]

### en-013　bow and arrow

- 语言 / 分组：en / dev
- v1 Recall@10 = 0.0000，v2 Recall@10 = 1.0000（Δ +1.0000）
- v1 前 3：`['stylized_mobile:kenney:castle/siege-ballista-demolished.glb', 'stylized_mobile:kenney:icons/Game Icons/upRight.png', 'stylized_mobile:kenney:icons/Game Icons/upLeft.png']`
- v2 前 3：`['stylized_mobile:kenney:icons/Game Icons/arrowLeft.png', 'stylized_mobile:kenney:icons/Game Icons/arrowRight.png', 'stylized_mobile:kenney:ui/UI Pack/arrow_decorative_w_small.png']`
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:icons/Game Icons/arrowLeft.png', 'ranks': {'semantic': 7, 'bm25': 21}, 'file': 'arrowLeft.png'}, {'id': 'stylized_mobile:kenney:icons/Game Icons/arrowRight.png', 'ranks': {'semantic': 8, 'bm25': 22}, 'file': 'arrowRight.png'}, {'id': 'stylized_mobile:kenney:ui/UI Pack/arrow_decorative_w_small.png', 'ranks': {'semantic': 20, 'bm25': 19}, 'file': 'arrow_decorative_w_small.png'}]

### en-019　avocado

- 语言 / 分组：en / test
- v1 Recall@10 = 0.0000，v2 Recall@10 = 0.5000（Δ +0.5000）
- v1 前 3：`['stylized_mobile:kenney:food/pear-half.glb', 'stylized_mobile:kenney:food/pear.glb', 'stylized_mobile:kenney:food/cauliflower.glb']`
- v2 前 3：`['stylized_mobile:kenney:food/avocado.glb', 'stylized_mobile:kenney:food/pear-half.glb', 'stylized_mobile:kenney:food/pear.glb']`
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:food/avocado.glb', 'ranks': {'bm25': 1}, 'file': 'avocado.glb'}, {'id': 'stylized_mobile:kenney:food/pear-half.glb', 'ranks': {'semantic': 1}, 'file': 'pear-half.glb'}, {'id': 'stylized_mobile:kenney:food/pear.glb', 'ranks': {'semantic': 2}, 'file': 'pear.glb'}]

### en-024　a spear

- 语言 / 分组：en / test
- v1 Recall@10 = 0.0000，v2 Recall@10 = 1.0000（Δ +1.0000）
- v1 前 3：`['stylized_mobile:kenney:food/corn-dog.glb', 'stylized_mobile:kenney:food/cooking-knife.glb', 'stylized_mobile:kenney:weapon/knife_sharp.glb']`
- v2 前 3：`['stylized_mobile:kenney:mini-dungeon/weapon-spear.glb', 'stylized_mobile:kenney:food/corn-dog.glb', 'stylized_mobile:kenney:food/cooking-knife.glb']`
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:mini-dungeon/weapon-spear.glb', 'ranks': {'semantic': 13, 'bm25': 1}, 'file': 'weapon-spear.glb'}, {'id': 'stylized_mobile:kenney:food/corn-dog.glb', 'ranks': {'semantic': 1}, 'file': 'corn-dog.glb'}, {'id': 'stylized_mobile:kenney:food/cooking-knife.glb', 'ranks': {'semantic': 2}, 'file': 'cooking-knife.glb'}]

### zh-001　一把剑

- 语言 / 分组：zh / dev
- v1 Recall@10 = 0.0000，v2 Recall@10 = 1.0000（Δ +1.0000）
- v1 前 3：`['stylized_mobile:kenney:weapon/knife_sharp.glb', 'stylized_mobile:kenney:weapon/knife_smooth.glb', 'stylized_mobile:kenney:weapon/knifeRound_sharp.glb']`
- v2 前 3：`['stylized_mobile:kenney:mini-dungeon/weapon-sword.glb', 'stylized_mobile:kenney:weapon/knife_sharp.glb', 'stylized_mobile:kenney:weapon/knife_smooth.glb']`
- 同义词扩展：['sword', 'blade']
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:mini-dungeon/weapon-sword.glb', 'ranks': {'semantic': 37, 'bm25': 1}, 'file': 'weapon-sword.glb'}, {'id': 'stylized_mobile:kenney:weapon/knife_sharp.glb', 'ranks': {'semantic': 1}, 'file': 'knife_sharp.glb'}, {'id': 'stylized_mobile:kenney:weapon/knife_smooth.glb', 'ranks': {'semantic': 2}, 'file': 'knife_smooth.glb'}]

### zh-002　圆形盾牌

- 语言 / 分组：zh / test
- v1 Recall@10 = 0.0000，v2 Recall@10 = 1.0000（Δ +1.0000）
- v1 前 3：`['stylized_mobile:kenney:food/pot-stew-lid.glb', 'stylized_mobile:kenney:mini-forest/target.glb', 'stylized_mobile:kenney:food/pot-lid.glb']`
- v2 前 3：`['stylized_mobile:kenney:mini-dungeon/shield-round.glb', 'stylized_mobile:kenney:food/cutting-board-round.glb', 'stylized_mobile:kenney:ui/UI Pack/check_round_grey.png']`
- 同义词扩展：['round', 'circular', 'circle', 'shield']
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:mini-dungeon/shield-round.glb', 'ranks': {'semantic': 12, 'bm25': 1}, 'file': 'shield-round.glb'}, {'id': 'stylized_mobile:kenney:food/cutting-board-round.glb', 'ranks': {'semantic': 9, 'bm25': 9}, 'file': 'cutting-board-round.glb'}, {'id': 'stylized_mobile:kenney:ui/UI Pack/check_round_grey.png', 'ranks': {'semantic': 27, 'bm25': 11}, 'file': 'check_round_grey.png'}]

### zh-004　长矛

- 语言 / 分组：zh / dev
- v1 Recall@10 = 0.0000，v2 Recall@10 = 1.0000（Δ +1.0000）
- v1 前 3：`['stylized_mobile:kenney:food/cooking-knife.glb', 'stylized_mobile:kenney:food/chopstic-decorative.glb', 'stylized_mobile:kenney:weapon/knife_sharp.glb']`
- v2 前 3：`['stylized_mobile:kenney:mini-dungeon/weapon-spear.glb', 'stylized_mobile:kenney:food/cooking-knife.glb', 'stylized_mobile:kenney:food/chopstic-decorative.glb']`
- 同义词扩展：['spear', 'pike']
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:mini-dungeon/weapon-spear.glb', 'ranks': {'semantic': 48, 'bm25': 1}, 'file': 'weapon-spear.glb'}, {'id': 'stylized_mobile:kenney:food/cooking-knife.glb', 'ranks': {'semantic': 1}, 'file': 'cooking-knife.glb'}, {'id': 'stylized_mobile:kenney:food/chopstic-decorative.glb', 'ranks': {'semantic': 2}, 'file': 'chopstic-decorative.glb'}]

### zh-005　一把弓

- 语言 / 分组：zh / dev
- v1 Recall@10 = 0.0000，v2 Recall@10 = 0.5000（Δ +0.5000）
- v1 前 3：`['stylized_mobile:kenney:mini-forest/target.glb', 'stylized_mobile:kenney:castle/siege-ballista-demolished.glb', 'stylized_mobile:kenney:mini-forest/fence.glb']`
- v2 前 3：`['stylized_mobile:kenney:mini-forest/weapon-bow.glb', 'stylized_mobile:kenney:mini-forest/target.glb', 'stylized_mobile:kenney:castle/siege-ballista-demolished.glb']`
- 同义词扩展：['bow']
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:mini-forest/weapon-bow.glb', 'ranks': {'semantic': 30, 'bm25': 1}, 'file': 'weapon-bow.glb'}, {'id': 'stylized_mobile:kenney:mini-forest/target.glb', 'ranks': {'semantic': 1}, 'file': 'target.glb'}, {'id': 'stylized_mobile:kenney:castle/siege-ballista-demolished.glb', 'ranks': {'semantic': 2}, 'file': 'siege-ballista-demolished.glb'}]

### zh-006　一支箭

- 语言 / 分组：zh / test
- v1 Recall@10 = 0.0000，v2 Recall@10 = 1.0000（Δ +1.0000）
- v1 前 3：`['stylized_mobile:kenney:food/cooking-knife.glb', 'stylized_mobile:kenney:food/corn-dog.glb', 'stylized_mobile:kenney:food/whole-ham.glb']`
- v2 前 3：`['stylized_mobile:kenney:platformer/arrow.glb', 'stylized_mobile:kenney:mini-forest/weapon-arrow.glb', 'stylized_mobile:kenney:icons/Game Icons/arrowLeft.png']`
- 同义词扩展：['arrow']
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:platformer/arrow.glb', 'ranks': {'semantic': 30, 'bm25': 1}, 'file': 'arrow.glb'}, {'id': 'stylized_mobile:kenney:mini-forest/weapon-arrow.glb', 'ranks': {'semantic': 39, 'bm25': 2}, 'file': 'weapon-arrow.glb'}, {'id': 'stylized_mobile:kenney:icons/Game Icons/arrowLeft.png', 'ranks': {'semantic': 25, 'bm25': 26}, 'file': 'arrowLeft.png'}]

### zh-007　兽人角色

- 语言 / 分组：zh / test
- v1 Recall@10 = 0.0000，v2 Recall@10 = 1.0000（Δ +1.0000）
- v1 前 3：`['stylized_mobile:kenney:2d/Toon Characters/character_zombie_attack0.png', 'stylized_mobile:kenney:mini-dungeon/character-human.glb', 'stylized_mobile:kenney:2d/Toon Characters/character_zombie_talk.png']`
- v2 前 3：`['stylized_mobile:kenney:mini-dungeon/character-human.glb', 'stylized_mobile:kenney:mini-dungeon/character-orc.glb', 'stylized_mobile:kenney:mini-characters/character-male-b.glb']`
- 同义词扩展：['orc', 'character']
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:mini-dungeon/character-human.glb', 'ranks': {'semantic': 2, 'bm25': 19}, 'file': 'character-human.glb'}, {'id': 'stylized_mobile:kenney:mini-dungeon/character-orc.glb', 'ranks': {'semantic': 28, 'bm25': 1}, 'file': 'character-orc.glb'}, {'id': 'stylized_mobile:kenney:mini-characters/character-male-b.glb', 'ranks': {'semantic': 19, 'bm25': 14}, 'file': 'character-male-b.glb'}]

### zh-008　人类角色

- 语言 / 分组：zh / test
- v1 Recall@10 = 0.0000，v2 Recall@10 = 1.0000（Δ +1.0000）
- v1 前 3：`['stylized_mobile:kenney:2d/Toon Characters/character_femaleAdventurer_hurt.png', 'stylized_mobile:kenney:2d/Toon Characters/character_femaleAdventurer_show.png', 'stylized_mobile:kenney:2d/Toon Characters/character_femaleAdventurer_attack0.png']`
- v2 前 3：`['stylized_mobile:kenney:mini-dungeon/character-human.glb', 'stylized_mobile:kenney:mini-characters/character-male-b.glb', 'stylized_mobile:kenney:mini-characters/character-male-f.glb']`
- 同义词扩展：['human', 'character']
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:mini-dungeon/character-human.glb', 'ranks': {'semantic': 17, 'bm25': 1}, 'file': 'character-human.glb'}, {'id': 'stylized_mobile:kenney:mini-characters/character-male-b.glb', 'ranks': {'semantic': 29, 'bm25': 14}, 'file': 'character-male-b.glb'}, {'id': 'stylized_mobile:kenney:mini-characters/character-male-f.glb', 'ranks': {'semantic': 47, 'bm25': 18}, 'file': 'character-male-f.glb'}]

### zh-012　宝箱

- 语言 / 分组：zh / dev
- v1 Recall@10 = 0.0000，v2 Recall@10 = 1.0000（Δ +1.0000）
- v1 前 3：`['stylized_mobile:kenney:platformer/lock.glb', 'stylized_mobile:kenney:mini-characters/aid-defibrillator-red.glb', 'stylized_mobile:kenney:castle/tower-square.glb']`
- v2 前 3：`['stylized_mobile:kenney:mini-dungeon/chest.glb', 'stylized_mobile:kenney:platformer/chest.glb', 'stylized_mobile:kenney:platformer/lock.glb']`
- 同义词扩展：['chest', 'treasure']
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:mini-dungeon/chest.glb', 'ranks': {'semantic': 37, 'bm25': 2}, 'file': 'chest.glb'}, {'id': 'stylized_mobile:kenney:platformer/chest.glb', 'ranks': {'semantic': 44, 'bm25': 1}, 'file': 'chest.glb'}, {'id': 'stylized_mobile:kenney:platformer/lock.glb', 'ranks': {'semantic': 1}, 'file': 'lock.glb'}]

### zh-021　弓箭手

- 语言 / 分组：zh / dev
- v1 Recall@10 = 0.0000，v2 Recall@10 = 1.0000（Δ +1.0000）
- v1 前 3：`['stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_attack2.png', 'stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_climb1.png', 'stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_switch0.png']`
- v2 前 3：`['stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_attack2.png', 'stylized_mobile:kenney:mini-forest/character-archer.glb', 'stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_climb1.png']`
- 同义词扩展：['archer']
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_attack2.png', 'ranks': {'semantic': 1}, 'file': 'character_maleAdventurer_attack2.png'}, {'id': 'stylized_mobile:kenney:mini-forest/character-archer.glb', 'ranks': {'bm25': 1}, 'file': 'character-archer.glb'}, {'id': 'stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_climb1.png', 'ranks': {'semantic': 2}, 'file': 'character_maleAdventurer_climb1.png'}]

### zh-022　攻城投石机

- 语言 / 分组：zh / dev
- v1 Recall@10 = 0.0000，v2 Recall@10 = 0.7500（Δ +0.7500）
- v1 前 3：`['stylized_mobile:kenney:platformer/lever.glb', 'stylized_mobile:kenney:castle/siege-tower.glb', 'stylized_mobile:kenney:castle/wall-narrow-stairs-rail.glb']`
- v2 前 3：`['stylized_mobile:kenney:castle/siege-tower.glb', 'stylized_mobile:kenney:castle/siege-ram-demolished.glb', 'stylized_mobile:kenney:castle/siege-ballista.glb']`
- 同义词扩展：['catapult', 'trebuchet', 'siege']
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:castle/siege-tower.glb', 'ranks': {'semantic': 2, 'bm25': 7}, 'file': 'siege-tower.glb'}, {'id': 'stylized_mobile:kenney:castle/siege-ram-demolished.glb', 'ranks': {'semantic': 5, 'bm25': 9}, 'file': 'siege-ram-demolished.glb'}, {'id': 'stylized_mobile:kenney:castle/siege-ballista.glb', 'ranks': {'semantic': 10, 'bm25': 5}, 'file': 'siege-ballista.glb'}]

### zh-023　攻城槌

- 语言 / 分组：zh / dev
- v1 Recall@10 = 0.0000，v2 Recall@10 = 1.0000（Δ +1.0000）
- v1 前 3：`['stylized_mobile:kenney:mini-forest/flag.glb', 'stylized_mobile:kenney:castle/flag-pennant.glb', 'stylized_mobile:kenney:castle/flag.glb']`
- v2 前 3：`['stylized_mobile:kenney:castle/siege-ballista-demolished.glb', 'stylized_mobile:kenney:castle/siege-catapult-demolished.glb', 'stylized_mobile:kenney:castle/siege-ram-demolished.glb']`
- 同义词扩展：['siege']
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:castle/siege-ballista-demolished.glb', 'ranks': {'semantic': 22, 'bm25': 6}, 'file': 'siege-ballista-demolished.glb'}, {'id': 'stylized_mobile:kenney:castle/siege-catapult-demolished.glb', 'ranks': {'semantic': 30, 'bm25': 7}, 'file': 'siege-catapult-demolished.glb'}, {'id': 'stylized_mobile:kenney:castle/siege-ram-demolished.glb', 'ranks': {'semantic': 40, 'bm25': 8}, 'file': 'siege-ram-demolished.glb'}]

### zh-039　吊桥

- 语言 / 分组：zh / test
- v1 Recall@10 = 0.0000，v2 Recall@10 = 1.0000（Δ +1.0000）
- v1 前 3：`['stylized_mobile:kenney:castle/flag-wide.glb', 'stylized_mobile:kenney:platformer/fence-rope.glb', 'stylized_mobile:kenney:mini-forest/fence.glb']`
- v2 前 3：`['stylized_mobile:kenney:castle/bridge-straight.glb', 'stylized_mobile:kenney:mini-forest/bridge.glb', 'stylized_mobile:kenney:castle/bridge-draw.glb']`
- 同义词扩展：['bridge']
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:castle/bridge-straight.glb', 'ranks': {'semantic': 15, 'bm25': 3}, 'file': 'bridge-straight.glb'}, {'id': 'stylized_mobile:kenney:mini-forest/bridge.glb', 'ranks': {'semantic': 27, 'bm25': 1}, 'file': 'bridge.glb'}, {'id': 'stylized_mobile:kenney:castle/bridge-draw.glb', 'ranks': {'semantic': 40, 'bm25': 2}, 'file': 'bridge-draw.glb'}]

## 明显提升（Δ Recall@10 ≥ 0.15）（7）

v1 已有部分召回，混合检索进一步提高。

### en-014　siege catapult

- 语言 / 分组：en / test
- v1 Recall@10 = 0.7000，v2 Recall@10 = 1.0000（Δ +0.3000）
- v1 前 3：`['stylized_mobile:kenney:castle/siege-tower-demolished.glb', 'stylized_mobile:kenney:castle/siege-trebuchet.glb', 'stylized_mobile:kenney:castle/siege-catapult.glb']`
- v2 前 3：`['stylized_mobile:kenney:castle/siege-catapult.glb', 'stylized_mobile:kenney:castle/siege-trebuchet.glb', 'stylized_mobile:kenney:castle/siege-ballista.glb']`
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:castle/siege-catapult.glb', 'ranks': {'semantic': 3, 'bm25': 1}, 'file': 'siege-catapult.glb'}, {'id': 'stylized_mobile:kenney:castle/siege-trebuchet.glb', 'ranks': {'semantic': 2, 'bm25': 6}, 'file': 'siege-trebuchet.glb'}, {'id': 'stylized_mobile:kenney:castle/siege-ballista.glb', 'ranks': {'semantic': 7, 'bm25': 3}, 'file': 'siege-ballista.glb'}]

### en-015　gold uzi

- 语言 / 分组：en / dev
- v1 Recall@10 = 0.6250，v2 Recall@10 = 1.0000（Δ +0.3750）
- v1 前 3：`['stylized_mobile:kenney:weapon/uziLongSilencerGold.glb', 'stylized_mobile:kenney:weapon/uziGold.glb', 'stylized_mobile:kenney:weapon/uziSilencerGold.glb']`
- v2 前 3：`['stylized_mobile:kenney:weapon/uziGold.glb', 'stylized_mobile:kenney:weapon/uziLongSilencerGold.glb', 'stylized_mobile:kenney:weapon/uziLongGold.glb']`
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:weapon/uziGold.glb', 'ranks': {'semantic': 2, 'bm25': 1}, 'file': 'uziGold.glb'}, {'id': 'stylized_mobile:kenney:weapon/uziLongSilencerGold.glb', 'ranks': {'semantic': 1, 'bm25': 4}, 'file': 'uziLongSilencerGold.glb'}, {'id': 'stylized_mobile:kenney:weapon/uziLongGold.glb', 'ranks': {'semantic': 4, 'bm25': 2}, 'file': 'uziLongGold.glb'}]

### en-025　checkpoint flag

- 语言 / 分组：en / dev
- v1 Recall@10 = 0.2857，v2 Recall@10 = 1.0000（Δ +0.7143）
- v1 前 3：`['stylized_mobile:kenney:platformer/flag.glb', 'stylized_mobile:kenney:castle/flag.glb', 'stylized_mobile:kenney:ui/UI Pack/icon_outline_checkmark.png']`
- v2 前 3：`['stylized_mobile:kenney:castle/flag.glb', 'stylized_mobile:kenney:platformer/flag.glb', 'stylized_mobile:kenney:castle/flag-pennant.glb']`
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:castle/flag.glb', 'ranks': {'semantic': 2, 'bm25': 1}, 'file': 'flag.glb'}, {'id': 'stylized_mobile:kenney:platformer/flag.glb', 'ranks': {'semantic': 1, 'bm25': 2}, 'file': 'flag.glb'}, {'id': 'stylized_mobile:kenney:castle/flag-pennant.glb', 'ranks': {'semantic': 28, 'bm25': 4}, 'file': 'flag-pennant.glb'}]

### zh-014　木桶

- 语言 / 分组：zh / test
- v1 Recall@10 = 0.3333，v2 Recall@10 = 1.0000（Δ +0.6667）
- v1 前 3：`['stylized_mobile:kenney:castle/wall-corner-half-tower.glb', 'stylized_mobile:kenney:castle/tower-base.glb', 'stylized_mobile:kenney:food/steamer.glb']`
- v2 前 3：`['stylized_mobile:kenney:platformer/barrel.glb', 'stylized_mobile:kenney:food/barrel.glb', 'stylized_mobile:kenney:mini-dungeon/barrel.glb']`
- 同义词扩展：['barrel']
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:platformer/barrel.glb', 'ranks': {'semantic': 8, 'bm25': 2}, 'file': 'barrel.glb'}, {'id': 'stylized_mobile:kenney:food/barrel.glb', 'ranks': {'semantic': 12, 'bm25': 1}, 'file': 'barrel.glb'}, {'id': 'stylized_mobile:kenney:mini-dungeon/barrel.glb', 'ranks': {'semantic': 21, 'bm25': 3}, 'file': 'barrel.glb'}]

### zh-026　火箭筒

- 语言 / 分组：zh / dev
- v1 Recall@10 = 0.6667，v2 Recall@10 = 1.0000（Δ +0.3333）
- v1 前 3：`['stylized_mobile:kenney:weapon/ammo_rocketModern.glb', 'stylized_mobile:kenney:weapon/rocketlauncherModern.glb', 'stylized_mobile:kenney:weapon/ammo_shotgun.glb']`
- v2 前 3：`['stylized_mobile:kenney:weapon/ammo_rocketModern.glb', 'stylized_mobile:kenney:weapon/rocketlauncherModern.glb', 'stylized_mobile:kenney:weapon/rocketlauncher.glb']`
- 同义词扩展：['rocketlauncher', 'rocket']
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:weapon/ammo_rocketModern.glb', 'ranks': {'semantic': 1, 'bm25': 3}, 'file': 'ammo_rocketModern.glb'}, {'id': 'stylized_mobile:kenney:weapon/rocketlauncherModern.glb', 'ranks': {'semantic': 2, 'bm25': 4}, 'file': 'rocketlauncherModern.glb'}, {'id': 'stylized_mobile:kenney:weapon/rocketlauncher.glb', 'ranks': {'semantic': 7, 'bm25': 2}, 'file': 'rocketlauncher.glb'}]

### zh-027　手榴弹

- 语言 / 分组：zh / test
- v1 Recall@10 = 0.5000，v2 Recall@10 = 1.0000（Δ +0.5000）
- v1 前 3：`['stylized_mobile:kenney:weapon/ammo_machinegunLauncher.glb', 'stylized_mobile:kenney:weapon/ammo_uzi.glb', 'stylized_mobile:kenney:weapon/grenadeSmoke.glb']`
- v2 前 3：`['stylized_mobile:kenney:weapon/grenadeSmoke.glb', 'stylized_mobile:kenney:weapon/grenade.glb', 'stylized_mobile:kenney:weapon/ammo_machinegunLauncher.glb']`
- 同义词扩展：['grenade']
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:weapon/grenadeSmoke.glb', 'ranks': {'semantic': 3, 'bm25': 3}, 'file': 'grenadeSmoke.glb'}, {'id': 'stylized_mobile:kenney:weapon/grenade.glb', 'ranks': {'semantic': 8, 'bm25': 1}, 'file': 'grenade.glb'}, {'id': 'stylized_mobile:kenney:weapon/ammo_machinegunLauncher.glb', 'ranks': {'semantic': 1}, 'file': 'ammo_machinegunLauncher.glb'}]

### zh-028　金色冲锋枪

- 语言 / 分组：zh / test
- v1 Recall@10 = 0.5000，v2 Recall@10 = 1.0000（Δ +0.5000）
- v1 前 3：`['stylized_mobile:kenney:weapon/uziLongSilencerGold.glb', 'stylized_mobile:kenney:weapon/sniperSand.glb', 'stylized_mobile:kenney:weapon/uziSilencerGold.glb']`
- v2 前 3：`['stylized_mobile:kenney:weapon/uziGold.glb', 'stylized_mobile:kenney:weapon/uziLongSilencerGold.glb', 'stylized_mobile:kenney:weapon/uziSilencerGold.glb']`
- 同义词扩展：['uzi', 'smg', 'submachine', 'gold', 'golden']
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:weapon/uziGold.glb', 'ranks': {'semantic': 4, 'bm25': 1}, 'file': 'uziGold.glb'}, {'id': 'stylized_mobile:kenney:weapon/uziLongSilencerGold.glb', 'ranks': {'semantic': 1, 'bm25': 4}, 'file': 'uziLongSilencerGold.glb'}, {'id': 'stylized_mobile:kenney:weapon/uziSilencerGold.glb', 'ranks': {'semantic': 3, 'bm25': 3}, 'file': 'uziSilencerGold.glb'}]

## 仍未解决（两边 Recall@10 均为 0）（6）

词表没覆盖、文件名与查询对不上、或相关资产在语义与词法两路都进不了前 10。不要为这些条目事后补词。

### en-022　drawbridge

- 语言 / 分组：en / test
- v1 Recall@10 = 0.0000，v2 Recall@10 = 0.0000（Δ +0.0000）
- v1 前 3：`['stylized_mobile:kenney:castle/flag-wide.glb', 'stylized_mobile:kenney:castle/bridge-straight.glb', 'stylized_mobile:kenney:mini-dungeon/banner.glb']`
- v2 前 3：`['stylized_mobile:kenney:castle/flag-wide.glb', 'stylized_mobile:kenney:castle/bridge-straight.glb', 'stylized_mobile:kenney:mini-dungeon/banner.glb']`
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:castle/flag-wide.glb', 'ranks': {'semantic': 1}, 'file': 'flag-wide.glb'}, {'id': 'stylized_mobile:kenney:castle/bridge-straight.glb', 'ranks': {'semantic': 2}, 'file': 'bridge-straight.glb'}, {'id': 'stylized_mobile:kenney:mini-dungeon/banner.glb', 'ranks': {'semantic': 3}, 'file': 'banner.glb'}]

### zh-003　长方形盾牌

- 语言 / 分组：zh / test
- v1 Recall@10 = 0.0000，v2 Recall@10 = 0.0000（Δ +0.0000）
- v1 前 3：`['stylized_mobile:kenney:food/cutting-board.glb', 'stylized_mobile:kenney:food/popsicle-stick.glb', 'stylized_mobile:kenney:ui/UI Pack/button_rectangle_depth_line.png']`
- v2 前 3：`['stylized_mobile:kenney:ui/UI Pack/input_outline_rectangle.png', 'stylized_mobile:kenney:ui/UI Pack/button_rectangle_gradient.png', 'stylized_mobile:kenney:ui/UI Pack/button_rectangle_depth_border.png']`
- 同义词扩展：['rectangle', 'rectangular', 'shield']
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:ui/UI Pack/input_outline_rectangle.png', 'ranks': {'semantic': 9, 'bm25': 5}, 'file': 'input_outline_rectangle.png'}, {'id': 'stylized_mobile:kenney:ui/UI Pack/button_rectangle_gradient.png', 'ranks': {'semantic': 6, 'bm25': 9}, 'file': 'button_rectangle_gradient.png'}, {'id': 'stylized_mobile:kenney:ui/UI Pack/button_rectangle_depth_border.png', 'ranks': {'semantic': 5, 'bm25': 11}, 'file': 'button_rectangle_depth_border.png'}]

### zh-010　男性角色

- 语言 / 分组：zh / dev
- v1 Recall@10 = 0.0000，v2 Recall@10 = 0.0000（Δ +0.0000）
- v1 前 3：`['stylized_mobile:kenney:2d/Toon Characters/character_femaleAdventurer_attack0.png', 'stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_attack2.png', 'stylized_mobile:kenney:2d/Toon Characters/character_femaleAdventurer_walk4.png']`
- v2 前 3：`['stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_interact.png', 'stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_talk.png', 'stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_hold.png']`
- 同义词扩展：['male', 'man', 'character']
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_interact.png', 'ranks': {'semantic': 17, 'bm25': 17}, 'file': 'character_maleAdventurer_interact.png'}, {'id': 'stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_talk.png', 'ranks': {'semantic': 14, 'bm25': 25}, 'file': 'character_maleAdventurer_talk.png'}, {'id': 'stylized_mobile:kenney:2d/Toon Characters/character_maleAdventurer_hold.png', 'ranks': {'semantic': 26, 'bm25': 14}, 'file': 'character_maleAdventurer_hold.png'}]

### zh-031　横向滑动条

- 语言 / 分组：zh / dev
- v1 Recall@10 = 0.0000，v2 Recall@10 = 0.0000（Δ +0.0000）
- v1 前 3：`['stylized_mobile:kenney:food/bacon-raw.glb', 'stylized_mobile:kenney:food/bacon.glb', 'stylized_mobile:kenney:platformer/spike-block-wide.glb']`
- v2 前 3：`['stylized_mobile:kenney:food/bacon-raw.glb', 'stylized_mobile:kenney:food/bacon.glb', 'stylized_mobile:kenney:platformer/spike-block-wide.glb']`
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:food/bacon-raw.glb', 'ranks': {'semantic': 1}, 'file': 'bacon-raw.glb'}, {'id': 'stylized_mobile:kenney:food/bacon.glb', 'ranks': {'semantic': 2}, 'file': 'bacon.glb'}, {'id': 'stylized_mobile:kenney:platformer/spike-block-wide.glb', 'ranks': {'semantic': 3}, 'file': 'spike-block-wide.glb'}]

### zh-037　牛油果

- 语言 / 分组：zh / dev
- v1 Recall@10 = 0.0000，v2 Recall@10 = 0.0000（Δ +0.0000）
- v1 前 3：`['stylized_mobile:kenney:food/pear.glb', 'stylized_mobile:kenney:food/pear-half.glb', 'stylized_mobile:kenney:food/pineapple.glb']`
- v2 前 3：`['stylized_mobile:kenney:food/pear.glb', 'stylized_mobile:kenney:food/pear-half.glb', 'stylized_mobile:kenney:food/pineapple.glb']`
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:food/pear.glb', 'ranks': {'semantic': 1}, 'file': 'pear.glb'}, {'id': 'stylized_mobile:kenney:food/pear-half.glb', 'ranks': {'semantic': 2}, 'file': 'pear-half.glb'}, {'id': 'stylized_mobile:kenney:food/pineapple.glb', 'ranks': {'semantic': 3}, 'file': 'pineapple.glb'}]

### zh-042　地牢里的陷阱

- 语言 / 分组：zh / dev
- v1 Recall@10 = 0.0000，v2 Recall@10 = 0.0000（Δ +0.0000）
- v1 前 3：`['stylized_mobile:kenney:mini-dungeon/wall.glb', 'stylized_mobile:kenney:mini-dungeon/wall-narrow.glb', 'stylized_mobile:kenney:food/bowl-broth.glb']`
- v2 前 3：`['stylized_mobile:kenney:mini-dungeon/wall.glb', 'stylized_mobile:kenney:mini-dungeon/wall-narrow.glb', 'stylized_mobile:kenney:food/bowl-broth.glb']`
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:mini-dungeon/wall.glb', 'ranks': {'semantic': 1}, 'file': 'wall.glb'}, {'id': 'stylized_mobile:kenney:mini-dungeon/wall-narrow.glb', 'ranks': {'semantic': 2}, 'file': 'wall-narrow.glb'}, {'id': 'stylized_mobile:kenney:food/bowl-broth.glb', 'ranks': {'semantic': 3}, 'file': 'bowl-broth.glb'}]

## 回退（v1 有召回，v2 变为 0）（0）

融合或扩展把不相关的词法命中抬上来，挤掉了原来语义能排进前 10 的相关资产。这是混合检索的真实代价，必须讲。

（无）

## 明显下降（Δ ≤ −0.15，但 v2 未到 0）（2）

同上，属于排序被词法干扰。

### en-020　rocket launcher

- 语言 / 分组：en / dev
- v1 Recall@10 = 1.0000，v2 Recall@10 = 0.6667（Δ -0.3333）
- v1 前 3：`['stylized_mobile:kenney:weapon/rocketlauncherModern.glb', 'stylized_mobile:kenney:weapon/ammo_rocketModern.glb', 'stylized_mobile:kenney:weapon/rocketlauncher.glb']`
- v2 前 3：`['stylized_mobile:kenney:weapon/ammo_rocketModern.glb', 'stylized_mobile:kenney:weapon/machinegunLauncher.glb', 'stylized_mobile:kenney:weapon/ammo_machinegunLauncher.glb']`
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:weapon/ammo_rocketModern.glb', 'ranks': {'semantic': 2, 'bm25': 2}, 'file': 'ammo_rocketModern.glb'}, {'id': 'stylized_mobile:kenney:weapon/machinegunLauncher.glb', 'ranks': {'semantic': 7, 'bm25': 3}, 'file': 'machinegunLauncher.glb'}, {'id': 'stylized_mobile:kenney:weapon/ammo_machinegunLauncher.glb', 'ranks': {'semantic': 15, 'bm25': 4}, 'file': 'ammo_machinegunLauncher.glb'}]

### zh-035　游戏手柄图标

- 语言 / 分组：zh / test
- v1 Recall@10 = 0.4000，v2 Recall@10 = 0.2000（Δ -0.2000）
- v1 前 3：`['stylized_mobile:kenney:icons/Game Icons/exitLeft.png', 'stylized_mobile:kenney:icons/Game Icons/exitRight.png', 'stylized_mobile:kenney:icons/Game Icons/leaderboardsSimple.png']`
- v2 前 3：`['stylized_mobile:kenney:icons/Game Icons/gamepad.png', 'stylized_mobile:kenney:icons/Game Icons/exitLeft.png', 'stylized_mobile:kenney:icons/Game Icons/exitRight.png']`
- 同义词扩展：['icon']
- v2 前 3 的分路名次：[{'id': 'stylized_mobile:kenney:icons/Game Icons/gamepad.png', 'ranks': {'semantic': 17, 'bm25': 1}, 'file': 'gamepad.png'}, {'id': 'stylized_mobile:kenney:icons/Game Icons/exitLeft.png', 'ranks': {'semantic': 1}, 'file': 'exitLeft.png'}, {'id': 'stylized_mobile:kenney:icons/Game Icons/exitRight.png', 'ranks': {'semantic': 2}, 'file': 'exitRight.png'}]

## 兵器类查询还剩什么

见 `eval/results_v2.md` 第 3 节的兵器专题表。语义一路的剑/刀混淆没有从模型上消失：
「一把剑」在 v2 能排到第一，是因为 BM25 在 `weapon-sword.glb` 上是第 1、语义上大约是第 30 多名，RRF 把它托上来。
若关掉词法一路，问题会回到 v1。后续若做重排或换预览，应在同一套金标上再比一次。

