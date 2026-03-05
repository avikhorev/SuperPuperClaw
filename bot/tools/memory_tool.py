def update_memory(new_content: str, storage) -> str:
    """Update the persistent memory file with new information about the user. Pass the complete updated memory content."""
    storage.write_memory(new_content)
    return "Memory updated."
