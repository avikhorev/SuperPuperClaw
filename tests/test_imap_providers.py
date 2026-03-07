from bot.imap_providers import get_provider_settings, get_app_password_instructions

def test_gmail_detected():
    settings = get_provider_settings("john@gmail.com")
    assert settings is not None
    imap_host, imap_port, smtp_host, smtp_port = settings
    assert imap_host == "imap.gmail.com"
    assert imap_port == 993

def test_outlook_detected():
    settings = get_provider_settings("john@outlook.com")
    assert settings is not None
    assert settings[0] == "outlook.office365.com"

def test_unknown_provider_returns_none():
    assert get_provider_settings("john@unknown-corp-email.com") is None

def test_gmail_instructions_mention_app_password():
    instructions = get_app_password_instructions("john@gmail.com")
    assert "App Password" in instructions or "app password" in instructions.lower()

def test_unknown_provider_instructions_returned():
    instructions = get_app_password_instructions("john@unknown-corp.com")
    assert isinstance(instructions, str)
    assert len(instructions) > 10
