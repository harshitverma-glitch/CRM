"""
Automatic download of RingCentral recordings when call logs are created
"""

import frappe


def auto_download_recording(doc, method=None):
	"""
	Automatically download recording after call log is created
	
	This is called via hooks when a CRM Call Log is inserted
	
	Args:
		doc: CRM Call Log document
		method: Hook method (not used)
	"""
	try:
		# Check if settings are enabled
		settings = frappe.get_single("CRM RingCentral Settings")
		if not settings or not settings.enabled:
			frappe.logger().debug("RingCentral auto-download disabled in settings")
			return
		
		# Check if call log has a recording URL
		if not doc.recording_url:
			frappe.logger().debug(f"No recording URL for call log {doc.name}")
			return
		
		# Skip if URL is already a local file (starts with /)
		if doc.recording_url.startswith("/"):
			frappe.logger().debug(f"Call log {doc.name} already has local recording")
			return
		
		# Skip if URL doesn't look like a RingCentral URL
		if "ringcentral.com" not in doc.recording_url:
			frappe.logger().debug(f"Call log {doc.name} has non-RingCentral URL")
			return
		
		# Enqueue background job to download
		frappe.enqueue(
			"crm.api.ringcentral_recording_download.download_and_store_recording",
			call_log_name=doc.name,
			queue="default",
			timeout=300,
			is_async=True
		)
		
		frappe.logger().info(f"📥 Enqueued recording download for {doc.name}")
		
	except Exception as e:
		# Don't fail the call log creation if download fails
		frappe.log_error(
			title=f"RingCentral Auto-Download Error: {doc.name}",
			message=frappe.get_traceback()
		)

