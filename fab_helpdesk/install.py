from __future__ import annotations

import frappe

from fab_helpdesk.onboarding import backfill_customer_landing_app

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

# Status of a ticket merged into another one. Only merge_ticket sets it; the
# fab_system_only flag keeps it out of the agent and customer status pickers.
MERGED_STATUS = "Merged"


def after_install():
	clear_portal_default_customer_role()
	setup_sla_levels()
	ensure_ticket_dev_fields()
	ensure_cc_field()
	ensure_kb_article_fields()
	ensure_customer_ticket_visibility_field()
	ensure_merged_ticket_status()
	backfill_customer_landing_app()


def after_migrate():
	clear_portal_default_customer_role()
	setup_sla_levels()
	ensure_ticket_dev_fields()
	ensure_cc_field()
	ensure_kb_article_fields()
	ensure_customer_ticket_visibility_field()
	ensure_merged_ticket_status()
	backfill_customer_landing_app()


def ensure_merged_ticket_status():
	"""Merged tickets used to sit in Closed, indistinguishable from a real closure.
	Give them their own status, flagged system-only so no picker offers it."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"HD Ticket Status": [
				{
					"fieldname": "fab_system_only",
					"fieldtype": "Check",
					"label": "System only",
					"insert_after": "enabled",
					"description": "Set by the system, hidden from the status pickers.",
				}
			]
		},
		ignore_validate=True,
	)

	if not frappe.db.exists("HD Ticket Status", MERGED_STATUS):
		closed_order = frappe.db.get_value("HD Ticket Status", "Closed", "order") or 4
		frappe.get_doc(
			{
				"doctype": "HD Ticket Status",
				"label_agent": MERGED_STATUS,
				"label_customer": MERGED_STATUS,
				"category": "Resolved",
				"color": "Gray",
				"order": closed_order + 1,
				"enabled": 1,
			}
		).insert(ignore_permissions=True)

	frappe.db.set_value("HD Ticket Status", MERGED_STATUS, "fab_system_only", 1)
	backfill_merged_ticket_status()


def backfill_merged_ticket_status():
	"""Tickets merged before the status existed are still marked Closed. Written
	straight to the database: the merge already notified everyone, so no hook,
	activity entry or feedback mail should fire again."""
	names = frappe.get_all(
		"HD Ticket",
		filters={"is_merged": 1, "status": ["!=", MERGED_STATUS]},
		pluck="name",
	)
	for name in names:
		frappe.db.set_value(
			"HD Ticket",
			name,
			{"status": MERGED_STATUS, "status_category": "Resolved"},
			update_modified=False,
		)


def ensure_customer_ticket_visibility_field():
	"""How much of a customer's tickets its members see. Standard keeps today's
	behaviour (own tickets, managers see all); Company-wide lets every member see
	all the customer's tickets. Enforced in hd_ticket permission_query."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"HD Customer": [
				{
					"fieldname": "fab_ticket_visibility",
					"fieldtype": "Select",
					"label": "Ticket visibility",
					"options": "Standard\nCompany-wide",
					"default": "Standard",
					"insert_after": "domain",
					"description": "Standard: members see their own tickets, managers see all. Company-wide: every member sees all the customer's tickets.",
				}
			]
		},
		ignore_validate=True,
	)


def ensure_kb_article_fields():
	"""Audience and language on knowledge base articles. Restricted articles are
	visible only to the listed customers (see hd_article permission hooks); the
	language drives the customer portal's per-language KB filter."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"HD Article": [
				{
					"fieldname": "fab_audience_section",
					"fieldtype": "Section Break",
					"label": "Audience",
					"insert_after": "views",
				},
				{
					"fieldname": "fab_visibility",
					"fieldtype": "Select",
					"label": "Visibility",
					"options": "Public\nRestricted",
					"default": "Public",
					"insert_after": "fab_audience_section",
					"description": "Public: visible to every customer. Restricted: only the customers listed below.",
				},
				{
					"fieldname": "fab_customers",
					"fieldtype": "Table MultiSelect",
					"label": "Visible to customers",
					"options": "FAB HD Article Customer",
					"insert_after": "fab_visibility",
					"depends_on": "eval:doc.fab_visibility=='Restricted'",
				},
				{
					"fieldname": "fab_language",
					"fieldtype": "Link",
					"label": "Language",
					"options": "Language",
					"insert_after": "fab_customers",
					"description": "Language of this article. Drives the per-language filter in the customer portal.",
				},
			]
		},
		ignore_validate=True,
	)


def ensure_cc_field():
	"""CC participants on the ticket: an email loop and a visibility grant.
	Captured from inbound mail and managed by agents from the sidebar; a CC'd
	contact may view the ticket (see hd_ticket has_permission)."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"HD Ticket": [
				{
					"fieldname": "fab_cc",
					"fieldtype": "Small Text",
					"label": "CC",
					"insert_after": "raised_by",
					"no_copy": 1,
				}
			]
		},
		ignore_validate=True,
	)


DEV_FIELDS = ("fab_dev_task_type", "fab_dev_task_id")
# permlevel 1: staff (Agent) writes, the customer only reads
DEV_PERMLEVEL = 1
DEV_WRITE_ROLES = ("Agent", "Agent Manager", "System Manager")
DEV_READ_ROLES = ("HD Customer", "HD Customer Manager")


def ensure_ticket_dev_fields():
	"""Dev-tracking fields on the ticket: the kind of dev task and its id in the
	dev tracker. Staff fill them, the customer can only view them: they sit at
	permlevel 1 (staff write, customer read) and are shown read-only on the portal
	ticket via the customer template."""
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
					"permlevel": DEV_PERMLEVEL,
				},
				{
					"fieldname": "fab_dev_task_id",
					"fieldtype": "Data",
					"label": "Dev Task ID",
					"insert_after": "fab_dev_task_type",
					"permlevel": DEV_PERMLEVEL,
				},
			]
		},
		ignore_validate=True,
	)
	ensure_ticket_dev_permlevel_perms()
	ensure_ticket_dev_template_fields()


def ensure_ticket_dev_permlevel_perms():
	"""Grant the permlevel-1 permissions the dev fields rely on: staff read+write,
	customer read-only."""
	from frappe.permissions import add_permission, update_permission_property

	for role in DEV_WRITE_ROLES:
		add_permission("HD Ticket", role, DEV_PERMLEVEL)
		update_permission_property("HD Ticket", role, DEV_PERMLEVEL, "read", 1)
		update_permission_property("HD Ticket", role, DEV_PERMLEVEL, "write", 1)
	for role in DEV_READ_ROLES:
		add_permission("HD Ticket", role, DEV_PERMLEVEL)
		update_permission_property("HD Ticket", role, DEV_PERMLEVEL, "read", 1)
		update_permission_property("HD Ticket", role, DEV_PERMLEVEL, "write", 0)


def ensure_ticket_dev_template_fields():
	"""Show the dev fields on the customer portal ticket (read-only there) by
	adding them to the Default ticket template, visible to the customer."""
	if not frappe.db.exists("HD Ticket Template", "Default"):
		return
	template = frappe.get_doc("HD Ticket Template", "Default")
	existing = {row.fieldname for row in template.fields}
	changed = False
	for fieldname in DEV_FIELDS:
		if fieldname not in existing:
			template.append("fields", {"fieldname": fieldname, "hide_from_customer": 0})
			changed = True
	if changed:
		template.flags.ignore_permissions = True
		template.save()


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
