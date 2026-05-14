"""Load and expose settings from config/settings.toml."""

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_CONFIG_PATH = _ROOT / "config" / "settings.toml"


def load() -> dict:
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Config not found at {_CONFIG_PATH}. "
            "Copy config/settings.example.toml → config/settings.toml and fill in your credentials."
        )
    with open(_CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def data_dir() -> Path:
    d = _ROOT / "data"
    d.mkdir(exist_ok=True)
    return d


def templates_dir() -> Path:
    return _ROOT / "templates"
