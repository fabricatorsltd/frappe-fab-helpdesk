import frappe
from frappe import _
from frappe.model.document import Document


class FABHelpdeskDomain(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		customer: DF.Link | None
		domain: DF.Data
	# end: auto-generated types

	def before_naming(self):
		# the record is named after the domain, so normalize before autoname runs
		self.domain = (self.domain or "").strip().lower().lstrip("@")

	def validate(self):
		self.before_naming()
		if not self.domain or "@" in self.domain or "." not in self.domain:
			frappe.throw(_("Enter a bare email domain such as example.com."))
