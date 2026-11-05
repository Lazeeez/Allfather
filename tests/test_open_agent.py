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
        out["error"] is None
        and out["no_answer"] == f"no answer after {open_agent.MAX_TURNS} turns and a final request"
    )


def test_tools_accept_numbers_in_any_form_and_never_crash(tmp_path):
    write(tmp_path)
    text = open_agent.call_tool(
        tmp_path, "read_file", '{"path": "pkg/config.py", "start_line": 1.0, "end_line": "2"}'
    )
    assert text.startswith("1: def load_config")
    assert "2:" in text
    assert open_agent.call_tool(
        tmp_path, "read_file", '{"path": "pkg/config.py", "start_line": "first"}'
    ).startswith("1:")
    assert open_agent.call_tool(tmp_path, "grep", '{"pattern": "load", "glob": 5}').startswith(
        ("the tool failed", "pkg", "no matches")
    )
    assert (
        open_agent.call_tool(tmp_path, "read_file", "[1, 2]") == "arguments must be a JSON object"
    )


def tool_reply(name: str, arguments: str) -> dict:
    call = {"id": "c", "function": {"name": name, "arguments": arguments}}
    return {"choices": [{"message": {"content": "", "tool_calls": [call]}}], "usage": {}}


def test_the_answer_tool_and_an_answer_handed_to_an_unknown_tool_both_count(tmp_path, monkeypatch):
    write(tmp_path)
    given = '{"functions": [{"file": "pkg/config.py", "name": "load_config"}]}'
    for name in ("answer", "JSON"):
        monkeypatch.setattr(
            open_agent, "chat", lambda model, messages, tools, n=name: tool_reply(n, given)
        )
        out = open_agent.run("find the bug", tmp_path, "m", True, parse)
        assert out["answer"] == {"functions": [{"file": "pkg/config.py", "name": "load_config"}]}
        assert out["turns"] == 1 and "no_answer" not in out
    monkeypatch.setattr(
        open_agent, "chat", lambda model, messages, tools: tool_reply("JSON", '{"x": 1}')
    )
    assert open_agent.run("find the bug", tmp_path, "m", True, parse)["answer"] is None


def test_a_final_request_collects_an_answer_after_the_last_turn(tmp_path, monkeypatch):
    write(tmp_path)
    final = {
        "choices": [
            {
                "message": {
                    "content": '{"functions": [{"file": "pkg/config.py", "name": "load_config"}]}'
                }
            }
        ],
        "usage": {},
    }

    def chat(model, messages, tools):
        return final if tools is None else tool_reply("list_files", '{"pattern": "**/*.py"}')

    monkeypatch.setattr(open_agent, "chat", chat)
    out = open_agent.run("find the bug", tmp_path, "m", True, parse)
    assert out["answer"]["functions"][0]["name"] == "load_config" and "no_answer" not in out


def test_tool_names_other_models_are_trained_on_map_to_the_read_only_tools(tmp_path):
    write(tmp_path)
    assert "load_config" in open_agent.call_tool(tmp_path, "search", '{"query": "load_config"}')
    assert "pkg/config.py" in open_agent.call_tool(tmp_path, "print_tree", "{}")
    assert open_agent.call_tool(tmp_path, "apply_patch", "{}") == "unknown tool apply_patch"


def test_an_answer_given_only_in_the_reasoning_field_is_read(tmp_path, monkeypatch):
    write(tmp_path)
    reply = {
        "choices": [
            {
                "message": {
                    "content": "",
                    "reasoning_content": '{"functions": [{"file": "pkg/config.py", "name": "load_config"}]}',
                }
            }
        ],
        "usage": {},
    }
    monkeypatch.setattr(open_agent, "chat", lambda model, messages, tools: reply)
    out = open_agent.run("find the bug", tmp_path, "m", False, parse)
    assert out["answer"]["functions"][0]["name"] == "load_config"
