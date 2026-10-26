from rent_management.onboarding import extend_invite_links
from rent_management.portal import ensure_tenant_role


def execute():
	ensure_tenant_role()
	extend_invite_links()  # tenant invites are opened hours later
