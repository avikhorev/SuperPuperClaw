def build_heartbeat_tools(storage):
    def read_heartbeat() -> str:
        """Read the current heartbeat instructions — what the bot proactively checks on schedule."""
        return storage.read_heartbeat()

    def update_heartbeat(content: str) -> str:
        """Update the heartbeat instructions — what the bot should proactively check on schedule."""
        storage.write_heartbeat(content)
        return "Heartbeat instructions updated."

    read_heartbeat._needs_storage = False
    update_heartbeat._needs_storage = False
    return [read_heartbeat, update_heartbeat]
