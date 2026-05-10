from app.config.models import AppConfig
from app.config.models import Contact as ConfigContact
from app.config.models import Tenant as ConfigTenant


class ContactNotVerifiedError(Exception):
    """Raised when an inbound contact cannot be matched to a registered tenant contact."""

    def __init__(self, channel: str, external_id: str) -> None:
        self.channel = channel
        self.external_id = external_id
        super().__init__(
            f"Contact not verified: channel={channel!r}, external_id={external_id!r}"
        )


class IdentityResolver:
    """
    Resolve (channel, external_id) → (Tenant, Contact) using tenants.yaml config.

    Config is the sole source of truth for identity in this prototype.
    Contacts must be pre-registered in config/tenants.yaml to be accepted.
    """

    def resolve(
        self,
        *,
        channel: str,
        external_id: str,
        config: AppConfig,
    ) -> tuple[ConfigTenant, ConfigContact]:
        for tenant in config.tenants.tenants:
            for contact in tenant.contacts:
                if contact.channel == channel and contact.external_id == external_id:
                    return tenant, contact

        raise ContactNotVerifiedError(channel, external_id)
