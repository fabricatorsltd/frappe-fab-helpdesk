import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from fab_helpdesk import onboarding


class TestGetEmailDomain(unittest.TestCase):
	def test_extracts_domain_lowercased(self):
		self.assertEqual(onboarding.get_email_domain("User@Acme.COM"), "acme.com")

	def test_handles_missing_or_invalid(self):
		self.assertIsNone(onboarding.get_email_domain(None))
		self.assertIsNone(onboarding.get_email_domain(""))
		self.assertIsNone(onboarding.get_email_domain("not-an-email"))


class TestValidateSignupDomain(unittest.TestCase):
	def make_user(self, email="user@acme.com", user_type="Website User"):
		return SimpleNamespace(email=email, user_type=user_type)

	def test_allows_listed_domain(self):
		with patch.object(onboarding, "frappe") as frappe:
			frappe.session = SimpleNamespace(user="Guest")
			frappe.db.exists.side_effect = [None, "acme.com"]
			onboarding.validate_signup_domain(self.make_user())
			frappe.throw.assert_not_called()

	def test_rejects_unlisted_domain(self):
		with (
			patch.object(onboarding, "frappe") as frappe,
			patch.object(onboarding, "_", side_effect=lambda text: text),
		):
			frappe.session = SimpleNamespace(user="Guest")
			frappe.db.exists.return_value = None
			onboarding.validate_signup_domain(self.make_user("who@gmail.com"))
			frappe.throw.assert_called_once()

	def test_allows_pending_invitation(self):
		with patch.object(onboarding, "frappe") as frappe:
			frappe.session = SimpleNamespace(user="Guest")
			frappe.db.exists.return_value = "some-invitation"
			onboarding.validate_signup_domain(self.make_user("who@gmail.com"))
			frappe.throw.assert_not_called()
			frappe.db.exists.assert_called_once_with(
				"User Invitation", {"email": "who@gmail.com", "status": "Pending"}
			)

	def test_skips_authenticated_sessions(self):
		with patch.object(onboarding, "frappe") as frappe:
			frappe.session = SimpleNamespace(user="agent@fabricators.ltd")
			onboarding.validate_signup_domain(self.make_user("who@gmail.com"))
			frappe.throw.assert_not_called()
			frappe.db.exists.assert_not_called()

	def test_skips_system_users(self):
		with patch.object(onboarding, "frappe") as frappe:
			frappe.session = SimpleNamespace(user="Guest")
			onboarding.validate_signup_domain(self.make_user(user_type="System User"))
			frappe.throw.assert_not_called()


