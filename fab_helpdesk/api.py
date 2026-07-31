import frappe
from frappe import _


def _resolve_customer(customer=None):
	from helpdesk.utils import get_customers, is_agent

	customers = list(get_customers())
	if customer:
		if customer not in customers and not is_agent():
			frappe.throw(_("Not permitted"), frappe.PermissionError)
		return customer
	return customers[0] if len(customers) == 1 else None


@frappe.whitelist()
def get_ticket_options(customer=None):
	"""Customer-facing ticket categories for the create form.

	Only types flagged customer-selectable are offered; labels go through the
	translation system so the picker follows the user's portal language.
	"""
	customer = _resolve_customer(customer)
	types = frappe.get_all(
		"HD Ticket Type",
		filters={"disabled": 0, "fab_customer_selectable": 1},
		fields=["name", "fab_sla_bound"],
		order_by="fab_sla_bound desc, name",
	)
	return {
		"customer": customer,
		"types": [
			{"value": t.name, "label": _(t.name), "sla_bound": bool(t.fab_sla_bound)}
			for t in types
		],
	}


@frappe.whitelist()
def get_sla_policy(ticket_type, customer=None):
	"""SLA policy (customer-authored rich text + level dropdown) that applies to a
	ticket of this type for this customer. Level labels are translated; the policy
	body is the contract text and is returned verbatim."""
	from helpdesk.helpdesk.doctype.hd_service_level_agreement.utils import get_sla

	customer = _resolve_customer(customer)
	probe = frappe.new_doc("HD Ticket")
	probe.subject = "_"
	probe.customer = customer
	probe.ticket_type = ticket_type
	probe.priority = frappe.db.get_single_value("HD Settings", "default_priority") or "P3"

	sla = get_sla(probe)
	if not sla or sla.default_sla:
		return {"applies": False}

	doc = frappe.get_doc("HD Service Level Agreement", sla.name)
	levels = []
	for row in sorted(doc.priorities, key=lambda r: r.idx):
		severity = frappe.db.get_value("HD Ticket Priority", row.priority, "description") or row.priority
		levels.append({"value": row.priority, "label": f"{row.priority} - {_(severity)}"})
	return {
		"applies": True,
		"sla": doc.name,
		"policy_html": doc.get("fab_policy_html") or "",
		"levels": levels,
	}


@frappe.whitelist()
def get_customer_sla_policies(customer=None):
	"""Every distinct SLA policy that applies to the customer's SLA-bound
	categories, for the read-only portal consultation page."""
	customer = _resolve_customer(customer)
	types = frappe.get_all(
		"HD Ticket Type",
		filters={"disabled": 0, "fab_customer_selectable": 1, "fab_sla_bound": 1},
		pluck="name",
	)
	policies = {}
	for ticket_type in types:
		result = get_sla_policy(ticket_type, customer=customer)
		if result.get("applies") and result["sla"] not in policies:
			policies[result["sla"]] = result
	return {"customer": customer, "policies": list(policies.values())}


@frappe.whitelist(allow_guest=True)
def get_languages():
	"""Enabled languages for the login page picker.

	Guests cannot read the Language doctype, and the picker must only offer
	what frappe will actually accept: get_language() rejects cookies pointing
	at disabled languages.
	"""
	return frappe.get_all(
		"Language",
		filters={"enabled": 1},
		fields=["name", "language_name"],
		order_by="language_name",
	)
