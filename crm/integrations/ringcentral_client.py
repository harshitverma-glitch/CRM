"""
RingCentral API Client for CRM
Handles authentication, recording downloads, and transcription
"""

import frappe
import requests
import json
from typing import Dict, Any, Optional
import base64
import time
import jwt as pyjwt  # PyJWT library for JWT signing
from frappe.utils.password import get_decrypted_password


class RingCentralClient:
	"""
	RingCentral API Client for fetching recordings and transcripts
	"""
	
	def __init__(self):
		"""Initialize RingCentral client with credentials from settings"""
		self.base_url = "https://platform.ringcentral.com"
		self.access_token = None
		self.account_id = None
		
		# Get credentials from CRM RingCentral Settings
		self.client_id = frappe.db.get_single_value("CRM RingCentral Settings", "client_id")
		# Use get_decrypted_password() for Password field to get actual value (not masked *******)
		self.client_secret = get_decrypted_password(
			"CRM RingCentral Settings",
			"CRM RingCentral Settings",
			"client_secret"
		)
		self.server_url = "https://platform.ringcentral.com"
		
	
	def authenticate_auto(self, account_id: str = None) -> bool:
		"""
		Auto-authenticate: Try OAuth first, fallback to JWT, then Password Flow.
		Modern approach prioritizes OAuth (most secure and reliable).
		
		Args:
			account_id: RingCentral account ID (optional, defaults to ~)
		
		Returns:
			bool: True if any authentication successful
		"""
		# Try OAuth first (modern, secure, works with 3-legged auth)
		try:
			from crm.api.ringcentral_auth import get_valid_access_token
			access_token = get_valid_access_token()
			
			if access_token:
				self.access_token = access_token
				self.account_id = account_id or "~"
				frappe.logger().info("✅ RingCentral: Authenticated via OAuth")
				return True
		except Exception as e:
			frappe.logger().info(f"⚠️  RingCentral: OAuth not available: {str(e)}")
		
		# Try JWT if OAuth fails
		if self.authenticate_jwt(account_id):
			frappe.logger().info("✅ RingCentral: Authenticated via JWT")
			return True
		
		# Fallback to Password Flow (deprecated)
		frappe.logger().info("⚠️  RingCentral: JWT failed, trying Password Flow...")
		if self.authenticate_password():
			frappe.logger().info("✅ RingCentral: Authenticated via Password Flow")
			return True
		
		# All methods failed
		frappe.logger().error("❌ RingCentral: All authentication methods failed")
		return False
	
	
	def authenticate_jwt(self, account_id: str = None) -> bool:
		"""
		Authenticate with RingCentral using JWT Bearer Grant
		Generates and signs a JWT token, then exchanges it for an access token
		
		Args:
			account_id: RingCentral account ID (optional, defaults to ~)
		
		Returns:
			bool: True if authentication successful
		"""
		try:
			if not self.client_id or not self.client_secret:
				frappe.log_error(
					title="RingCentral JWT Auth Failed",
					message="Client ID or Client Secret not configured"
				)
				return False
			
			# Get account_id from parameter or use default
			acc_id = account_id or "~"
			
			# Step 1: Create JWT token payload
			current_time = int(time.time())
			payload = {
				"iss": self.client_id,  # Issuer: Your Client ID
				"sub": self.client_id,  # Subject: Your Client ID
				"aud": "https://platform.ringcentral.com/restapi/oauth/token",  # Audience: RingCentral token endpoint
				"iat": current_time,  # Issued at
				"exp": current_time + 60  # Expires in 60 seconds
			}
			
			# Step 2: Sign the JWT token with Client Secret
			jwt_token = pyjwt.encode(payload, self.client_secret, algorithm="HS256")
			
			# Step 3: Prepare Basic Auth (required for JWT Bearer grant)
			auth_string = f"{self.client_id}:{self.client_secret}"
			auth_bytes = auth_string.encode('utf-8')
			auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
			
			# Step 4: Exchange JWT for access token with Basic Auth
			headers = {
				"Authorization": f"Basic {auth_b64}",
				"Content-Type": "application/x-www-form-urlencoded"
			}
			
			data = {
				"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
				"assertion": jwt_token
			}
			
			response = requests.post(
				f"{self.server_url}/restapi/oauth/token",
				headers=headers,
				data=data,
				timeout=30
			)
			
			if response.status_code == 200:
				result = response.json()
				self.access_token = result.get("access_token")
				self.account_id = acc_id
				frappe.logger().info(f"✅ RingCentral JWT authentication successful (account: {acc_id})")
				return True
			else:
				frappe.log_error(
					title="RingCentral JWT Authentication Failed",
					message=f"Status: {response.status_code}\n{response.text}"
				)
				return False
				
		except Exception as e:
			frappe.log_error(
				title="RingCentral JWT Authentication Error",
				message=f"Error: {str(e)}\n{frappe.get_traceback()}"
			)
			return False
	
	
	def authenticate_password(self) -> bool:
		"""
		Authenticate with RingCentral using Password Flow.
		Requires username, password, and extension from settings.
		
		Returns:
			bool: True if authentication successful
		"""
		try:
			# Get password flow credentials from settings
			settings = frappe.get_single("CRM RingCentral Settings")
			username = settings.username
			password = get_decrypted_password(
				"CRM RingCentral Settings",
				"CRM RingCentral Settings",
				"password"
			) if settings.password else None
			extension = settings.extension
			
			if not username or not password or not extension:
				frappe.logger().info("Password Flow: Missing username/password/extension")
				return False
			
			if not self.client_id or not self.client_secret:
				return False
			
			# Prepare authentication with Basic Auth
			auth_string = f"{self.client_id}:{self.client_secret}"
			auth_bytes = auth_string.encode('utf-8')
			auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
			
			headers = {
				"Authorization": f"Basic {auth_b64}",
				"Content-Type": "application/x-www-form-urlencoded"
			}
			
			# Password Flow uses password grant type
			data = {
				"grant_type": "password",
				"username": username,
				"password": password,
				"extension": extension
			}
			
			response = requests.post(
				f"{self.server_url}/restapi/oauth/token",
				headers=headers,
				data=data,
				timeout=30
			)
			
			if response.status_code == 200:
				result = response.json()
				self.access_token = result.get("access_token")
				self.account_id = result.get("owner_id", "~")
				frappe.logger().info(f"✅ RingCentral Password Flow authentication successful")
				return True
			else:
				frappe.log_error(
					title="RingCentral Password Authentication Failed",
					message=f"Status: {response.status_code}\n{response.text}"
				)
				return False
				
		except Exception as e:
			frappe.log_error(
				title="RingCentral Password Authentication Error",
				message=f"Error: {str(e)}\n{frappe.get_traceback()}"
			)
			return False
	
	
	def get_call_log_details(self, session_id: str, account_id: str = None) -> Optional[Dict[str, Any]]:
		"""
		Fetch call log details from RingCentral Call Log API
		This provides accurate duration, start time, and end time
		
		Args:
			session_id: RingCentral session ID (telephonySessionId)
			account_id: Account ID (optional, uses authenticated account if not provided)
			
		Returns:
			dict: Call log details with duration, timestamps, etc.
		"""
		try:
			if not self.access_token:
				frappe.throw("Not authenticated. Call authenticate() first.")
			
			acc_id = account_id or self.account_id
			if not acc_id:
				frappe.throw("No account ID available")
			
			headers = {
				"Authorization": f"Bearer {self.access_token}"
			}
			
			# Query call log by session ID
			url = f"{self.server_url}/restapi/v1.0/account/{acc_id}/call-log"
			params = {
				"sessionId": session_id,
				"view": "Detailed"
			}
			
			response = requests.get(url, headers=headers, params=params, timeout=30)
			
			if response.status_code == 200:
				result = response.json()
				records = result.get("records", [])
				if records:
					return records[0]  # Return first matching record
				else:
					frappe.logger().info(f"No call log found for session {session_id}")
					return None
			else:
				frappe.log_error(
					title="RingCentral Call Log Fetch Failed",
					message=f"Session ID: {session_id}\nStatus: {response.status_code}\n{response.text}"
				)
				return None
				
		except Exception as e:
			frappe.log_error(
				title="RingCentral Call Log Fetch Error",
				message=f"Session ID: {session_id}\nError: {str(e)}"
			)
			return None
	
	
	def get_recording(self, recording_id: str, account_id: str = None) -> Optional[bytes]:
		"""
		Download call recording from RingCentral
		
		Args:
			recording_id: RingCentral recording ID
			account_id: Account ID (optional, uses authenticated account if not provided)
			
		Returns:
			bytes: Recording file content (audio)
		"""
		try:
			if not self.access_token:
				frappe.throw("Not authenticated. Call authenticate() first.")
			
			acc_id = account_id or self.account_id
			if not acc_id:
				frappe.throw("No account ID available")
			
			headers = {
				"Authorization": f"Bearer {self.access_token}"
			}
			
			url = f"{self.server_url}/restapi/v1.0/account/{acc_id}/recording/{recording_id}/content"
			
			response = requests.get(url, headers=headers, timeout=30)
			
			if response.status_code == 200:
				return response.content
			else:
				frappe.log_error(
					title="RingCentral Recording Download Failed",
					message=f"Recording ID: {recording_id}\nStatus: {response.status_code}\n{response.text}"
				)
				return None
				
		except Exception as e:
			frappe.log_error(
				title="RingCentral Recording Download Error",
				message=f"Recording ID: {recording_id}\nError: {str(e)}"
			)
			return None
	
	
	def get_message_recording(self, message_id: str, account_id: str = None, extension_id: str = None) -> Optional[bytes]:
		"""
		Download voicemail recording from RingCentral Messages
		
		Args:
			message_id: RingCentral message ID
			account_id: Account ID (optional, uses authenticated account if not provided)
			extension_id: Extension ID (optional, uses ~ for current extension)
			
		Returns:
			bytes: Recording file content (audio)
		"""
		try:
			if not self.access_token:
				frappe.throw("Not authenticated. Call authenticate() first.")
			
			acc_id = account_id or "~"
			ext_id = extension_id or "~"
			
			headers = {
				"Authorization": f"Bearer {self.access_token}"
			}
			
			# First, get the message to find the attachment ID
			msg_url = f"{self.server_url}/restapi/v1.0/account/{acc_id}/extension/{ext_id}/message-store/{message_id}"
			msg_response = requests.get(msg_url, headers=headers, timeout=30)
			
			if msg_response.status_code != 200:
				frappe.log_error(
					title="RingCentral Message Fetch Failed",
					message=f"Message ID: {message_id}\nStatus: {msg_response.status_code}\n{msg_response.text}"
				)
				return None
			
			message_data = msg_response.json()
			
			# Get the attachment (recording)
			attachments = message_data.get("attachments", [])
			if not attachments:
				frappe.log_error(
					title="No Recording Attachment Found",
					message=f"Message ID: {message_id}\nMessage has no attachments"
				)
				return None
			
			# Get the first audio attachment
			audio_attachment = None
			for att in attachments:
				if att.get("contentType", "").startswith("audio/"):
					audio_attachment = att
					break
			
			if not audio_attachment:
				return None
			
			# Download the attachment
			attachment_id = audio_attachment.get("id")
			content_url = f"{self.server_url}/restapi/v1.0/account/{acc_id}/extension/{ext_id}/message-store/{message_id}/content/{attachment_id}"
			
			content_response = requests.get(content_url, headers=headers, timeout=60)
			
			if content_response.status_code == 200:
				return content_response.content
			else:
				frappe.log_error(
					title="RingCentral Recording Content Download Failed",
					message=f"Message ID: {message_id}\nAttachment ID: {attachment_id}\nStatus: {content_response.status_code}"
				)
				return None
				
		except Exception as e:
			frappe.log_error(
				title="RingCentral Message Recording Error",
				message=f"Message ID: {message_id}\nError: {str(e)}"
			)
			return None
	
	
	def save_recording_to_file(self, recording_data: bytes, identifier: str, call_log_name: str) -> Optional[str]:
		"""
		Save recording data as File in ERPNext
		
		Args:
			recording_data: Binary audio data
			identifier: Recording or message ID for filename
			call_log_name: Name of CRM Call Log to attach to
			
		Returns:
			str: File URL in ERPNext
		"""
		try:
			if not recording_data:
				return None
			
			# Create File in ERPNext
			from frappe.utils.file_manager import save_file
			
			filename = f"call_recording_{identifier}.mp3"
			
			# Save as PUBLIC file (is_private=0) so HTML5 audio player can access it
			file_doc = save_file(
				fname=filename,
				content=recording_data,
				dt="CRM Call Log",
				dn=call_log_name,
				is_private=0  # Changed from 1 to 0 - makes file publicly accessible
			)
			
			return file_doc.file_url
			
		except Exception as e:
			frappe.log_error(
				title="RingCentral Recording Save Error",
				message=f"Identifier: {identifier}\nCall Log: {call_log_name}\nError: {str(e)}"
			)
			return None
	
	def get_ringcentral_transcript(self, recording_id: str, account_id: str = None) -> Optional[str]:
		"""
		Get transcript from RingCentral AI API
		
		Args:
			recording_id: RingCentral recording ID (or message_ID prefixed with "message_")
			account_id: Account ID (optional, defaults to ~)
			
		Returns:
			str: Transcript text or None if not available
		"""
		try:
			if not self.access_token:
				frappe.logger().error("RingCentral: Not authenticated")
				return None
			
			acc_id = account_id or self.account_id or "~"
			
			# Handle message-based recording IDs (voicemail)
			if recording_id.startswith("message_"):
				message_id = recording_id.replace("message_", "")
				settings = frappe.get_single("CRM RingCentral Settings")
				extension_id = settings.extension_id if settings.extension_id else "~"
				
				# Get message to check for voicemail transcription
				msg_url = f"{self.base_url}/restapi/v1.0/account/{acc_id}/extension/{extension_id}/message-store/{message_id}"
				
				headers = {
					"Authorization": f"Bearer {self.access_token}",
					"Accept": "application/json"
				}
				
				response = requests.get(msg_url, headers=headers, timeout=30)
				
				if response.status_code == 200:
					message_data = response.json()
					vm_transcription_status = message_data.get("vmTranscriptionStatus")
					
					# Check if voicemail has transcription
					if vm_transcription_status == "Completed":
						# Get transcription from message subject or body
						transcript_text = message_data.get("subject") or message_data.get("body")
						if transcript_text:
							frappe.logger().info(f"✅ Voicemail transcript retrieved for message {message_id}")
							return transcript_text
				
				frappe.logger().info(f"RingCentral: No voicemail transcript available for message {message_id}")
				return None
			
			# Try to get transcript from RingCentral AI API for regular recordings
			url = f"{self.base_url}/restapi/v1.0/account/{acc_id}/recording/{recording_id}/transcript"
			
			headers = {
				"Authorization": f"Bearer {self.access_token}",
				"Accept": "application/json"
			}
			
			response = requests.get(url, headers=headers, timeout=30)
			
			if response.status_code == 200:
				data = response.json()
				# RingCentral may return transcript in different formats
				# Try to extract text from common response structures
				if isinstance(data, dict):
					transcript = data.get("transcript") or data.get("text") or data.get("content")
					if transcript:
						frappe.logger().info(f"✅ RingCentral transcript retrieved for recording {recording_id}")
						return transcript
				elif isinstance(data, str):
					return data
			elif response.status_code == 404:
				frappe.logger().info(f"RingCentral: No transcript available for recording {recording_id}")
			else:
				frappe.logger().warning(f"RingCentral transcript API returned {response.status_code}: {response.text}")
			
			return None
			
		except Exception as e:
			frappe.logger().error(f"RingCentral transcript error: {str(e)}")
			return None


