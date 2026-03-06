import os
import pytest
from bot.storage import UserStorage
from bot.tools.skills_tool import build_skills_tools


@pytest.fixture
def storage(tmp_path):
    return UserStorage(data_dir=str(tmp_path), telegram_id=12345)


@pytest.fixture
def tools(storage):
    return build_skills_tools(storage)


def test_save_and_read_skill(storage):
    storage.write_skill("weekly_report", "Generate a weekly summary of completed tasks.")
    content = storage.read_skill("weekly_report")
    assert content == "Generate a weekly summary of completed tasks."


def test_list_skills_empty(storage):
    assert storage.list_skills() == []


def test_list_skills_shows_names(storage):
    storage.write_skill("skill_a", "Content A")
    storage.write_skill("skill_b", "Content B")
    names = storage.list_skills()
    assert "skill_a" in names
    assert "skill_b" in names


def test_read_skill_missing(storage):
    result = storage.read_skill("nonexistent")
    assert result is None


def test_save_skill_tool(tools, storage):
    save_fn = next(t for t in tools if t.__name__ == "save_skill")
    result = save_fn("email_digest", "Summarize all unread emails.")
    assert "saved" in result.lower()
    assert storage.read_skill("email_digest") == "Summarize all unread emails."


def test_read_skill_tool(tools, storage):
    storage.write_skill("my_skill", "Do something useful.")
    read_fn = next(t for t in tools if t.__name__ == "read_skill")
    result = read_fn("my_skill")
    assert result == "Do something useful."


def test_read_skill_tool_missing(tools):
    read_fn = next(t for t in tools if t.__name__ == "read_skill")
    result = read_fn("doesnt_exist")
    assert "not found" in result.lower()


def test_list_skills_tool(tools, storage):
    storage.write_skill("alpha", "Alpha skill")
    storage.write_skill("beta", "Beta skill")
    list_fn = next(t for t in tools if t.__name__ == "list_skills")
    result = list_fn()
    assert "alpha" in result
    assert "beta" in result


def test_list_skills_tool_empty(tools):
    list_fn = next(t for t in tools if t.__name__ == "list_skills")
    result = list_fn()
    assert "No skills" in result


def test_overwrite_skill(storage):
    storage.write_skill("report", "version 1")
    storage.write_skill("report", "version 2")
    assert storage.read_skill("report") == "version 2"


def test_skill_names_without_extension(storage):
    storage.write_skill("my_skill", "content")
    names = storage.list_skills()
    assert "my_skill" in names
    assert "my_skill.md" not in names


def test_save_skill_tool_overwrites(tools, storage):
    save_fn = next(t for t in tools if t.__name__ == "save_skill")
    save_fn("report", "first version")
    save_fn("report", "second version")
    assert storage.read_skill("report") == "second version"


def test_list_skills_tool_sorted(tools, storage):
    storage.write_skill("zebra", "z")
    storage.write_skill("alpha", "a")
    list_fn = next(t for t in tools if t.__name__ == "list_skills")
    result = list_fn()
    assert result.index("alpha") < result.index("zebra")


def test_read_skill_tool_names_missing_skill(tools):
    read_fn = next(t for t in tools if t.__name__ == "read_skill")
    result = read_fn("no_such_skill")
    assert "no_such_skill" in result
