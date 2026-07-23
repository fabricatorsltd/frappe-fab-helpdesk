import frappe


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
