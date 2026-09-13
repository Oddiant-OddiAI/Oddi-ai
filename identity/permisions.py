from config.permissions import ROLE_PERMISSIONS


def has_permission(identity, permission: str) -> bool:
    permissions = ROLE_PERMISSIONS.get(identity.role, {})
    return permissions.get(permission, False)