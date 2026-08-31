from email.utils import getaddresses

import frappe


def _parse_emails(raw):
	return [addr.lower() for _, addr in getaddresses([raw or ""]) if addr and "@" in addr]


def _internal_addresses():
	"""Our own mailboxes and every agent: we never keep ourselves in a ticket CC."""
	addrs = set()
	for a in frappe.get_all("Email Account", pluck="email_id"):
		if a:
			addrs.add(a.lower())
	for a in frappe.get_all("HD Agent", pluck="name"):
		if a and "@" in a:
			addrs.add(a.lower())
	return addrs


def capture_ticket_cc(doc, method=None):
	"""Persist external CC participants on the ticket so agent replies loop them in.

	Runs on Communication after_insert. Only inbound emails contribute, and our own
	mailboxes/agents plus the ticket's primary contact are filtered out.
	"""
	if doc.reference_doctype != "HD Ticket" or not doc.reference_name:
		return
	if doc.sent_or_received != "Received" or not doc.cc:
		return
	incoming = _parse_emails(doc.cc)
	if not incoming:
		return

	internal = _internal_addresses()
	raised_by = (
		frappe.db.get_value("HD Ticket", doc.reference_name, "raised_by") or ""
	).lower()
	existing = _parse_emails(frappe.db.get_value("HD Ticket", doc.reference_name, "fab_cc"))

	merged = list(existing)
	for addr in incoming:
		if addr in internal or addr == raised_by or addr in merged:
			continue
		merged.append(addr)

	if merged != existing:
		frappe.db.set_value(
			"HD Ticket",
			doc.reference_name,
			"fab_cc",
			", ".join(merged),
			update_modified=False,
		)


def merge_reply_cc(fab_cc, cc, recipients):
	"""Union of the ticket's stored CC and any CC the agent typed, minus the
	primary recipients. Returns a comma-joined string or None."""
	to_addrs = {addr.lower() for _, addr in getaddresses([recipients or ""]) if addr}
	out = []
	for raw in (fab_cc, cc):
		for addr in _parse_emails(raw):
			if addr not in to_addrs and addr not in out:
				out.append(addr)
	return ", ".join(out) or None
