from allfather.eval.metrics import score
from allfather.eval.resolution import SymbolResolver, ranking_slots


def answer(*names):
    return {"functions": [{"file": "m.py", "name": name} for name in names]}


def test_resolution_never_uses_gold_and_does_not_repair_wrong_qualifiers():
    resolver = SymbolResolver(["m.py::Right.run", "m.py::Other.run", "m.py::Owner.only"])
    resolved = resolver.answer(answer("run", "Wrong.run", "only", "Right.run"))
    assert [r.status for r in resolved] == ["ambiguous", "invalid", "resolved", "exact"]
    before = ranking_slots(resolved)
    assert score(before, ["m.py::Right.run"], [1, 3, 4]).first_rank == 4
    assert score(before, ["m.py::Owner.only"], [1, 3, 4]).first_rank == 3
    assert ranking_slots(resolver.answer(answer("run", "Wrong.run", "only", "Right.run"))) == before


def test_collision_in_inventory_is_ambiguous_even_for_exact_names():
    resolver = SymbolResolver(["m.py::A.run", "m.py::A.run"])
    assert [r.status for r in resolver.answer(answer("A.run", "run"))] == ["ambiguous"] * 2


def test_bad_predictions_and_duplicate_aliases_keep_their_slots():
    resolver = SymbolResolver(["m.py::A.one", "m.py::two"])
    result = resolver.answer({"functions": [None, {}, *answer("one", "A.one", "two")["functions"]]})
    assert [r.status for r in result] == ["invalid", "invalid", "resolved", "duplicate", "exact"]
    assert score(ranking_slots(result), ["m.py::two"], [1, 5]).first_rank == 5


def test_normalization_preserves_dotfiles_and_rejects_parent_paths():
    resolver = SymbolResolver([".hidden.py::A.run", "dir/m.py::A.run"])
    assert (
        resolver.resolve({"file": "./.hidden.py", "name": "A::run"}, 1).canonical
        == ".hidden.py::A.run"
    )
    assert resolver.resolve({"file": "dir\\m.py", "name": "run"}, 1).canonical == "dir/m.py::A.run"
    for path in ("../dir/m.py", "/dir/m.py", "C:/dir/m.py"):
        assert resolver.resolve({"file": path, "name": "run"}, 1).status == "invalid"
