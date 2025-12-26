"""
API endpoints for fetching and managing call recordings
"""

import frappe
import requests
from typing import Dict, Any


@frappe.whitelist()
def get_recording_audio(call_log_name: str) -> Dict[str, Any]:
	"""
	Fetch the actual audio file for a call recording.
	Downloads from RingCentral and stores in ERPNext if not already cached.
	
	Args:
		call_log_name: Name of the CRM Call Log document
		
	Returns:
		dict with file_url to the audio file in ERPNext
	"""
	try:
		# Get call log
		call_log = frappe.get_doc("CRM Call Log", call_log_name)
		
		if not call_log.recording_url:
			return {"success": False, "error": "No recording URL found"}
		
	# Check if we already have the file cached (check both public and private)
	existing_file = frappe.db.get_value(
		"File",
		{
			"attached_to_doctype": "CRM Call Log",
			"attached_to_name": call_log_name,
		},
		["name", "file_url"],
		as_dict=True
	)
		
		if existing_file:
			return {
				"success": True,
				"file_url": existing_file.file_url,
				"cached": True
			}
		
		# Download from RingCentral
		audio_data = download_ringcentral_recording(call_log)
		
		if not audio_data:
			return {
				"success": False,
				"error": "Failed to download recording from RingCentral"
			}
		
	# Save to ERPNext File Manager as PUBLIC file
	# Changed is_private to 0 so HTML5 audio player can access it
	file_doc = frappe.get_doc({
		"doctype": "File",
		"file_name": f"recording_{call_log_name}.mp3",
		"attached_to_doctype": "CRM Call Log",
		"attached_to_name": call_log_name,
		"is_private": 0,  # Changed from 1 to 0 - makes file publicly accessible
		"content": audio_data,
	})
	file_doc.save(ignore_permissions=True)
	frappe.db.commit()
		
		return {
			"success": True,
			"file_url": file_doc.file_url,
			"cached": False
		}
		
	except Exception as e:
		frappe.log_error(
			title=f"Call Recording Fetch Error: {call_log_name}",
			message=str(e)
		)
		return {
			"success": False,
			"error": str(e)
		}


def download_ringcentral_recording(call_log) -> bytes:
	"""
	Download recording audio from RingCentral API
	
	Args:
		call_log: CRM Call Log document
		
	Returns:
		bytes of audio file
	"""
	try:
		# Get RingCentral credentials from settings
		# For now, return None - user needs to set up API credentials first
		settings = frappe.get_single("CRM RingCentral Settings")
		
		if not settings or not settings.enabled:
			frappe.log_error(
				title="RingCentral Settings Missing",
				message="RingCentral API credentials not configured"
			)
			return None
		
		# TODO: Implement actual RingCentral API download
		# This requires OAuth2 authentication with RingCentral
		# For now, return None and users can set up later
		
		frappe.msgprint(
			"RingCentral API download not yet configured. "
			"Please set up API credentials in CRM RingCentral Settings."
		)
		
		return None
		
	except Exception as e:
		frappe.log_error(
			title="RingCentral Download Error",
			message=str(e)
		)
		return None


@frappe.whitelist()
def get_recording_proxy_url(call_log_name: str) -> Dict[str, Any]:
	"""
	Get a proxied URL for playing RingCentral recordings.
	This returns the original RingCentral URL for now.
	
	Args:
		call_log_name: Name of the CRM Call Log
		
	Returns:
		dict with recording_url
	"""
	try:
		recording_url = frappe.db.get_value(
			"CRM Call Log",
			call_log_name,
			"recording_url"
		)
		
		if not recording_url:
			return {"success": False, "error": "No recording URL"}
		
		# For voicemail messages, construct the direct API URL
		if "app.ringcentral.com/messages/" in recording_url:
			# Extract message ID from URL
			message_id = recording_url.split("/messages/")[-1]
			
			# TODO: Get account_id and extension_id from call log payload
			# For now, return the web app URL
			return {
				"success": True,
				"recording_url": recording_url,
				"type": "voicemail",
				"message": "RingCentral login required to play"
			}
		
		# For direct recording URLs
		return {
			"success": True,
			"recording_url": recording_url,
			"type": "recording"
		}
		
	except Exception as e:
		frappe.log_error(
			title=f"Recording Proxy URL Error: {call_log_name}",
			message=str(e)
		)
		return {"success": False, "error": str(e)}