class TestBindContactToCustomer(unittest.TestCase):
	def make_contact(self, email="user@acme.com", user="user@acme.com"):
		contact = MagicMock()
		contact.name = "User Contact"
		contact.email_id = email
		contact.email_ids = []
		contact.get.side_effect = lambda key: {"user": user}.get(key)
		return contact

	def test_adds_member_for_mapped_domain(self):
		with patch.object(onboarding, "frappe") as frappe:
			frappe.db.get_value.return_value = "Acme"
			customer = MagicMock()
			customer.add_contact.return_value = True
			frappe.get_doc.return_value = customer
			onboarding.bind_contact_to_customer(self.make_contact())
			customer.add_contact.assert_called_once_with("User Contact")
			customer.save.assert_called_once_with(ignore_permissions=True)

	def test_skips_contact_without_user(self):
		with patch.object(onboarding, "frappe") as frappe:
			onboarding.bind_contact_to_customer(self.make_contact(user=None))
			frappe.db.get_value.assert_not_called()

	def test_skips_unmapped_domain(self):
		with patch.object(onboarding, "frappe") as frappe:
			frappe.db.get_value.return_value = None
			onboarding.bind_contact_to_customer(self.make_contact("who@gmail.com"))
			frappe.get_doc.assert_not_called()

	def test_skips_existing_member(self):
		with patch.object(onboarding, "frappe") as frappe:
			frappe.db.get_value.return_value = "Acme"
			customer = MagicMock()
			customer.add_contact.return_value = False
			frappe.get_doc.return_value = customer
			onboarding.bind_contact_to_customer(self.make_contact())
			customer.save.assert_not_called()

	def test_skips_update_without_relevant_change(self):
		with patch.object(onboarding, "frappe") as frappe:
			contact = self.make_contact()
			contact.has_value_changed.return_value = False
			onboarding.bind_contact_to_customer(contact, "on_update")
			frappe.db.get_value.assert_not_called()

	def test_binds_on_update_when_user_changes(self):
		with patch.object(onboarding, "frappe") as frappe:
			frappe.db.get_value.return_value = "Acme"
			customer = MagicMock()
			customer.add_contact.return_value = True
			frappe.get_doc.return_value = customer
			contact = self.make_contact()
			contact.has_value_changed.side_effect = lambda field: field == "user"
			onboarding.bind_contact_to_customer(contact, "on_update")
			customer.save.assert_called_once()

	def test_prefers_primary_email_over_first(self):
		with patch.object(onboarding, "frappe") as frappe:
			frappe.db.get_value.return_value = "Acme"
			customer = MagicMock()
			customer.add_contact.return_value = True
			frappe.get_doc.return_value = customer
			contact = self.make_contact(email=None)
			contact.email_ids = [
				SimpleNamespace(email_id="other@gmail.com", is_primary=0),
				SimpleNamespace(email_id="user@acme.com", is_primary=1),
			]
			onboarding.bind_contact_to_customer(contact)
			frappe.db.get_value.assert_called_once_with(
				onboarding.DOMAIN_DOCTYPE, {"domain": "acme.com"}, "customer"
			)


class TestBindDomainContacts(unittest.TestCase):
	def make_domain(self, domain="acme.com", customer="Acme"):
		row = MagicMock()
		row.domain = domain
		row.customer = customer
		return row

	def test_binds_existing_contacts_with_user(self):
		with (
			patch.object(onboarding, "frappe") as frappe,
			patch.object(onboarding, "add_membership") as add_membership,
		):
			frappe.get_all.return_value = ["Contact A", "Contact B"]
			onboarding.bind_domain_contacts(self.make_domain())
			frappe.get_all.assert_called_once_with(
				"Contact",
				filters={"email_id": ["like", "%@acme.com"], "user": ["is", "set"]},
				pluck="name",
			)
			add_membership.assert_has_calls(
				[call("Acme", "Contact A"), call("Acme", "Contact B")]
			)

	def test_skips_rows_without_customer(self):
		with patch.object(onboarding, "frappe") as frappe:
			onboarding.bind_domain_contacts(self.make_domain(customer=None))
			frappe.get_all.assert_not_called()

	def test_skips_update_without_relevant_change(self):
		with patch.object(onboarding, "frappe") as frappe:
			row = self.make_domain()
			row.has_value_changed.return_value = False
			onboarding.bind_domain_contacts(row, "on_update")
			frappe.get_all.assert_not_called()


class TestAddMembership(unittest.TestCase):
	def test_retries_once_on_stale_save(self):
		class Stale(Exception):
			pass

		with patch.object(onboarding, "frappe") as frappe:
			frappe.TimestampMismatchError = Stale
			stale = MagicMock()
			stale.add_contact.return_value = True
			stale.save.side_effect = Stale
			fresh = MagicMock()
			fresh.add_contact.return_value = True
			frappe.get_doc.side_effect = [stale, fresh]
			onboarding.add_membership("Acme", "User Contact")
			fresh.save.assert_called_once_with(ignore_permissions=True)

	def test_raises_after_second_stale_save(self):
		class Stale(Exception):
			pass

		with patch.object(onboarding, "frappe") as frappe:
			frappe.TimestampMismatchError = Stale
			customer = MagicMock()
			customer.add_contact.return_value = True
			customer.save.side_effect = Stale
			frappe.get_doc.return_value = customer
			with self.assertRaises(Stale):
				onboarding.add_membership("Acme", "User Contact")


if __name__ == "__main__":
	unittest.main()