@frappe.whitelist()
def fetch_and_save_recording(call_log_name: str) -> Dict[str, Any]:
	"""
	Fetch recording for a call log and save to ERPNext
	Handles both direct recording URLs and voicemail message URLs
	
	Args:
		call_log_name: Name of CRM Call Log
		
	Returns:
		Dict with success status and file URL
	"""
	try:
		call_log = frappe.get_doc("CRM Call Log", call_log_name)
		
		if not call_log.recording_url:
			return {"success": False, "message": "No recording URL found"}
		
		recording_url = call_log.recording_url
		
		# Initialize client and authenticate
		client = RingCentralClient()
		
		# Get credentials from settings and authenticate
		settings = frappe.get_single("CRM RingCentral Settings")
		if not settings or not settings.enabled:
			return {"success": False, "message": "RingCentral Settings not configured or disabled"}
		
		# Authenticate using auto-fallback (tries JWT first, then Password Flow)
		account_id = settings.account_id if settings.account_id else "~"
		auth_success = client.authenticate_auto(account_id=account_id)
		
		if not auth_success:
			return {"success": False, "message": "RingCentral authentication failed. Check Client ID, Client Secret, and optionally Username/Password/Extension in settings."}
		
		# Determine URL type and extract IDs
		import re
		recording_data = None
		identifier = None
		
		# Type 1: Voicemail Message URL
		# Format: https://app.ringcentral.com/messages/{messageId}
		message_match = re.search(r'/messages/(\d+)', recording_url)
		
		if message_match:
			message_id = message_match.group(1)
			identifier = f"msg_{message_id}"
			
			account_id = settings.account_id if settings.account_id else "~"
			extension_id = settings.extension_id if settings.extension_id else "~"
			
			recording_data = client.get_message_recording(message_id, account_id, extension_id)
		
		# Type 2: Direct Recording URL
		# Format: https://platform.ringcentral.com/restapi/v1.0/account/{accountId}/recording/{recordingId}/content
		else:
			recording_match = re.search(r'/recording/([^/]+)/content', recording_url)
			
			if recording_match:
				recording_id = recording_match.group(1)
				identifier = f"rec_{recording_id}"
				
				# Extract account ID
				match_account = re.search(r'/account/([^/]+)/', recording_url)
				account_id = match_account.group(1) if match_account else None
				
				recording_data = client.get_recording(recording_id, account_id)
			else:
				return {"success": False, "message": "Invalid recording URL format. Must be RingCentral message or recording URL."}
		
		if not recording_data:
			return {"success": False, "message": "Failed to download recording from RingCentral"}
		
		# Save recording to file
		file_url = client.save_recording_to_file(recording_data, identifier, call_log_name)
		
		if file_url:
			# Preserve original RingCentral URL for transcript fetching
			call_log.db_set('ringcentral_recording_url', recording_url, update_modified=False)
			# Update call log with local file URL
			call_log.db_set('recording_url', file_url, update_modified=True)
			frappe.db.commit()
			
			return {
				"success": True,
				"message": "Recording downloaded successfully",
				"file_url": file_url
			}
		else:
			return {"success": False, "message": "Failed to save recording to ERPNext"}
			
	except Exception as e:
		frappe.log_error(
			title="Fetch Recording Error",
			message=f"Call Log: {call_log_name}\nError: {str(e)}\nTraceback: {frappe.get_traceback()}"
		)
		return {"success": False, "message": str(e)}


