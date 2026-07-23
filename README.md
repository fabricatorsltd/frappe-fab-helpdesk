# FAB Helpdesk

Customer onboarding and domain policies for Frappe Helpdesk.

## What it does

- Restricts self service signup (email or OAuth) to email domains listed in
  the FAB Helpdesk Domain allowlist. Users created by agents are not affected,
  so customers on public domains (gmail, yahoo, ...) can be registered by hand.
- Adds new contacts to the HD Customer mapped to their email domain, so portal
  users land in the right organization without an invite.

Rows without a customer allow signup without binding, which is meant for
internal domains.

## Language selection

The login and signup pages get a language picker (served by
`fab_helpdesk.api.get_languages`, so it only offers languages enabled on
the site). The choice is stored on the User at signup, and a language
picked on the login page is saved onto the User at login; sessions,
portal, and email content then follow `User.language` as usual. Users
created by agents keep whatever language the agent set until they pick
one themselves.

## Security note on OAuth providers

The gate and the binding trust the email asserted by the identity provider.
Only enable Social Login Keys whose provider verifies email ownership: on
Azure AD the `email` claim is user editable, so multi tenant apps must either
map the login email from the UPN or require the `xms_edov` (domain owner
verified) claim. An unverified claim would let anyone reach another
organization's tickets by asserting an email on its domain.

## Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/fabricatorsltd/frappe-fab-helpdesk.git --branch version-16
bench --site [site] install-app fab_helpdesk
```

`fab_helpdesk` requires `helpdesk` in the bench.
