from __future__ import annotations

import frappe


def after_install():
	clear_portal_default_customer_role()


def after_migrate():
	clear_portal_default_customer_role()


def clear_portal_default_customer_role():
	"""Stop new signups from defaulting to the helpdesk customer role.

	Core Helpdesk sets Portal Settings.default_role to "HD Customer", which
	frappe then grants to every OAuth/self service signup. In the fab model
	customers are bound to their HD Customer explicitly through the domain
	allowlist, so the portal role must not be handed out by default: internal
	staff and unmapped users should land with no role until granted one.
	"""
	if frappe.db.get_single_value("Portal Settings", "default_role") == "HD Customer":
		frappe.db.set_single_value("Portal Settings", "default_role", "")
