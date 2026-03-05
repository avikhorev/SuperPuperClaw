"""IMAP/SMTP server auto-detection and provider-specific user instructions."""

# Well-known provider settings: domain -> (imap_host, imap_port, smtp_host, smtp_port)
KNOWN_PROVIDERS: dict[str, tuple[str, int, str, int]] = {
    "gmail.com":        ("imap.gmail.com",        993, "smtp.gmail.com",        587),
    "googlemail.com":   ("imap.gmail.com",        993, "smtp.gmail.com",        587),
    "outlook.com":      ("outlook.office365.com", 993, "smtp.office365.com",    587),
    "hotmail.com":      ("outlook.office365.com", 993, "smtp.office365.com",    587),
    "live.com":         ("outlook.office365.com", 993, "smtp.office365.com",    587),
    "msn.com":          ("outlook.office365.com", 993, "smtp.office365.com",    587),
    "yahoo.com":        ("imap.mail.yahoo.com",   993, "smtp.mail.yahoo.com",   587),
    "ymail.com":        ("imap.mail.yahoo.com",   993, "smtp.mail.yahoo.com",   587),
    "icloud.com":       ("imap.mail.me.com",      993, "smtp.mail.me.com",      587),
    "me.com":           ("imap.mail.me.com",      993, "smtp.mail.me.com",      587),
    "mac.com":          ("imap.mail.me.com",      993, "smtp.mail.me.com",      587),
    "fastmail.com":     ("imap.fastmail.com",     993, "smtp.fastmail.com",     587),
    "fastmail.fm":      ("imap.fastmail.com",     993, "smtp.fastmail.com",     587),
    "proton.me":        ("127.0.0.1",             1143, "127.0.0.1",            1025),  # bridge
    "protonmail.com":   ("127.0.0.1",             1143, "127.0.0.1",            1025),
}

# Provider-specific instructions for obtaining an app password
APP_PASSWORD_INSTRUCTIONS: dict[str, str] = {
    "gmail.com": (
        "For Gmail, use an *App Password* (not your regular password):\n"
        "1. Go to myaccount.google.com/apppasswords\n"
        "2. Sign in if prompted\n"
        "3. Select *Mail* and your device, then click *Generate*\n"
        "4. Copy the 16-character password and paste it here\n\n"
        "_Note: You must have 2-Step Verification enabled on your Google account._"
    ),
    "googlemail.com": None,  # same as gmail.com, handled below
    "outlook.com": (
        "For Outlook/Hotmail, use your regular Microsoft password.\n"
        "If you have 2-factor authentication enabled, create an App Password:\n"
        "1. Go to account.microsoft.com/security\n"
        "2. Click *Advanced security options*\n"
        "3. Under *App passwords*, click *Create a new app password*\n"
        "4. Copy the password and paste it here"
    ),
    "hotmail.com": None,
    "live.com": None,
    "yahoo.com": (
        "For Yahoo Mail, use an *App Password*:\n"
        "1. Go to login.yahoo.com → Account Security\n"
        "2. Turn on *2-Step Verification* if not already on\n"
        "3. Scroll to *App passwords* → *Generate app password*\n"
        "4. Select *Other app*, name it anything, click *Generate*\n"
        "5. Copy the password and paste it here"
    ),
    "ymail.com": None,
    "icloud.com": (
        "For iCloud Mail, use an *App-Specific Password*:\n"
        "1. Go to appleid.apple.com\n"
        "2. Sign in → *Sign-In and Security* → *App-Specific Passwords*\n"
        "3. Click *+* to generate a new password\n"
        "4. Copy it and paste it here"
    ),
    "me.com": None,
    "mac.com": None,
    "fastmail.com": (
        "For Fastmail, use an *App Password*:\n"
        "1. Go to app.fastmail.com → Settings → Privacy & Security\n"
        "2. Under *Integrations*, click *Add* next to App Passwords\n"
        "3. Give it a name and select *Mail* access\n"
        "4. Copy the password and paste it here"
    ),
    "fastmail.fm": None,
}


def get_provider_settings(email: str) -> tuple[str, int, str, int] | None:
    """Return (imap_host, imap_port, smtp_host, smtp_port) for a known provider, or None."""
    domain = email.split("@")[-1].lower()
    return KNOWN_PROVIDERS.get(domain)


def get_app_password_instructions(email: str) -> str:
    """Return provider-specific instructions for obtaining an app password."""
    domain = email.split("@")[-1].lower()
    instructions = APP_PASSWORD_INSTRUCTIONS.get(domain)
    # Resolve aliases (None means use another key)
    if instructions is None:
        # Try common aliases
        for canonical in ("gmail.com", "outlook.com", "yahoo.com", "icloud.com", "fastmail.com"):
            if domain in APP_PASSWORD_INSTRUCTIONS and KNOWN_PROVIDERS.get(domain) == KNOWN_PROVIDERS.get(canonical):
                instructions = APP_PASSWORD_INSTRUCTIONS.get(canonical)
                break
    if not instructions:
        instructions = (
            "Enter the password for your email account.\n"
            "If your provider supports app passwords (recommended), use that instead of your main password.\n"
            "Check your provider's settings for instructions."
        )
    return instructions
