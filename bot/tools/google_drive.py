from googleapiclient.discovery import build


def search_drive_files(query: str, max_results: int = 10, storage=None) -> str:
    """Search Google Drive files by name."""
    try:
        tokens = storage.load_oauth_tokens()
        if not tokens:
            return "Google not connected."
        from bot.oauth import OAuthManager
        from bot.config import Config
        config = Config()
        creds = OAuthManager(config.google_client_id, config.google_client_secret).get_credentials(tokens)
        service = build("drive", "v3", credentials=creds)
        files = service.files().list(
            q=f"name contains '{query}'",
            pageSize=max_results,
            fields="files(id, name, mimeType, webViewLink)"
        ).execute().get("files", [])
        if not files:
            return "No files found."
        return "\n".join(f"• {f['name']} — {f.get('webViewLink', '')}" for f in files)
    except Exception as e:
        return f"Drive unavailable: {e}"


search_drive_files._needs_storage = True
