"""
API endpoints for call transcription
Handles on-demand transcription of call recordings
"""

import frappe
from typing import Dict, Any


@frappe.whitelist()
def get_or_create_transcript(call_log_name: str) -> Dict[str, Any]:
	"""
	Get existing transcript or create new one on-demand
	
	This function:
	1. Checks if transcript already exists in call log
	2. If exists, returns immediately (cached)
	3. If not, ensures recording is downloaded
	4. Triggers transcription workflow
	5. Saves transcript to database
	6. Returns transcript text
	
	Args:
		call_log_name: Name of the CRM Call Log
		
	Returns:
		dict with success status, transcript text, and cached flag
	"""
	try:
		# Get call log
		call_log = frappe.get_doc("CRM Call Log", call_log_name)
		
		# Check if transcript already exists
		if call_log.transcript:
			return {
				"success": True,
				"transcript": call_log.transcript,
				"cached": True,
				"message": "Transcript loaded from cache"
			}
		
		# Check if recording URL exists
		if not call_log.recording_url:
			return {
				"success": False,
				"message": "No recording available for this call"
			}
		
		# Ensure recording file is downloaded
		from crm.integrations.ringcentral_client import fetch_and_save_recording
		
		# Check if recording file already exists
		existing_file = frappe.db.exists("File", {
			"attached_to_doctype": "CRM Call Log",
			"attached_to_name": call_log_name
		})
		
		if not existing_file:
			# Download recording first
			frappe.logger().info(f"Downloading recording for {call_log_name}")
			download_result = fetch_and_save_recording(call_log_name)
			
			if not download_result.get("success"):
				return {
					"success": False,
					"message": f"Failed to download recording: {download_result.get('message', 'Unknown error')}"
				}
		
		# Transcribe the recording using RingCentral
		frappe.logger().info(f"Transcribing recording for {call_log_name}")
		from crm.integrations.ringcentral_client import transcribe_recording
		
		# Use RingCentral native transcription
		transcription_result = transcribe_recording(call_log_name)
		
		if transcription_result.get("success"):
			return {
				"success": True,
				"transcript": transcription_result.get("transcript"),
				"cached": False,
				"message": "Transcript generated successfully"
			}
		else:
			return {
				"success": False,
				"message": transcription_result.get("message", "Transcription failed")
			}
			
	except Exception as e:
		frappe.log_error(
			title=f"Get Transcript Error: {call_log_name}",
			message=f"Error: {str(e)}\n{frappe.get_traceback()}"
		)
		return {
			"success": False,
			"message": f"Error: {str(e)}"
		}


@frappe.whitelist()
def refresh_transcript(call_log_name: str) -> Dict[str, Any]:
	"""
	Force refresh/regenerate transcript for a call log
	
	Args:
		call_log_name: Name of the CRM Call Log
		
	Returns:
		dict with success status and new transcript
	"""
	try:
		# Get call log
		call_log = frappe.get_doc("CRM Call Log", call_log_name)
		
		# Clear existing transcript
		call_log.db_set('transcript', None, update_modified=False)
		frappe.db.commit()
		
		# Generate new transcript
		return get_or_create_transcript(call_log_name)
		
	except Exception as e:
		frappe.log_error(
			title=f"Refresh Transcript Error: {call_log_name}",
			message=f"Error: {str(e)}\n{frappe.get_traceback()}"
		)
		return {
			"success": False,
			"message": f"Error: {str(e)}"
		}