@frappe.whitelist()
def transcribe_recording(call_log_name: str) -> Dict[str, Any]:
	"""
	Transcribe call recording using RingCentral native transcription
	
	Args:
		call_log_name: Name of CRM Call Log
		
	Returns:
		Dict with transcript text
	"""
	try:
		call_log = frappe.get_doc("CRM Call Log", call_log_name)
		
		# Check if transcript already exists
		if call_log.transcript:
			return {
				"success": True,
				"message": "Transcript already exists",
				"transcript": call_log.transcript,
				"cached": True
			}
		
		# Try to use preserved RingCentral URL first, fallback to recording_url
		url_to_use = getattr(call_log, 'ringcentral_recording_url', None) or call_log.recording_url
		
		if not url_to_use:
			return {"success": False, "message": "No recording URL found"}
		
		# Extract recording ID from URL
		import re
		
		# Check if it's a local file (already downloaded)
		if url_to_use.startswith("/files/") or url_to_use.startswith("/private/files/"):
			return {
				"success": False,
				"message": "Recording is stored locally. Transcripts can only be fetched from RingCentral URLs. Please try fetching before the recording is downloaded."
			}
		
		# Try direct recording URL format
		recording_match = re.search(r'/recording/([^/]+)/content', url_to_use)
		if recording_match:
			recording_id = recording_match.group(1)
		else:
			# Try message URL format (voicemail)
			message_match = re.search(r'/messages/(\d+)', url_to_use)
			if message_match:
				recording_id = f"message_{message_match.group(1)}"
			else:
				# Try alternative recording format without /content
				recording_match_alt = re.search(r'/recording/([^/]+)$', url_to_use)
				if recording_match_alt:
					recording_id = recording_match_alt.group(1)
				else:
					return {
						"success": False,
						"message": f"Could not extract recording ID from URL: {url_to_use}"
					}
		
		# Initialize and authenticate RingCentral client
		client = RingCentralClient()
		settings = frappe.get_single("CRM RingCentral Settings")
		account_id = settings.account_id if settings and settings.account_id else "~"
		
		if not client.authenticate_auto(account_id=account_id):
			return {"success": False, "message": "Failed to authenticate with RingCentral"}
		
		# Get transcript from RingCentral
		transcript = client.get_ringcentral_transcript(recording_id, account_id)
		
		if transcript:
			# Save transcript directly to call log field
			call_log.db_set('transcript', transcript, update_modified=True)
			frappe.db.commit()
			
			frappe.logger().info(f"✅ RingCentral transcription successful for {call_log_name}")
			
			return {
				"success": True,
				"message": "Transcript generated successfully",
				"transcript": transcript,
				"cached": False
			}
		else:
			return {
				"success": False,
				"message": "RingCentral transcription not available for this recording. The recording may not have been transcribed yet, or transcription may not be enabled for your RingCentral account."
			}
			
	except Exception as e:
		frappe.log_error(
			title="Transcription Error",
			message=f"Call Log: {call_log_name}\nError: {str(e)}\n{frappe.get_traceback()}"
		)
		return {"success": False, "message": f"Error: {str(e)}"}



