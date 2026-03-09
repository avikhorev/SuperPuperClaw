import logging
import os


def setup_logging(data_dir: str):
    os.makedirs(os.path.join(data_dir, "logs"), exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s — %(message)s")
    handlers = [logging.StreamHandler()]
    log_path = os.path.join(data_dir, "logs", "bot.log")
    try:
        handlers.append(logging.FileHandler(log_path))
        error_handler = logging.FileHandler(os.path.join(data_dir, "logs", "errors.log"))
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(fmt)
        handlers.append(error_handler)
    except OSError:
        pass
    for h in handlers:
        h.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in handlers:
        root.addHandler(h)
