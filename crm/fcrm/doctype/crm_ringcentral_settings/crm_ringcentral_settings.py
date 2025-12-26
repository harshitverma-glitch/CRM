# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CRMRingCentralSettings(Document):
	def before_save(self):
		"""Set redirect URI if not set"""
		if not self.redirect_uri:
			site_url = frappe.utils.get_url()
			self.redirect_uri = f"{site_url}/api/method/crm.integrations.ringcentral_oauth.ringcentral_callback"
	
	def on_update(self):
		"""Clear cache when settings are updated"""
		frappe.cache().delete_value("ringcentral_oauth_state")

