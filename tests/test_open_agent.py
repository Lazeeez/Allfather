import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import open_agent  # noqa: E402


def parse(text):
    return json.loads(text) if text.startswith("{") else None


def write(root: Path) -> None:
    (root / "pkg").mkdir()
    (root / "pkg" / "config.py").write_text(
        "def load_config(path):\n    return parse(path)\n", encoding="utf-8"
    )
    (root / "secret.txt").write_text("outside the source set\n", encoding="utf-8")


def test_tools_stay_inside_the_checkout(tmp_path):
    write(tmp_path)
    assert open_agent.list_files(tmp_path, "pkg/*.py") == "pkg/config.py"
    assert open_agent.list_files(tmp_path, "../*") == ""
    assert open_agent.read_file(tmp_path, "../../etc/passwd", 1, 2).startswith("no such file")
    assert "pkg/config.py:1: def load_config(path):" in open_agent.grep(
        tmp_path, "load_config", None
    )
    assert open_agent.read_file(tmp_path, "pkg/config.py", 2, 2) == "2:     return parse(path)"


def test_agent_loop_runs_tools_then_returns_the_answer(tmp_path, monkeypatch):
    write(tmp_path)
    replies = iter(
        [
            {
                "model": "m",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                "choices": [{"message": {"content": "", "tool_calls": [
                    {"id": "1", "function": {"name": "grep", "arguments": json.dumps({"pattern": "load_config"})}}
                ]}}],
            },
            {
                "model": "m",
                "usage": {"prompt_tokens": 20, "completion_tokens": 7},
                "choices": [{"message": {"content": '{"functions": [{"file": "pkg/config.py", "name": "load_config"}]}'}}],
            },
        ]
    )  # fmt: skip
    seen = []

    def fake_chat(model, messages, tools):
        seen.append([m["role"] for m in messages])
        return next(replies)

    monkeypatch.setattr(open_agent, "chat", fake_chat)
    out = open_agent.run("find it", tmp_path, "m", True, parse)
    assert out["answer"] == {"functions": [{"file": "pkg/config.py", "name": "load_config"}]}
    assert out["tools"] == ["grep"] and out["turns"] == 2
    assert out["usage"]["prompt_tokens"] == 30
    assert seen[1] == ["user", "assistant", "tool"]


def test_single_call_sends_no_tools(tmp_path, monkeypatch):
    calls = []

    def fake_chat(model, messages, tools):
        calls.append(tools)
        return {"model": "m", "choices": [{"message": {"content": '{"functions": []}'}}]}

    monkeypatch.setattr(open_agent, "chat", fake_chat)
    out = open_agent.run("find it", tmp_path, "m", False, parse)
    assert calls == [None] and out["answer"] == {"functions": []}


def test_a_full_context_is_recorded_as_no_answer(tmp_path, monkeypatch):
    write(tmp_path)

    def full(model, messages, tools):
        raise open_agent.ContextFull("This model's maximum context length is 262144 tokens")

    monkeypatch.setattr(open_agent, "chat", full)
    out = open_agent.run("find the bug", tmp_path, "m", True, parse)
    assert out["answer"] is None and out["error"] is None
    assert out["no_answer"].startswith("context full at turn 1")


def test_running_out_of_turns_is_no_answer_not_an_error(tmp_path, monkeypatch):
    write(tmp_path)
    call = {"id": "c", "function": {"name": "list_files", "arguments": '{"pattern": "**/*.py"}'}}
    reply = {"choices": [{"message": {"content": "", "tool_calls": [call]}}], "usage": {}}
    monkeypatch.setattr(open_agent, "chat", lambda model, messages, tools: reply)
    out = open_agent.run("find the bug", tmp_path, "m", True, parse)
    assert (
        out["error"] is None and out["no_answer"] == f"no answer after {open_agent.MAX_TURNS} turns"
    )
