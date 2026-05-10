class TenantAccessError(Exception):
    """Raised when a data-access operation would cross tenant boundaries."""

    def __init__(self, resource: str, resource_id: object, requested_tenant: str) -> None:
        self.resource = resource
        self.resource_id = resource_id
        self.requested_tenant = requested_tenant
        super().__init__(
            f"Tenant isolation violation: {resource} {resource_id!r} "
            f"does not belong to tenant {requested_tenant!r}"
        )
