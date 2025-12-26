"""
RingCentral OAuth Callback - Simple Version
Matches the redirect URI already configured in RingCentral app
"""

import frappe
import requests
import base64
import secrets
from typing import Dict, Any, Optional
from frappe.utils.password import get_decrypted_password, set_encrypted_password


@frappe.whitelist(allow_guest=True)
def ringcentral_auth_callback():
	"""
	OAuth callback endpoint for RingCentral authorization
	Fast callback - just stores code and redirects immediately
	"""
	try:
		# Get authorization code from URL parameter
		code = frappe.form_dict.get("code")
		state = frappe.form_dict.get("state")
		
		if not code:
			error = frappe.form_dict.get("error")
			error_description = frappe.form_dict.get("error_description", "")
			return {
				"success": False,
				"error": f"{error}: {error_description}"
			}
		
		# Store code in cache for immediate retrieval (10 minute expiry)
		frappe.cache().set_value("ringcentral_auth_code", code, expires_in_sec=600)
		frappe.cache().set_value("ringcentral_auth_state_received", state, expires_in_sec=600)
		
		# Return success page IMMEDIATELY (no token exchange yet - that's done separately)
		frappe.respond_as_web_page(
			"Authorization Successful",
			"""
			<div style='text-align: center; padding: 40px;'>
				<h1 style='color: green; font-size: 48px;'>✅</h1>
				<h2>Authorization Code Received!</h2>
				<p>RingCentral has authorized your app.</p>
				<p>Close this window and run the token exchange in your console.</p>
				<p style='margin-top: 20px; padding: 15px; background: #f0f0f0; border-radius: 5px;'>
					<code>from crm.api.ringcentral_auth import complete_authorization<br>
					complete_authorization()</code>
				</p>
			</div>
			""",
			indicator_color="green"
		)
		
	except Exception as e:
		frappe.log_error(
			title="RingCentral OAuth Callback Error",
			message=frappe.get_traceback()
		)
		return {"success": False, "error": str(e)}


