"""
RingCentral Recording Download API
Downloads voicemail recordings and stores them in ERPNext
"""

import frappe
import requests
from typing import Dict, Any, Optional


@frappe.whitelist()
def download_and_store_recording(call_log_name: str) -> Dict[str, Any]:
	"""
	Download recording from RingCentral API and store in ERPNext.
	
	This function:
	1. Gets the message_id from the call log
	2. Uses RingCentral API to download the audio
	3. Stores it as a File in ERPNext
	4. Updates the call log with the local file URL
	
	Args:
		call_log_name: Name of the CRM Call Log
		
	Returns:
		dict with success status and file_url or error
	"""
	try:
		# Get call log
		call_log = frappe.get_doc("CRM Call Log", call_log_name)
		
		if not call_log.recording_url:
			return {"success": False, "error": "No recording URL found"}
		
		# Check if already downloaded
		existing_file = frappe.db.get_value(
			"File",
			{
				"attached_to_doctype": "CRM Call Log",
				"attached_to_name": call_log_name,
				"file_name": ["like", "recording_%"]
			},
			["name", "file_url"],
			as_dict=True
		)
		
		if existing_file:
			return {
				"success": True,
				"file_url": existing_file.file_url,
				"message": "Recording already downloaded",
				"cached": True
			}
		
		# Extract message_id from recording_url
		message_id = extract_message_id(call_log.recording_url)
		if not message_id:
			return {
				"success": False,
				"error": "Could not extract message ID from recording URL"
			}
		
		# Get RingCentral API credentials
		settings = frappe.get_single("CRM RingCentral Settings")
		if not settings or not settings.enabled:
			return {
				"success": False,
				"error": "RingCentral API not configured. Please set up CRM RingCentral Settings."
			}
		
		# Download from RingCentral API
		audio_data = download_from_ringcentral(message_id, settings, call_log)
		
		if not audio_data:
			return {
				"success": False,
				"error": "Failed to download recording from RingCentral API"
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
		
		# Update call log with local file URL
		frappe.db.set_value(
			"CRM Call Log",
			call_log_name,
			"recording_url",
			file_doc.file_url
		)
		frappe.db.commit()
		
		return {
			"success": True,
			"file_url": file_doc.file_url,
			"message": "Recording downloaded successfully",
			"cached": False
		}
		
	except Exception as e:
		frappe.log_error(
			title=f"Recording Download Error: {call_log_name}",
			message=frappe.get_traceback()
		)
		return {
			"success": False,
			"error": str(e)
		}


def extract_message_id(recording_url: str) -> Optional[str]:
	"""Extract message ID from RingCentral URL"""
	if not recording_url:
		return None
	
	# Format: https://app.ringcentral.com/messages/3162057434048
	if "app.ringcentral.com/messages/" in recording_url:
		parts = recording_url.split("/messages/")
		if len(parts) == 2:
			return parts[1].strip()
	
	return None


def download_from_ringcentral(
	message_id: str,
	settings: Any,
	call_log: Any
) -> Optional[bytes]:
	"""
	Download voicemail recording from RingCentral API
	
	Args:
		message_id: RingCentral message ID
		settings: CRM RingCentral Settings singleton
		call_log: CRM Call Log document
		
	Returns:
		bytes of audio file, or None if failed
	"""
	try:
		# Step 1: Authenticate with RingCentral
		access_token = get_ringcentral_token(settings)
		if not access_token:
			frappe.log_error("Failed to get RingCentral access token")
			return None
		
		# Step 2: Get account_id and extension_id
		# These should be stored in the call log or settings
		account_id = settings.account_id if hasattr(settings, 'account_id') else "~"
		extension_id = settings.extension_id if hasattr(settings, 'extension_id') else "~"
		
		# Step 3: Construct API URL for message content
		# Format: /restapi/v1.0/account/{accountId}/extension/{extensionId}/message-store/{messageId}/content/{attachmentId}
		api_url = f"https://platform.ringcentral.com/restapi/v1.0/account/{account_id}/extension/{extension_id}/message-store/{message_id}/content/{message_id}"
		
		# Step 4: Download the audio file
		headers = {
			"Authorization": f"Bearer {access_token}"
		}
		
		response = requests.get(api_url, headers=headers, timeout=30)
		response.raise_for_status()
		
		frappe.logger().info(f"Successfully downloaded recording for message {message_id}")
		return response.content
		
	except requests.exceptions.RequestException as e:
		frappe.log_error(
			title=f"RingCentral API Download Error: {message_id}",
			message=f"API Error: {str(e)}\nURL: {api_url if 'api_url' in locals() else 'N/A'}"
		)
		return None
	except Exception as e:
		frappe.log_error(
			title=f"Recording Download Error: {message_id}",
			message=frappe.get_traceback()
		)
		return None


def get_ringcentral_token(settings: Any) -> Optional[str]:
	"""
	Get RingCentral OAuth access token
	
	Now uses OAuth Authorization Code flow (modern, secure method)
	Falls back to legacy Password authentication if OAuth tokens not available
	
	Args:
		settings: CRM RingCentral Settings
		
	Returns:
		access_token string, or None if failed
	"""
	try:
		# Try OAuth first (modern method)
		from crm.api.ringcentral_auth import get_valid_access_token
		
		try:
			access_token = get_valid_access_token()
			if access_token:
				frappe.logger().info("✅ Using OAuth access token")
				return access_token
		except Exception as e:
			frappe.logger().info(f"OAuth not configured, trying legacy Password Flow: {str(e)}")
		
		# Fallback to Password Flow (legacy - deprecated by RingCentral)
		# This only works if your app was created before RingCentral deprecated Password Flow
		frappe.logger().warning("⚠️  Using legacy Password Flow - consider migrating to OAuth")
		
		# Validate required fields
		if not settings.client_id:
			frappe.log_error("RingCentral: Client ID not configured")
			return None
		
		# Get client secret
		from frappe.utils.password import get_decrypted_password
		client_secret = get_decrypted_password(
			"CRM RingCentral Settings",
			"CRM RingCentral Settings",
			"client_secret"
		)
		
		if not client_secret:
			frappe.log_error("RingCentral: Client Secret not configured")
			return None
		
		# Check for Password authentication fields
		if not settings.username or not settings.extension:
			frappe.log_error("RingCentral: Username and Extension required for Password authentication")
			return None
		
		# Get password
		password = get_decrypted_password(
			"CRM RingCentral Settings",
			"CRM RingCentral Settings",
			"password"
		)
		
		if not password:
			frappe.log_error("RingCentral: Password not configured")
			return None
		
		# Authenticate with RingCentral using Password Flow
		token_url = "https://platform.ringcentral.com/restapi/oauth/token"
		
		import base64
		auth_string = f"{settings.client_id}:{client_secret}"
		auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
		
		headers = {
			"Authorization": f"Basic {auth_b64}",
			"Content-Type": "application/x-www-form-urlencoded"
		}
		
		data = {
			"grant_type": "password",
			"username": settings.username,
			"password": password,
			"extension": settings.extension
		}
		
		frappe.logger().info(f"Authenticating with RingCentral: {settings.username}")
		
		response = requests.post(
			token_url,
			headers=headers,
			data=data,
			timeout=10
		)
		response.raise_for_status()
		
		token_data = response.json()
		access_token = token_data.get("access_token")
		
		frappe.logger().info("✅ RingCentral authentication successful")
		return access_token
		
	except requests.exceptions.HTTPError as e:
		frappe.log_error(
			title="RingCentral OAuth HTTP Error",
			message=f"Status: {e.response.status_code}\nResponse: {e.response.text}\n\n{frappe.get_traceback()}"
		)
		return None
	except Exception as e:
		frappe.log_error(
			title="RingCentral OAuth Error",
			message=frappe.get_traceback()
		)
		return None


@frappe.whitelist()
def test_ringcentral_connection() -> Dict[str, Any]:
	"""
	Test RingCentral API connection and authentication
	
	Returns:
		dict with success status and message
	"""
	try:
		settings = frappe.get_single("CRM RingCentral Settings")
		
		if not settings or not settings.enabled:
			return {
				"success": False,
				"error": "RingCentral Settings not configured"
			}
		
		# Try to get access token
		access_token = get_ringcentral_token(settings)
		
		if access_token:
			return {
				"success": True,
				"message": "✅ Successfully connected to RingCentral API!",
				"token_preview": access_token[:20] + "..." if len(access_token) > 20 else access_token
			}
		else:
			return {
				"success": False,
				"error": "Failed to get access token. Check credentials."
			}
			
	except Exception as e:
		return {
			"success": False,
			"error": str(e)
		}

