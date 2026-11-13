#!/usr/bin/env python3
"""根据目录元数据（文件名 / 类型 / 包名）自动起草检索金标。

【必须由作者审阅】本文件生成的查询与相关资产是根据目录自动起草的，
不是人工逐条看过预览后标定的，更不是根据检索结果回改的。
面试前请打开 eval/gold_queries.yaml，核对相关资产是否合理，
把 status 从 auto_drafted_needs_review 改成 reviewed。

生成时机：在 build_library 之后、measure 之前。不要看检索结果再改规则。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from artgate.paths import CATALOG, EVAL  # noqa: E402

OUT = EVAL / "gold_queries.yaml"
README = EVAL / "GOLD_QUERIES_README.md"


def load_catalog():
    data = json.loads(Path(CATALOG).read_text(encoding="utf-8"))
    return data["assets"]


def _blob(a):
    return " ".join(
        str(x or "")
        for x in (
            a.get("original_filename"),
            a.get("canonical_name"),
            a.get("source_pack"),
            a.get("description"),
            a.get("asset_type"),
            a.get("id"),
        )
    ).lower()


def match(assets, project, pred, grade):
    hits = []
    for a in assets:
        if project and a.get("project_id") != project:
            continue
        if a.get("status") not in ("approved", "appeal_passed", None):
            # 种子库都是 approved；若字段缺失也算
            if a.get("status") not in (None, "approved", "appeal_passed"):
                continue
        if pred(a):
            hits.append({"asset_id": a["id"], "grade": grade, "filename": a.get("original_filename")})
    return hits


def fn_is(name):
    name = name.lower()

    def p(a):
        return (a.get("original_filename") or "").lower() == name or (a.get("original_filename") or "").lower().startswith(name)

    return p


def fn_regex(rx, pack_contains=None):
    r = re.compile(rx, re.I)

    def p(a):
        if pack_contains and pack_contains.lower() not in (a.get("source_pack") or "").lower():
            return False
        return bool(r.search(a.get("original_filename") or ""))

    return p


def fn_stem_in(stems, pack_contains=None):
    stems = {s.lower() for s in stems}

    def p(a):
        if pack_contains and pack_contains.lower() not in (a.get("source_pack") or "").lower():
            return False
        stem = Path(a.get("original_filename") or "").stem.lower()
        return stem in stems or (a.get("original_filename") or "").lower() in {s + ".glb" for s in stems} or {s + ".png" for s in stems}

    return p


def pack_and_name(pack, rx):
    r = re.compile(rx, re.I)

    def p(a):
        return pack.lower() in (a.get("source_pack") or "").lower() and bool(r.search(a.get("original_filename") or ""))

    return p


def type_and_name(atype, rx, project=None):
    r = re.compile(rx, re.I)

    def p(a):
        if project and a.get("project_id") != project:
            return False
        return a.get("asset_type") == atype and bool(r.search(_blob(a)))

    return p


def build_specs():
    """查询规格：相关资产用规则匹配，不看检索结果。"""
    M = "stylized_mobile"
    R = "realistic"
    q = []

    def add(**kw):
        q.append(kw)

    # —— 中文，风格化库 ——
    add(id="zh-001", query="一把剑", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^weapon-sword\.glb$"), grade1=fn_regex(r"sword"))
    add(id="zh-002", query="圆形盾牌", lang="zh", project_id=M, difficulty="medium",
        grade2=fn_regex(r"^shield-round\.glb$"),
        note="相近干扰：shield-rectangle")
    add(id="zh-003", query="长方形盾牌", lang="zh", project_id=M, difficulty="medium",
        grade2=fn_regex(r"^shield-rectangle\.glb$"))
    add(id="zh-004", query="长矛", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^weapon-spear\.glb$"))
    add(id="zh-005", query="一把弓", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^weapon-bow\.glb$"), grade1=fn_regex(r"weapon-arrow"))
    add(id="zh-006", query="一支箭", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^weapon-arrow\.glb$|^arrow\.glb$"))
    add(id="zh-007", query="兽人角色", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^character-orc\.glb$"))
    add(id="zh-008", query="人类角色", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^character-human\.glb$"))
    add(id="zh-009", query="女性角色", lang="zh", project_id=M, difficulty="medium",
        grade2=fn_regex(r"character-female|femaleAdventurer|female adventurer|female person"))
    add(id="zh-010", query="男性角色", lang="zh", project_id=M, difficulty="medium",
        grade2=fn_regex(r"character-male"))
    add(id="zh-011", query="轮椅", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"wheelchair"))
    add(id="zh-012", query="宝箱", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^chest\.glb$"))
    add(id="zh-013", query="金币", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^coin\.glb$"))
    add(id="zh-014", query="木桶", lang="zh", project_id=M, difficulty="medium",
        grade2=fn_regex(r"^barrel\.glb$"),
        note="多个包里都有 barrel，都标为完全相关")
    add(id="zh-015", query="苹果", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^apple\.glb$|^apple-half\.glb$"),
        note="干扰：avocado")
    add(id="zh-016", query="香蕉", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^banana\.glb$"))
    add(id="zh-017", query="汉堡", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^burger.*\.glb$"))
    add(id="zh-018", query="生日蛋糕", lang="zh", project_id=M, difficulty="medium",
        grade2=fn_regex(r"^cake-birthday\.glb$"), grade1=fn_regex(r"^cake\.glb$|^cupcake\.glb$"))
    add(id="zh-019", query="一棵树", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^tree\.glb$|^tree-high\.glb$"))
    add(id="zh-020", query="帐篷", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^tent\.glb$"))
    add(id="zh-021", query="弓箭手", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^character-archer\.glb$"))
    add(id="zh-022", query="攻城投石机", lang="zh", project_id=M, difficulty="medium",
        grade2=fn_regex(r"^siege-catapult\.glb$"),
        grade1=fn_regex(r"^siege-trebuchet|^siege-catapult-demolished"))
    add(id="zh-023", query="攻城槌", lang="zh", project_id=M, difficulty="medium",
        grade2=fn_regex(r"^siege-ram\.glb$"), grade1=fn_regex(r"^siege-ram-demolished"))
    add(id="zh-024", query="手枪", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^pistol\.glb$|^pistolSilencer\.glb$"),
        note="风格化库里的 Kenney 手枪，不是 Poly Haven 写实手枪")
    add(id="zh-025", query="狙击枪", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^sniper\.glb$|^sniperSand\.glb$"))
    add(id="zh-026", query="火箭筒", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^rocketlauncher.*\.glb$"))
    add(id="zh-027", query="手榴弹", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^grenade.*\.glb$"))
    add(id="zh-028", query="金色冲锋枪", lang="zh", project_id=M, difficulty="hard",
        grade2=fn_regex(r"^uziGold\.glb$|^uziLongGold\.glb$|^uziSilencerGold\.glb$|^uziLongSilencerGold\.glb$"),
        grade1=fn_regex(r"^uzi.*\.glb$"),
        note="近重复：金色与普通 uzi，靠颜色/装饰区分")
    add(id="zh-029", query="矩形按钮", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^button_rectangle"))
    add(id="zh-030", query="圆形按钮", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^button_round"))
    add(id="zh-031", query="横向滑动条", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^slide_horizontal"))
    add(id="zh-032", query="勾选框", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^check_"))
    add(id="zh-033", query="奖杯图标", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^trophy\.png$"))
    add(id="zh-034", query="星星图标", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^star\.png$"))
    add(id="zh-035", query="游戏手柄图标", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^gamepad"))
    add(id="zh-036", query="纸杯蛋糕", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^cupcake\.glb$"))
    add(id="zh-037", query="牛油果", lang="zh", project_id=M, difficulty="hard",
        grade2=fn_regex(r"^avocado\.glb$|^advocado-half\.glb$|^avocado"),
        note="与苹果外形接近，是难点。Kenney 有拼写 advocado-half。")
    add(id="zh-038", query="西瓜", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^watermelon"))
    add(id="zh-039", query="吊桥", lang="zh", project_id=M, difficulty="medium",
        grade2=fn_regex(r"^bridge-draw\.glb$"), grade1=fn_regex(r"^bridge"))
    add(id="zh-040", query="城堡旗帜", lang="zh", project_id=M, difficulty="medium",
        grade2=fn_regex(r"^flag", pack_contains="castle"))
    add(id="zh-041", query="梯子", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^ladder\.glb$"))
    add(id="zh-042", query="地牢里的陷阱", lang="zh", project_id=M, difficulty="medium",
        grade2=fn_regex(r"^trap\.glb$"))
    add(id="zh-043", query="火焰喷射器", lang="zh", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^flamethrower"))
    add(id="zh-044", query="卡通风格的女性冒险者", lang="zh", project_id=M, difficulty="medium",
        grade2=fn_regex(r"femaleAdventurer"),
        note="Toon Characters 文件名是 character_femaleAdventurer_*.png")
    add(id="zh-045", query="音乐开关图标", lang="zh", project_id=M, difficulty="medium",
        grade2=fn_regex(r"^musicOn\.png$|^musicOff\.png$"))

    # —— 英文，风格化 ——
    add(id="en-001", query="a sword", lang="en", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^weapon-sword\.glb$"), grade1=fn_regex(r"sword"))
    add(id="en-002", query="a round shield", lang="en", project_id=M, difficulty="medium",
        grade2=fn_regex(r"^shield-round\.glb$"))
    add(id="en-003", query="an orc character", lang="en", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^character-orc\.glb$"))
    add(id="en-004", query="birthday cake", lang="en", project_id=M, difficulty="medium",
        grade2=fn_regex(r"^cake-birthday\.glb$"), grade1=fn_regex(r"^cake\.glb$|^cupcake"))
    add(id="en-005", query="a pistol", lang="en", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^pistol\.glb$|^pistolSilencer\.glb$"))
    add(id="en-006", query="sniper rifle", lang="en", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^sniper\.glb$|^sniperSand\.glb$"))
    add(id="en-007", query="wooden barrel", lang="en", project_id=M, difficulty="medium",
        grade2=fn_regex(r"^barrel\.glb$"))
    add(id="en-008", query="treasure chest", lang="en", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^chest\.glb$"))
    add(id="en-009", query="a cartoon tree", lang="en", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^tree\.glb$|^tree-high\.glb$"))
    add(id="en-010", query="wheelchair", lang="en", project_id=M, difficulty="easy",
        grade2=fn_regex(r"wheelchair"))
    add(id="en-011", query="UI button", lang="en", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^button_"))
    add(id="en-012", query="hamburger", lang="en", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^burger.*\.glb$"))
    add(id="en-013", query="bow and arrow", lang="en", project_id=M, difficulty="medium",
        grade2=fn_regex(r"^weapon-bow\.glb$|^weapon-arrow\.glb$"))
    add(id="en-014", query="siege catapult", lang="en", project_id=M, difficulty="medium",
        grade2=fn_regex(r"^siege-catapult\.glb$"), grade1=fn_regex(r"^siege-"))
    add(id="en-015", query="gold uzi", lang="en", project_id=M, difficulty="hard",
        grade2=fn_regex(r"uzi.*Gold|uziGold"), grade1=fn_regex(r"^uzi"))
    add(id="en-016", query="female character", lang="en", project_id=M, difficulty="medium",
        grade2=fn_regex(r"character-female|femaleAdventurer|female adventurer|female person"))
    add(id="en-017", query="a tent", lang="en", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^tent\.glb$"))
    add(id="en-018", query="apple", lang="en", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^apple\.glb$|^apple-half\.glb$"))
    add(id="en-019", query="avocado", lang="en", project_id=M, difficulty="hard",
        grade2=fn_regex(r"avocado|advocado"))
    add(id="en-020", query="rocket launcher", lang="en", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^rocketlauncher"))
    add(id="en-021", query="trophy icon", lang="en", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^trophy\.png$"))
    add(id="en-022", query="drawbridge", lang="en", project_id=M, difficulty="medium",
        grade2=fn_regex(r"^bridge-draw\.glb$"))
    add(id="en-023", query="flamethrower", lang="en", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^flamethrower"))
    add(id="en-024", query="a spear", lang="en", project_id=M, difficulty="easy",
        grade2=fn_regex(r"^weapon-spear\.glb$"))
    add(id="en-025", query="checkpoint flag", lang="en", project_id=M, difficulty="hard",
        grade2=fn_regex(r"^flag", pack_contains="mini-forest"),
        grade1=fn_regex(r"^flag"))

    # —— 写实项目 ——
    add(id="zh-046", query="一台复古相机", lang="zh", project_id=R, difficulty="easy",
        grade2=fn_regex(r"Camera_01"))
    add(id="zh-047", query="写实风格的手枪", lang="zh", project_id=R, difficulty="medium",
        grade2=fn_regex(r"service_pistol|Service"))
    add(id="zh-048", query="皮沙发", lang="zh", project_id=R, difficulty="easy",
        grade2=fn_regex(r"sofa_02|Sofa"))
    add(id="zh-049", query="红酒瓶", lang="zh", project_id=R, difficulty="easy",
        grade2=fn_regex(r"wine_bottles"))
    add(id="zh-050", query="砖墙贴图", lang="zh", project_id=R, difficulty="easy",
        grade2=fn_regex(r"brick_wall"))
    add(id="en-026", query="vintage camera", lang="en", project_id=R, difficulty="easy",
        grade2=fn_regex(r"Camera_01"))
    add(id="en-027", query="a realistic pistol", lang="en", project_id=R, difficulty="medium",
        grade2=fn_regex(r"service_pistol"))
    add(id="en-028", query="wooden table", lang="en", project_id=R, difficulty="easy",
        grade2=fn_regex(r"wooden_table"))
    add(id="en-029", query="rusty metal texture", lang="en", project_id=R, difficulty="medium",
        grade2=fn_regex(r"rusty_metal"))
    add(id="en-030", query="horse statue", lang="en", project_id=R, difficulty="easy",
        grade2=fn_regex(r"horse_statue"))
    add(id="zh-051", query="办公桌", lang="zh", project_id=R, difficulty="easy",
        grade2=fn_regex(r"metal_office_desk|office_desk"))
    add(id="zh-052", query="墙上的钟", lang="zh", project_id=R, difficulty="easy",
        grade2=fn_regex(r"wall_clock"))
    add(id="en-031", query="ceramic vase", lang="en", project_id=R, difficulty="easy",
        grade2=fn_regex(r"ceramic_vase"))
    add(id="en-032", query="leather texture", lang="en", project_id=R, difficulty="medium",
        grade2=fn_regex(r"leather"))
    add(id="zh-053", query="螺栓步枪", lang="zh", project_id=R, difficulty="medium",
        grade2=fn_regex(r"bolt_action_rifle"))

    # —— 风格限定 / 宽查询（仍有明确相关集）——
    add(id="zh-054", query="武器", lang="zh", project_id=M, difficulty="hard",
        grade2=lambda a: a.get("asset_type") == "weapon",
        note="过宽查询：产品应提示加过滤。金标把类型=weapon 全部视为相关，Recall 会偏低或偏高都要如实记。")
    add(id="en-033", query="food", lang="en", project_id=M, difficulty="hard",
        grade2=fn_regex(r".*", pack_contains="food") if False else (lambda a: "food" in (a.get("source_pack") or "").lower()),
        note="过宽查询。")

    return q


def resolve_image_queries(assets):
    """以图搜图：用库内预览当查询，相关项是自己及同 stem 变体。"""
    specs = []
    targets = [
        ("img-001", "weapon-sword.glb", "stylized_mobile", "zh"),
        ("img-002", "apple.glb", "stylized_mobile", "zh"),
        ("img-003", "character-orc.glb", "stylized_mobile", "en"),
        ("img-004", "Camera_01", "realistic", "en"),
        ("img-005", "button_rectangle_flat.png", "stylized_mobile", "zh"),
        ("img-006", "shield-round.glb", "stylized_mobile", "zh"),
        ("img-007", "trophy.png", "stylized_mobile", "en"),
        ("img-008", "service_pistol", "realistic", "en"),
    ]
    for qid, name, proj, lang in targets:
        def pred_factory(n):
            def p(a):
                fn = (a.get("original_filename") or "") + " " + (a.get("id") or "")
                return n.lower() in fn.lower()
            return p
        specs.append({
            "id": qid,
            "query": f"[image:{name}]",
            "lang": lang,
            "project_id": proj,
            "difficulty": "medium",
            "modality": "image",
            "image_from_filename": name,
            "grade2": pred_factory(name),
        })
    return specs


def main():
    assets = load_catalog()
    print("catalog", len(assets))
    specs = build_specs() + resolve_image_queries(assets)
    queries = []
    skipped = []
    for s in specs:
        g2 = match(assets, s["project_id"], s.get("grade2") or (lambda a: False), 2) if s.get("grade2") else []
        g1 = match(assets, s["project_id"], s.get("grade1") or (lambda a: False), 1) if s.get("grade1") else []
        # 去重：grade2 优先
        seen = {x["asset_id"] for x in g2}
        g1 = [x for x in g1 if x["asset_id"] not in seen]
        rel = g2 + g1
        item = {
            "id": s["id"],
            "query": s["query"],
            "lang": s["lang"],
            "project_id": s["project_id"],
            "modality": s.get("modality", "text"),
            "difficulty": s.get("difficulty", "medium"),
            "status": "auto_drafted_needs_review",
            "relevant": rel,
            "n_relevant": len(rel),
            "note": s.get("note", ""),
        }
        if s.get("image_from_filename"):
            # 填入预览路径
            cands = [a for a in assets if s["image_from_filename"].lower() in ((a.get("original_filename") or "") + (a.get("id") or "")).lower() and a.get("project_id") == s["project_id"]]
            if cands and cands[0].get("preview_path"):
                item["image_path"] = cands[0]["preview_path"]
                item["image_asset_id"] = cands[0]["id"]
            else:
                skipped.append({**item, "skip_reason": "找不到查询图"})
                continue
        if not rel:
            skipped.append({**item, "skip_reason": "目录中匹配不到相关资产，不进入正式指标"})
            continue
        queries.append(item)

    payload = {
        "status": "auto_drafted_needs_review",
        "warning": (
            "这些查询和相关资产是脚本根据文件名 / 包名 / 类型自动起草的，"
            "必须由作者人工审阅后才能作为面试口径。"
            "生成时没有参考任何检索结果。"
        ),
        "n_queries": len(queries),
        "n_skipped": len(skipped),
        "queries": queries,
        "skipped": skipped,
    }
    EVAL.mkdir(parents=True, exist_ok=True)
    OUT.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    README.write_text(
        "\n".join([
            "# 检索金标说明（请作者审阅）",
            "",
            "状态：**auto_drafted_needs_review**。",
            "",
            "本金标由 `scripts/generate_gold.py` 根据 `data/catalog.json` 的文件名、包名和类型自动起草。",
            "起草时**没有运行检索，也没有根据模型输出回改查询**。这是为了避免「边看结果边改题」。",
            "",
            "请你逐条核对：",
            "1. 这条查询的相关资产是不是你认为美术会接受的「可复用结果」；",
            "2. grade 2（完全相关）和 grade 1（部分相关）的划分是否合理，例如「金色 uzi」是否应排除普通 uzi；",
            "3. 过宽查询（「武器」「food」）的相关集是否过大，要不要从正式指标里拿掉；",
            "4. 以图搜图用的是库内预览，自己搜自己偏容易，只能说明管线通了，不能单独当产品效果宣传。",
            "",
            "审阅后把 YAML 里的 `status` 改成 `reviewed`，并删掉你不认可的条目。",
            "在此之前，简历里的 Recall / nDCG 必须注明「金标未经人工审阅，数字仅供参考」。",
            "",
        ]),
        encoding="utf-8",
    )
    print("wrote", OUT, "queries", len(queries), "skipped", len(skipped))
    from collections import Counter
    print("by lang", Counter(x["lang"] for x in queries))
    print("by modality", Counter(x["modality"] for x in queries))
    if skipped:
        print("skipped:")
        for s in skipped:
            print(" ", s["id"], s["query"], s.get("skip_reason"))


if __name__ == "__main__":
    main()
