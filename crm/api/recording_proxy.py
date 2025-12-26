"""
API endpoint to serve private recording files with proper authentication and content-type
"""

import frappe
from frappe import _
from typing import Optional
import mimetypes


@frappe.whitelist()
def get_recording_file(call_log_name: str):
	"""
	Serve the recording file for a call log with proper authentication.
	This endpoint returns the actual file content with correct MIME type.
	
	Args:
		call_log_name: Name of the CRM Call Log
		
	Returns:
		File content with proper headers
	"""
	try:
		# Get the call log to verify access
		call_log = frappe.get_doc("CRM Call Log", call_log_name)
		
		# Find attached file
		file_doc = frappe.db.get_value(
			"File",
			{
				"attached_to_doctype": "CRM Call Log",
				"attached_to_name": call_log_name,
			},
			["name", "file_url", "file_name", "content_hash"],
			as_dict=True
		)
		
		if not file_doc:
			frappe.throw(_("No recording file found for this call log"))
		
		# Get the actual file content
		file_path = frappe.get_doc("File", file_doc.name).get_full_path()
		
		# Read file content
		with open(file_path, 'rb') as f:
			file_content = f.read()
		
		# Determine MIME type
		mime_type = mimetypes.guess_type(file_doc.file_name)[0]
		if not mime_type:
			# Default to common audio formats
			if file_doc.file_name.endswith('.mp3'):
				mime_type = 'audio/mpeg'
			elif file_doc.file_name.endswith('.wav'):
				mime_type = 'audio/wav'
			elif file_doc.file_name.endswith('.m4a'):
				mime_type = 'audio/mp4'
			else:
				mime_type = 'audio/mpeg'  # Default fallback
		
		# Set response headers
		frappe.response['type'] = 'download'
		frappe.response['filecontent'] = file_content
		frappe.response['filename'] = file_doc.file_name
		frappe.response['content_type'] = mime_type
		
		# Add headers to allow streaming
		frappe.local.response.headers['Accept-Ranges'] = 'bytes'
		frappe.local.response.headers['Content-Length'] = str(len(file_content))
		
	except frappe.DoesNotExistError:
		frappe.throw(_("Call Log not found"))
	except FileNotFoundError:
		frappe.throw(_("Recording file not found on disk"))
	except Exception as e:
		frappe.log_error(
			title=f"Recording Proxy Error: {call_log_name}",
			message=frappe.get_traceback()
		)
		frappe.throw(_("Error loading recording: {0}").format(str(e)))


@frappe.whitelist()
def get_recording_url(call_log_name: str) -> dict:
	"""
	Get the authenticated URL for a recording file.
	Returns a URL that can be used by the audio player.
	
	Args:
		call_log_name: Name of the CRM Call Log
		
	Returns:
		dict with recording_url
	"""
	try:
		# Verify call log exists
		if not frappe.db.exists("CRM Call Log", call_log_name):
			return {"success": False, "message": "Call log not found"}
		
		# Check if file exists
		file_doc = frappe.db.get_value(
			"File",
			{
				"attached_to_doctype": "CRM Call Log",
				"attached_to_name": call_log_name,
			},
			["name", "file_url", "is_private"],
			as_dict=True
		)
		
		if not file_doc:
			return {"success": False, "message": "No recording file found"}
		
		# For private files, use the API endpoint that handles authentication
		if file_doc.is_private:
			# Use the proxy endpoint that serves with auth
			recording_url = f"/api/method/crm.api.recording_proxy.get_recording_file?call_log_name={call_log_name}"
		else:
			# Public files can be accessed directly
			recording_url = file_doc.file_url
		
		return {
			"success": True,
			"recording_url": recording_url,
			"is_private": file_doc.is_private
		}
		
	except Exception as e:
		frappe.log_error(
			title=f"Get Recording URL Error: {call_log_name}",
			message=frappe.get_traceback()
		)
		return {"success": False, "message": str(e)}

