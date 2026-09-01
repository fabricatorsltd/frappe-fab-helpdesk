from __future__ import annotations

import frappe

from helpdesk.utils import get_customers

# Staff see every article regardless of audience; everyone else is a reader.
PRIVILEGED_ROLES = {"Agent", "Agent Manager", "System Manager"}


def _is_staff(user: str) -> bool:
	if user == "Administrator":
		return True
	return bool(set(frappe.get_roles(user)) & PRIVILEGED_ROLES)


def _user_customers(user: str) -> tuple[str, ...]:
	if not user or user == "Guest":
		return ()
	return tuple(get_customers(user=user))


def article_permission_query(user: str | None = None) -> str:
	"""Row-level filter for HD Article list queries. Staff: no restriction. Others:
	only published articles that are Public or restricted to one of their customers."""
	user = user or frappe.session.user
	if _is_staff(user):
		return ""

	cond = (
		"`tabHD Article`.status = 'Published' and "
		"(ifnull(`tabHD Article`.fab_visibility, 'Public') = 'Public'"
	)
	customers = _user_customers(user)
	if customers:
		vals = ", ".join(frappe.db.escape(c) for c in customers)
		cond += (
			" or exists (select 1 from `tabFAB HD Article Customer` fac "
			f"where fac.parent = `tabHD Article`.name and fac.customer in ({vals}))"
		)
	cond += ")"
	return cond


def has_article_permission(doc, user: str | None = None, permission_type: str | None = None) -> bool:
	"""Per-document audience check, mirroring article_permission_query for the
	paths that load a single article (get_doc based reads)."""
	user = user or frappe.session.user
	if _is_staff(user):
		return True
	# Readers only ever read published articles.
	if permission_type not in (None, "read", "select"):
		return False
	if (doc.get("status") if hasattr(doc, "get") else getattr(doc, "status", None)) != "Published":
		return False
	visibility = (doc.get("fab_visibility") if hasattr(doc, "get") else getattr(doc, "fab_visibility", None)) or "Public"
	if visibility == "Public":
		return True
	rows = doc.get("fab_customers") if hasattr(doc, "get") else getattr(doc, "fab_customers", None)
	allowed = {r.customer for r in (rows or [])}
	return bool(set(_user_customers(user)) & allowed)


def is_article_visible(name: str, user: str | None = None) -> bool:
	"""Convenience wrapper used by the whitelisted KB endpoints that fetch a
	single article via get_doc (which does not run permission_query)."""
	user = user or frappe.session.user
	if _is_staff(user):
		return True
	doc = frappe.get_cached_doc("HD Article", name)
	return has_article_permission(doc, user, "read")
