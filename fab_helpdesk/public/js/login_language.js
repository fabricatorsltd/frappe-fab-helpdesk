// Language picker for the login and signup page. Guests have no user record to
// carry a language, so the choice is stored in the preferred_language cookie,
// which frappe reads before the Accept-Language header. The signup hook then
// copies the resolved language onto the new user.
//
// The list comes from the server: frappe rejects cookies pointing at disabled
// languages, so offering anything but the enabled ones would be a dead control.
(function () {
	if (window.location.pathname !== "/login") return;

	function getCookie(name) {
		var match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
		return match ? decodeURIComponent(match[1]) : "";
	}

	function render(languages) {
		if (!languages || languages.length < 2) return;
		var card = document.querySelector(".login-content.page-card");
		if (!card) return;

		var current = getCookie("preferred_language") || document.documentElement.lang || "en";

		var select = document.createElement("select");
		select.className = "form-control";
		select.setAttribute("aria-label", "Language");
		select.style.marginTop = "15px";
		languages.forEach(function (lang) {
			var option = document.createElement("option");
			option.value = lang.name;
			option.textContent = lang.language_name;
			if (lang.name === current) option.selected = true;
			select.appendChild(option);
		});

		select.addEventListener("change", function () {
			document.cookie =
				"preferred_language=" +
				encodeURIComponent(select.value) +
				"; path=/; max-age=31536000";
			var url = new URL(window.location.href);
			url.searchParams.set("_lang", select.value);
			window.location.replace(url.toString());
		});

		card.appendChild(select);
	}

	fetch("/api/method/fab_helpdesk.api.get_languages", {
		headers: { "X-Frappe-Site-Name": window.location.hostname },
	})
		.then(function (response) {
			return response.json();
		})
		.then(function (payload) {
			render(payload.message);
		})
		.catch(function () {
			// no list, no picker: never render options the server would reject
		});
})();

// Split the SSO buttons by host, both sides symmetric and driven by site_config
// so the module ships unchanged to customer instances:
//   - on the helpdesk customer host: hide the internal staff button(s), keeping
//     email/password + the customer SSO so customers without M365 can sign in;
//   - on any other host (the aziendale desk): hide the customer SSO button(s),
//     keeping email/password + the internal staff SSO.
// Only splits when helpdesk_host is set; otherwise the page stays as rendered.
(function () {
	if (window.location.pathname !== "/login") return;

	function hide(keys, fallback) {
		(keys || fallback).split(",").forEach(function (key) {
			key = key.trim();
			if (!key) return;
			document.querySelectorAll(".btn-login-option.btn-" + key).forEach(function (el) {
				el.style.display = "none";
			});
		});
	}

	fetch("/api/method/fab_helpdesk.api.get_login_config", {
		headers: { "X-Frappe-Site-Name": window.location.hostname },
	})
		.then(function (response) {
			return response.json();
		})
		.then(function (payload) {
			var cfg = (payload && payload.message) || {};
			// helpdesk_host must be a bare lowercase host (no scheme/port) to match
			// window.location.hostname; otherwise this host counts as the desk.
			if (!cfg.helpdesk_host) return;
			if (window.location.hostname === cfg.helpdesk_host) {
				hide(cfg.internal_login_keys, "office_365");
			} else {
				hide(cfg.customer_login_keys, "m365_customer");
			}
		})
		.catch(function () {
			// no config, no change: the login page stays as frappe rendered it
		});
})();
