def update_profile(new_content: str, storage) -> str:
    """Update the user profile with stable facts: name, timezone, language, preferences. Pass the complete updated profile content."""
    storage.write_profile(new_content)
    return "Profile updated."

update_profile._needs_storage = True


def update_context(new_content: str, storage) -> str:
    """Update the working context with current projects, ongoing tasks, recent decisions. Pass the complete updated context content."""
    storage.write_context(new_content)
    return "Context updated."

update_context._needs_storage = True
