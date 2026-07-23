import frappe
from frappe import _

DOMAIN_DOCTYPE = "FAB Helpdesk Domain"


def get_email_domain(email: str | None) -> str | None:
	email = (email or "").strip().lower()
	if "@" not in email:
		return None
	return email.rsplit("@", 1)[1]


def validate_signup_domain(doc, method=None):
	"""Reject self service signups from domains outside the allowlist.

	Runs on User.before_insert. Only guards users created from a Guest session,
	which covers both the signup form and first time OAuth logins. Users created
	by an agent or by installers run under an authenticated session and pass
	untouched, so customers on public domains can still be registered by hand.

	Invited users are exempted explicitly: frappe currently creates them as
	System Users, which would skip the gate anyway, but the invite flow also
	runs as Guest and this must keep working if that upstream detail changes.
	"""
	if doc.user_type != "Website User":
		return
	if getattr(frappe.session, "user", None) != "Guest":
		return
	if frappe.db.exists("User Invitation", {"email": doc.email, "status": "Pending"}):
		return

	domain = get_email_domain(doc.email)
	if domain and frappe.db.exists(DOMAIN_DOCTYPE, {"domain": domain}):
		return

	frappe.throw(
		_("Sign up is limited to approved organizations. Contact support to get access."),
		frappe.PermissionError,
	)


def bind_contact_to_customer(doc, method=None):
	"""Add a contact with a portal user to the HD Customer mapped to its domain.

	Runs on Contact.after_insert and on_update, which covers every path that
	creates portal users: signup, first OAuth login and manual creation, since
	frappe creates or relinks the contact in all three. Contacts without a user
	are CRM data and are left alone. Membership is skipped when the domain is
	not mapped or maps to a row without a customer (internal domains).
	"""
	if method == "on_update" and not (
		doc.has_value_changed("user") or doc.has_value_changed("email_id")
	):
		return
	if not doc.get("user"):
		return

	email = doc.email_id or next(
		(row.email_id for row in doc.email_ids or [] if row.is_primary),
		next((row.email_id for row in doc.email_ids or []), None),
	)
	domain = get_email_domain(email)
	if not domain:
		return

	customer_name = frappe.db.get_value(DOMAIN_DOCTYPE, {"domain": domain}, "customer")
	if not customer_name:
		return

	add_membership(customer_name, doc.name)


def bind_domain_contacts(doc, method=None):
	"""Bind the existing contacts of a domain when its allowlist row changes.

	Runs on FAB Helpdesk Domain after_insert and on_update, so allowlisting a
	domain after its people already signed up (or were created by agents) still
	gets them into the right customer.
	"""
	if not doc.customer:
		return
	if method == "on_update" and not (
		doc.has_value_changed("customer") or doc.has_value_changed("domain")
	):
		return

	contacts = frappe.get_all(
		"Contact",
		filters={"email_id": ["like", f"%@{doc.domain}"], "user": ["is", "set"]},
		pluck="name",
	)
	for contact_name in contacts:
		add_membership(doc.customer, contact_name)


def add_membership(customer_name: str, contact_name: str):
	"""Append a contact to an HD Customer, retrying once on concurrent edits.

	The binding often runs inside the enqueued create_contact job, so the
	customer can be saved by an agent between load and save. A stale save would
	roll back the whole job, taking the freshly inserted contact with it.
	"""
	for attempt in range(2):
		customer = frappe.get_doc("HD Customer", customer_name)
		if not customer.add_contact(contact_name):
			return
		try:
			customer.save(ignore_permissions=True)
			return
		except frappe.TimestampMismatchError:
			if attempt:
				raise
