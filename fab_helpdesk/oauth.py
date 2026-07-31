import json

import frappe
from frappe import _
from frappe.utils.oauth import login_via_oauth2_id_token

CUSTOMER_PROVIDER = "m365_customer"


def _decoder(b):
	return json.loads(bytes(b).decode("utf-8"))


@frappe.whitelist(allow_guest=True)
def login_via_m365_customer(code: str, state: str):
	"""OAuth callback for the multi-tenant Microsoft 365 customer login.

	Uses the id_token flow so the email comes from the signed token claims, the
	way the built-in Office 365 provider does. The generic custom-provider flow
	reads a userinfo endpoint where Microsoft returns userPrincipalName instead
	of email, which breaks user resolution. Keyed to the "m365_customer" Social
	Login Key, kept separate from the internal single-tenant Office 365 app.

	A customer from an organization outside the allowlist is stopped by the
	domain gate (a PermissionError on User creation); catch it here and show a
	clear message instead of the generic 403 page, since self service signup is
	off and the account has to be provisioned by us.
	"""
	try:
		login_via_oauth2_id_token(CUSTOMER_PROVIDER, code, state, decoder=_decoder)
	except frappe.PermissionError:
		frappe.local.response = frappe._dict()
		frappe.respond_as_web_page(
			_("Access not enabled"),
			_(
				"Your Microsoft account is not linked to an authorized organization. "
				"Please contact support to request access."
			),
			http_status_code=403,
			indicator_color="red",
			primary_action="/login",
			primary_label=_("Back to login"),
		)
