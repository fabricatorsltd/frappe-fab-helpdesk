from __future__ import annotations

import frappe

# Urgent/High/Medium/Low -> P1..P4, English-canonical severity (the source language;
# it/fr come from the .po catalog). integer_value is preserved by the rename.
PRIORITY_RENAME = [
	("Urgent", "P1", "Critical"),
	("High", "P2", "High"),
	("Medium", "P3", "Medium"),
	("Low", "P4", "Low"),
]

# customer-facing categories: (name, sla_bound). Incident is the only SLA-bound one.
CUSTOMER_TICKET_TYPES = [("Incident", 1), ("Request", 0), ("Feature Request", 0)]


def after_install():
	clear_portal_default_customer_role()
	setup_sla_levels()
	ensure_ticket_dev_fields()


def after_migrate():
	clear_portal_default_customer_role()
	setup_sla_levels()
	ensure_ticket_dev_fields()


def ensure_ticket_dev_fields():
	"""Agent-side dev-tracking fields on the ticket: the kind of dev task and its
	id in the dev tracker. Inserted after a core field so it ships to any helpdesk
	instance, and left out of the customer template so it never shows on the portal."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"HD Ticket": [
				{
					"fieldname": "fab_dev_task_type",
					"fieldtype": "Select",
					"label": "Dev Task Type",
					"options": "\nBug\nFeature",
					"insert_after": "agent_group",
				},
				{
					"fieldname": "fab_dev_task_id",
					"fieldtype": "Data",
					"label": "Dev Task ID",
					"insert_after": "fab_dev_task_type",
				},
			]
		},
		ignore_validate=True,
	)


def setup_sla_levels():
	"""Idempotent: the SLA-policy custom fields, the P1-P4 priority scheme and the
	customer-selectable ticket categories the create-form SLA guidance relies on."""
	ensure_sla_custom_fields()
	rename_priorities_to_levels()
	ensure_customer_ticket_types()


def ensure_sla_custom_fields():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"HD Service Level Agreement": [
				{
					"fieldname": "fab_policy_section",
					"fieldtype": "Section Break",
					"label": "Customer-facing policy",
					"insert_after": "description",
				},
				{
					"fieldname": "fab_policy_html",
					"fieldtype": "Text Editor",
					"label": "SLA Policy (rich text, shown to the customer)",
					"insert_after": "fab_policy_section",
				},
			],
			"HD Ticket Type": [
				{
					"fieldname": "fab_customer_selectable",
					"fieldtype": "Check",
					"label": "Customer selectable",
					"insert_after": "disabled",
					"description": "Show this type as a category the customer can pick when opening a ticket.",
				},
				{
					"fieldname": "fab_sla_bound",
					"fieldtype": "Check",
					"label": "SLA-bound (incident)",
					"insert_after": "fab_customer_selectable",
					"description": "Incidents/problems: an SLA policy applies and its level guide is shown at creation.",
				},
			],
		},
		ignore_validate=True,
	)


def rename_priorities_to_levels():
	for old, new, label in PRIORITY_RENAME:
		if frappe.db.exists("HD Ticket Priority", old) and not frappe.db.exists(
			"HD Ticket Priority", new
		):
			frappe.rename_doc("HD Ticket Priority", old, new, force=True)
		if frappe.db.exists("HD Ticket Priority", new):
			frappe.db.set_value("HD Ticket Priority", new, "description", label)

	if frappe.db.exists("HD Ticket Priority", "P3") and not frappe.db.get_single_value(
		"HD Settings", "default_priority"
	):
		frappe.db.set_single_value("HD Settings", "default_priority", "P3")


def ensure_customer_ticket_types():
	for name, sla_bound in CUSTOMER_TICKET_TYPES:
		if not frappe.db.exists("HD Ticket Type", name):
			frappe.get_doc({"doctype": "HD Ticket Type", "name": name}).insert(
				ignore_permissions=True
			)
		frappe.db.set_value(
			"HD Ticket Type",
			name,
			{"fab_customer_selectable": 1, "fab_sla_bound": sla_bound},
		)


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
