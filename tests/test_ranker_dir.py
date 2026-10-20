from pathlib import Path

from allfather.rank import ltr


def test_rankers_load_from_the_directory_they_are_given(monkeypatch, tmp_path):
    loaded: list[Path] = []
    monkeypatch.setattr(ltr, "_load", lambda path: loaded.append(path) or path)
    monkeypatch.setattr(ltr.HybridRetriever, "__init__", lambda self, *args, **kwargs: None)
    monkeypatch.setattr(ltr, "FeatureExtractor", lambda *args, **kwargs: None)
    monkeypatch.setattr(ltr, "issue_memory", lambda retriever: None)
    ltr.LTRRetriever(None, None, model_dir=tmp_path)
    assert sorted(p.name for p in loaded) == ["ltr_file.txt", "ltr_function.txt"]
    assert {p.parent for p in loaded} == {tmp_path}


def test_the_shipped_rankers_stay_the_default(monkeypatch):
    loaded: list[Path] = []
    monkeypatch.setattr(ltr, "_load", lambda path: loaded.append(path) or path)
    monkeypatch.setattr(ltr.HybridRetriever, "__init__", lambda self, *args, **kwargs: None)
    monkeypatch.setattr(ltr, "FeatureExtractor", lambda *args, **kwargs: None)
    monkeypatch.setattr(ltr, "issue_memory", lambda retriever: None)
    ltr.LTRRetriever(None, None)
    assert {p.parent for p in loaded} == {ltr.MODEL_DIR}
