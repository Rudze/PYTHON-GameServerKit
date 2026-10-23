from server import content
from server.modules import character
from server.modules.movement import read_state
from server.stats import Gauge, Progression


def test_gauge_bounds_and_callback():
    seen = []
    gauge = Gauge(100, on_change=seen.append)
    assert gauge.remove(30) == 30 and gauge.value == 70
    assert gauge.add(100) == 30 and gauge.value == 100
    assert gauge.add(5) == 0
    assert len(seen) == 2                     # no change, no callback


def test_progression_levels():
    progression = Progression(1, 0, max_level=3, exp_per_level=100)
    assert progression.add_exp(350) == 2      # 100 to level 2, 200 to level 3
    assert progression.level == 3 and progression.exp == 0


def test_names():
    assert character.clean_name("  Élise   Durand ") == "Élise Durand"
    assert character.clean_name("ab") is None
    assert character.clean_name("_bad") is None
    assert character.clean_name("x" * 17) is None


def test_state_is_clamped_and_typed():
    data = {"x": 1e9, "y": 0, "z": 2, "rot": 1, "speed": 3, "vy": 0, "air": True, "crouch": "yes", "anim": "run"}
    state = read_state(data)
    assert state["x"] == content.RULES.state_numbers["x"]
    assert state["air"] is True and state["crouch"] is False and state["anim"] == "run"
    assert read_state({**data, "speed": "fast"}) is None
    assert read_state({**data, "speed": float("nan")}) is None


def test_content_hash_is_stable():
    first = content.content_hash
    content.load()
    assert content.content_hash == first and len(first) == 16
