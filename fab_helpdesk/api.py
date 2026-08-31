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


def _priority_level_options(priority_codes):
	levels = []
	for code in priority_codes:
		severity = frappe.db.get_value("HD Ticket Priority", code, "description") or code
		levels.append({"value": code, "label": f"{code} - {_(severity)}"})
	return levels


@frappe.whitelist()
def get_sla_policy(ticket_type, customer=None):
	"""Priority levels for the ticket form, plus the SLA policy when one applies.

	The priority picker is always offered (every ticket is triaged by priority).
	A contractual SLA only applies to SLA-bound ticket types (Incident); other
	types are handled best-effort during office hours, still honouring the chosen
	priority. Level labels are translated; the policy body is returned verbatim.
	"""
	from helpdesk.helpdesk.doctype.hd_service_level_agreement.utils import get_sla

	customer = _resolve_customer(customer)
	sla_bound = bool(frappe.db.get_value("HD Ticket Type", ticket_type, "fab_sla_bound"))

	probe = frappe.new_doc("HD Ticket")
	probe.subject = "_"
	probe.customer = customer
	probe.ticket_type = ticket_type
	probe.priority = frappe.db.get_single_value("HD Settings", "default_priority") or "P3"
	sla = get_sla(probe) if sla_bound else None

	if sla_bound and sla and not sla.default_sla:
		doc = frappe.get_doc("HD Service Level Agreement", sla.name)
		codes = [row.priority for row in sorted(doc.priorities, key=lambda r: r.idx)]
		return {
			"applies": True,
			"best_effort": False,
			"sla": doc.name,
			"policy_html": doc.get("fab_policy_html") or "",
			"levels": _priority_level_options(codes),
		}

	codes = frappe.get_all("HD Ticket Priority", order_by="name", pluck="name")
	return {"applies": False, "best_effort": True, "levels": _priority_level_options(codes)}


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
def get_login_config():
	"""Login-page customisation for a helpdesk customer portal host.

	On `helpdesk_host` the internal staff login buttons listed in
	`helpdesk_internal_login_keys` (comma separated Social Login Key names,
	default the internal Office 365 app) are hidden; the email/password form and
	the customer SSO stay so customers without M365 can still sign in. Both are
	per-instance site_config so the module ships unchanged to customer sites; an
	unset `helpdesk_host` leaves the login page untouched.
	"""
	return {
		"helpdesk_host": frappe.conf.get("helpdesk_host"),
		"internal_login_keys": frappe.conf.get("helpdesk_internal_login_keys") or "office_365",
		"customer_login_keys": frappe.conf.get("helpdesk_customer_login_keys") or "m365_customer",
	}


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
