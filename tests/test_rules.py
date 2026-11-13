from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from artgate.config import clear_caches, load_template, make_canonical, naming_regex
from artgate.precheck.image_specs import is_power_of_two
from artgate.precheck.engine import run_precheck
from artgate.paths import REPO_ROOT


def test_pot():
    assert is_power_of_two(512)
    assert is_power_of_two(2048)
    assert not is_power_of_two(1000)
    assert not is_power_of_two(0)


def test_naming():
    clear_caches()
    t = load_template("stylized_mobile")
    rx = naming_regex(t)
    name = make_canonical(t, "weapon", "sword", "glb")
    assert name == "m_wpn_sword_lod0_v001.glb"
    assert rx.match(name)
    assert not rx.match("final_final2.glb")
    t2 = load_template("realistic")
    assert naming_regex(t2).match(make_canonical(t2, "prop", "camera", "glb"))
    assert not naming_regex(t2).match(name)  # m_ 不应匹配 r_


def test_sword_precheck_if_data_present():
    src = REPO_ROOT / "data/raw/kenney/3d/mini-dungeon/weapon-sword.glb"
    if not src.exists():
        return
    clear_caches()
    t = load_template("stylized_mobile")
    canon = make_canonical(t, "weapon", "sword", "glb")
    r = run_precheck(src, "stylized_mobile", asset_type="weapon", canonical_name=canon, skip_vlm=True)
    assert r["overall"] == "pass"
    by = {i["check_id"]: i for i in r["items"]}
    assert by["naming"]["status"] == "pass"
    assert by["poly_budget"]["measured"] == 80
    assert by["gltf_valid"]["status"] == "pass"


if __name__ == "__main__":
    test_pot()
    test_naming()
    test_sword_precheck_if_data_present()
    print("ok")
