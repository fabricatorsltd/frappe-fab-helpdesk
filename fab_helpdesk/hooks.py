app_name = "fab_helpdesk"
app_title = "FAB Helpdesk"
app_publisher = "fabricators"
app_description = "Customer onboarding and domain policies for Frappe Helpdesk"
app_email = "support@fabricators.ltd"
app_license = "agpl-3.0"

required_apps = ["helpdesk"]

# add_to_apps_screen is deliberately not declared: this app has no UI of its
# own, so it must not claim a tile on the desk. Declaring it also made
# create_desktop_icons_from_installed_apps() read app_details["logo"] without a
# default, which raised KeyError and aborted desktop icon creation for the site.

doc_events = {
	"User": {
		"before_insert": "fab_helpdesk.onboarding.validate_signup_domain",
	},
	"Contact": {
		"after_insert": "fab_helpdesk.onboarding.bind_contact_to_customer",
		"on_update": "fab_helpdesk.onboarding.bind_contact_to_customer",
	},
	"FAB Helpdesk Domain": {
		"after_insert": "fab_helpdesk.onboarding.bind_domain_contacts",
		"on_update": "fab_helpdesk.onboarding.bind_domain_contacts",
	},
}
