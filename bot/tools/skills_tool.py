def build_skills_tools(storage):
    def list_skills() -> str:
        """List all available skills by name."""
        names = storage.list_skills()
        if not names:
            return "No skills saved yet."
        return "Available skills:\n" + "\n".join(f"- {n}" for n in sorted(names))

    list_skills._needs_storage = False

    def read_skill(name: str) -> str:
        """Read the instructions/content of a saved skill by name."""
        content = storage.read_skill(name)
        if content is None:
            return f"Skill '{name}' not found. Use list_skills to see available skills."
        return content

    read_skill._needs_storage = False

    def save_skill(name: str, content: str) -> str:
        """Save or update a skill with instructions. Provide the skill name and its full content."""
        storage.write_skill(name, content)
        return f"Skill '{name}' saved."

    save_skill._needs_storage = False

    return [list_skills, read_skill, save_skill]
