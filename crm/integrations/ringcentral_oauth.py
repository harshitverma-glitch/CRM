"""
RingCentral OAuth Authorization Code Flow for ERPNext
This implements the modern OAuth flow since Password Flow is deprecated
"""

import frappe
import requests
import secrets
from urllib.parse import urlencode
from typing import Dict, Any, Optional
from frappe.utils.password import get_decrypted_password


@frappe.whitelist(allow_guest=True)
def ringcentral_callback():
	"""
	OAuth callback endpoint for RingCentral authorization
	URL: https://your-erp-domain.com/api/method/crm.integrations.ringcentral_oauth.ringcentral_callback
	"""
	try:
		# Get authorization code from URL parameter
		code = frappe.form_dict.get("code")
		state = frappe.form_dict.get("state")
		
		if not code:
			error = frappe.form_dict.get("error")
			error_description = frappe.form_dict.get("error_description", "")
			frappe.throw(f"Authorization failed: {error} - {error_description}")
		
		# Verify state to prevent CSRF
		stored_state = frappe.cache().get_value("ringcentral_oauth_state")
		if state != stored_state:
			frappe.throw("Invalid state parameter - possible CSRF attack")
		
		# Exchange code for access token
		settings = frappe.get_single("CRM RingCentral Settings")
		client_secret = get_decrypted_password(
			"CRM RingCentral Settings",
			"CRM RingCentral Settings",
			"client_secret"
		)
		
		token_url = "https://platform.ringcentral.com/restapi/oauth/token"
		
		import base64
		auth_string = f"{settings.client_id}:{client_secret}"
		auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
		
		headers = {
			"Authorization": f"Basic {auth_b64}",
			"Content-Type": "application/x-www-form-urlencoded"
		}
		
		# Get redirect URI from settings (or construct it)
		redirect_uri = settings.redirect_uri or get_redirect_uri()
		
		data = {
			"grant_type": "authorization_code",
			"code": code,
			"redirect_uri": redirect_uri
		}
		
		response = requests.post(token_url, headers=headers, data=data, timeout=30)
		response.raise_for_status()
		
		token_data = response.json()
		
		# Store tokens securely
		store_tokens(token_data)
		
		# Show success page
		frappe.respond_as_web_page(
			"Authorization Successful",
			"✅ RingCentral has been successfully connected! You can close this window.",
			indicator_color="green"
		)
		
	except Exception as e:
		frappe.log_error(
			title="RingCentral OAuth Callback Error",
			message=frappe.get_traceback()
		)
		frappe.respond_as_web_page(
			"Authorization Failed",
			f"❌ Failed to connect RingCentral: {str(e)}",
			indicator_color="red"
		)


@frappe.whitelist()
def initiate_authorization():
	"""
	Start the OAuth authorization flow
	Returns the authorization URL that user should visit
	"""
	try:
		settings = frappe.get_single("CRM RingCentral Settings")
		
		if not settings.client_id:
			frappe.throw("Client ID not configured")
		
		# Generate state for CSRF protection
		state = secrets.token_urlsafe(32)
		frappe.cache().set_value("ringcentral_oauth_state", state, expires_in_sec=600)
		
		# Get redirect URI
		redirect_uri = settings.redirect_uri or get_redirect_uri()
		
		# Build authorization URL
		params = {
			"response_type": "code",
			"client_id": settings.client_id,
			"redirect_uri": redirect_uri,
			"state": state,
			"prompt": "login consent"
		}
		
		auth_url = f"https://platform.ringcentral.com/restapi/oauth/authorize?{urlencode(params)}"
		
		return {
			"success": True,
			"authorization_url": auth_url,
			"message": "Please visit the URL to authorize RingCentral"
		}
		
	except Exception as e:
		frappe.log_error(
			title="RingCentral OAuth Initiation Error",
			message=frappe.get_traceback()
		)
		return {
			"success": False,
			"error": str(e)
		}


def get_redirect_uri() -> str:
	"""Get the OAuth redirect URI for this ERPNext instance"""
	site_url = frappe.utils.get_url()
	return f"{site_url}/api/method/crm.integrations.ringcentral_oauth.ringcentral_callback"


def store_tokens(token_data: Dict[str, Any]):
	"""Store OAuth tokens securely"""
	from frappe.utils.password import set_encrypted_password
	
	# Store access token
	set_encrypted_password(
		"CRM RingCentral Settings",
		"CRM RingCentral Settings",
		token_data.get("access_token"),
		fieldname="access_token"
	)
	
	# Store refresh token
	if token_data.get("refresh_token"):
		set_encrypted_password(
			"CRM RingCentral Settings",
			"CRM RingCentral Settings",
			token_data.get("refresh_token"),
			fieldname="refresh_token"
		)
	
	# Store token expiry time
	import time
	expires_in = token_data.get("expires_in", 3600)
	expires_at = int(time.time()) + expires_in
	
	frappe.db.set_value(
		"CRM RingCentral Settings",
		"CRM RingCentral Settings",
		{
			"token_expires_at": expires_at,
			"last_token_refresh": frappe.utils.now()
		}
	)
	frappe.db.commit()


def get_valid_access_token() -> Optional[str]:
	"""
	Get a valid access token, refreshing if necessary
	This is what the recording download should call
	"""
	from frappe.utils.password import get_decrypted_password
	import time
	
	settings = frappe.get_single("CRM RingCentral Settings")
	
	# Check if token is expired
	expires_at = settings.get("token_expires_at", 0)
	
	if time.time() >= expires_at - 300:  # Refresh 5 minutes before expiry
		# Token expired, refresh it
		refresh_token = get_decrypted_password(
			"CRM RingCentral Settings",
			"CRM RingCentral Settings",
			"refresh_token"
		)
		
		if refresh_token:
			new_token_data = refresh_access_token(refresh_token)
			if new_token_data:
				store_tokens(new_token_data)
				return new_token_data.get("access_token")
		else:
			# No refresh token, need to re-authorize
			frappe.throw("RingCentral authorization expired. Please re-authorize.")
	
	# Return existing token
	return get_decrypted_password(
		"CRM RingCentral Settings",
		"CRM RingCentral Settings",
		"access_token"
	)


def refresh_access_token(refresh_token: str) -> Optional[Dict[str, Any]]:
	"""Refresh the access token using refresh token"""
	try:
		settings = frappe.get_single("CRM RingCentral Settings")
		client_secret = get_decrypted_password(
			"CRM RingCentral Settings",
			"CRM RingCentral Settings",
			"client_secret"
		)
		
		import base64
		auth_string = f"{settings.client_id}:{client_secret}"
		auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
		
		headers = {
			"Authorization": f"Basic {auth_b64}",
			"Content-Type": "application/x-www-form-urlencoded"
		}
		
		data = {
			"grant_type": "refresh_token",
			"refresh_token": refresh_token
		}
		
		response = requests.post(
			"https://platform.ringcentral.com/restapi/oauth/token",
			headers=headers,
			data=data,
			timeout=30
		)
		response.raise_for_status()
		
		return response.json()
		
	except Exception as e:
		frappe.log_error(
			title="RingCentral Token Refresh Error",
			message=frappe.get_traceback()
		)
		return None

