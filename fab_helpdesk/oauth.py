import json

import frappe
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
	"""
	login_via_oauth2_id_token(CUSTOMER_PROVIDER, code, state, decoder=_decoder)
