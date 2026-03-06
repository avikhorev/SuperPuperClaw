def build_heartbeat_tools(storage):
    def update_heartbeat(content: str) -> str:
        """Update the heartbeat instructions — what the bot should proactively check daily."""
        storage.write_heartbeat(content)
        return "Heartbeat instructions updated."

    update_heartbeat._needs_storage = False
    return [update_heartbeat]