@frappe.whitelist()
def complete_authorization():
	"""
	Complete the authorization by exchanging the stored code for tokens
	Call this after the callback has stored the authorization code
	"""
	try:
		# Get the stored code
		code = frappe.cache().get_value("ringcentral_auth_code")
		state_received = frappe.cache().get_value("ringcentral_auth_state_received")
		
		if not code:
			return {
				"success": False,
				"error": "No authorization code found. Please authorize first."
			}
		
		# Verify state
		stored_state = frappe.cache().get_value("ringcentral_oauth_state")
		if state_received != stored_state:
			return {
				"success": False,
				"error": "State mismatch - possible CSRF attack"
			}
		
		# Exchange code for token
		settings = frappe.get_single("CRM RingCentral Settings")
		client_secret = get_decrypted_password(
			"CRM RingCentral Settings",
			"CRM RingCentral Settings",
			"client_secret"
		)
		
		auth_string = f"{settings.client_id}:{client_secret}"
		auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
		
		site_url = frappe.utils.get_url()
		redirect_uri = f"{site_url}/api/method/crm.api.ringcentral_auth.ringcentral_auth_callback"
		
		headers = {
			"Authorization": f"Basic {auth_b64}",
			"Content-Type": "application/x-www-form-urlencoded"
		}
		
		data = {
			"grant_type": "authorization_code",
			"code": code,
			"redirect_uri": redirect_uri
		}
		
		response = requests.post(
			"https://platform.ringcentral.com/restapi/oauth/token",
			headers=headers,
			data=data,
			timeout=30
		)
		
		if response.status_code != 200:
			return {
				"success": False,
				"error": f"Token exchange failed: {response.text}"
			}
		
		token_data = response.json()
		
		# Store tokens
		store_oauth_tokens(token_data)
		
		# Clear cached code
		frappe.cache().delete_value("ringcentral_auth_code")
		frappe.cache().delete_value("ringcentral_auth_state_received")
		
		return {
			"success": True,
			"message": "✅ RingCentral connected successfully!",
			"token_preview": token_data.get("access_token")[:30] + "...",
			"expires_in": token_data.get("expires_in")
		}
		
	except Exception as e:
		frappe.log_error(
			title="RingCentral Token Exchange Error",
			message=frappe.get_traceback()
		)
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def start_authorization():
	"""
	Start the OAuth authorization flow
	Returns the authorization URL that user should visit
	"""
	try:
		settings = frappe.get_single("CRM RingCentral Settings")
		
		if not settings.client_id:
			frappe.throw("Client ID not configured in CRM RingCentral Settings")
		
		# Generate state for CSRF protection
		state = secrets.token_urlsafe(32)
		frappe.cache().set_value("ringcentral_oauth_state", state, expires_in_sec=600)
		
		# Get redirect URI (matches RingCentral app configuration)
		site_url = frappe.utils.get_url()
		redirect_uri = f"{site_url}/api/method/ringcentral_auth_callback"
		
		# Build authorization URL
		from urllib.parse import urlencode
		params = {
			"response_type": "code",
			"client_id": settings.client_id,
			"redirect_uri": redirect_uri,
			"state": state
		}
		
		auth_url = f"https://platform.ringcentral.com/restapi/oauth/authorize?{urlencode(params)}"
		
		return {
			"success": True,
			"authorization_url": auth_url,
			"redirect_uri": redirect_uri
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


def store_oauth_tokens(token_data: Dict[str, Any]):
	"""Store OAuth tokens securely in CRM RingCentral Settings"""
	import time
	
	# Store access token
	if token_data.get("access_token"):
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
	
	frappe.logger().info("✅ RingCentral OAuth tokens stored successfully")


def get_valid_access_token() -> Optional[str]:
	"""
	Get a valid access token, refreshing if necessary
	This is what the recording download should call
	"""
	import time
	
	settings = frappe.get_single("CRM RingCentral Settings")
	
	# Check if token is expired
	expires_at = settings.get("token_expires_at", 0)
	
	if time.time() >= expires_at - 300:  # Refresh 5 minutes before expiry
		frappe.logger().info("🔄 Access token expired, refreshing...")
		
		refresh_token = get_decrypted_password(
			"CRM RingCentral Settings",
			"CRM RingCentral Settings",
			"refresh_token"
		)
		
		if refresh_token:
			new_token_data = refresh_access_token(refresh_token)
			if new_token_data:
				store_oauth_tokens(new_token_data)
				return new_token_data.get("access_token")
		else:
			frappe.log_error(
				title="RingCentral Token Refresh Failed",
				message="No refresh token available. Please re-authorize RingCentral."
			)
			return None
	
	# Return existing token
	access_token = get_decrypted_password(
		"CRM RingCentral Settings",
		"CRM RingCentral Settings",
		"access_token"
	)
	
	if access_token:
		frappe.logger().info("✅ Using existing access token")
	
	return access_token


def refresh_access_token(refresh_token: str) -> Optional[Dict[str, Any]]:
	"""Refresh the access token using refresh token"""
	try:
		settings = frappe.get_single("CRM RingCentral Settings")
		client_secret = get_decrypted_password(
			"CRM RingCentral Settings",
			"CRM RingCentral Settings",
			"client_secret"
		)
		
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
		
		frappe.logger().info("✅ Access token refreshed successfully")
		return response.json()
		
	except Exception as e:
		frappe.log_error(
			title="RingCentral Token Refresh Error",
			message=frappe.get_traceback()
		)
		return None


@frappe.whitelist()
def test_connection():
	"""Test RingCentral OAuth connection"""
	try:
		token = get_valid_access_token()
		
		if token:
			return {
				"success": True,
				"message": "✅ RingCentral is connected and authenticated!",
				"token_preview": token[:20] + "..."
			}
		else:
			return {
				"success": False,
				"message": "❌ Not authenticated. Please authorize RingCentral first."
			}
			
	except Exception as e:
		return {
			"success": False,
			"error": str(e)
		}

