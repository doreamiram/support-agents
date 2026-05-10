from pathlib import Path

import yaml
from pydantic import ValidationError

from app.config.models import (
    AppConfig,
    ComponentsConfig,
    EscalationChainsConfig,
    KnowledgeIndexConfig,
    QuietHoursConfig,
    SLARulesConfig,
    TenantsConfig,
)

# Default config directory: <project_root>/config/
_DEFAULT_CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


class ConfigLoadError(Exception):
    """Raised when a config file is missing, unreadable, or fails validation."""


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        raise ConfigLoadError(f"Config file not found: {path}")
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, dict) else {}


def load_config(config_dir: Path = _DEFAULT_CONFIG_DIR) -> AppConfig:
    """Load and validate all YAML config files.

    Raises ConfigLoadError with a human-readable message on any failure so
    the application can fail fast at startup.
    """
    config_dir = Path(config_dir)

    files: dict[str, Path] = {
        "tenants":           config_dir / "tenants.yaml",
        "components":        config_dir / "components.yaml",
        "sla_rules":         config_dir / "sla_rules.yaml",
        "escalation_chains": config_dir / "escalation_chains.yaml",
        "quiet_hours":       config_dir / "quiet_hours.yaml",
        "knowledge_index":   config_dir / "knowledge" / "index.yaml",
    }

    try:
        raw = {key: _read_yaml(path) for key, path in files.items()}
    except ConfigLoadError:
        raise

    try:
        return AppConfig(
            tenants=TenantsConfig.model_validate(raw["tenants"]),
            components=ComponentsConfig.model_validate(raw["components"]),
            sla_rules=SLARulesConfig.model_validate(raw["sla_rules"]),
            escalation_chains=EscalationChainsConfig.model_validate(
                raw["escalation_chains"]
            ),
            quiet_hours=QuietHoursConfig.model_validate(raw["quiet_hours"]),
            knowledge_index=KnowledgeIndexConfig.model_validate(
                raw["knowledge_index"]
            ),
        )
    except ValidationError as exc:
        raise ConfigLoadError(
            f"Config validation failed — fix the errors below and restart:\n\n{exc}"
        ) from exc
