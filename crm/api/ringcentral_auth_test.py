"""
RingCentral Authentication Diagnostic and Test Tool
Tests both JWT and Password Flow authentication
"""

import frappe
from frappe.utils.password import get_decrypted_password
import requests
import base64
import json


@frappe.whitelist()
def test_ringcentral_auth():
	"""
	Test RingCentral authentication with current settings.
	Tests both JWT and Password Flow to see which works.
	
	Returns:
		dict with test results and recommendations
	"""
	print("\n" + "="*70)
	print("🔐 RINGCENTRAL AUTHENTICATION DIAGNOSTIC")
	print("="*70 + "\n")
	
	# Get settings
	settings = frappe.get_single("CRM RingCentral Settings")
	
	if not settings.enabled:
		return {
			"success": False,
			"message": "RingCentral integration is disabled. Enable it first in CRM RingCentral Settings."
		}
	
	# Get credentials
	client_id = settings.client_id
	client_secret = get_decrypted_password(
		"CRM RingCentral Settings",
		"CRM RingCentral Settings",
		"client_secret"
	)
	username = settings.username
	password = get_decrypted_password(
		"CRM RingCentral Settings",
		"CRM RingCentral Settings",
		"password"
	) if settings.password else None
	extension = settings.extension
	account_id = settings.account_id or "~"
	
	results = {
		"settings_check": {},
		"jwt_test": {},
		"password_test": {},
		"recommendations": []
	}
	
	# 1. Check settings
	print("📋 Step 1: Checking Settings...")
	results["settings_check"] = {
		"client_id_set": bool(client_id),
		"client_secret_set": bool(client_secret),
		"username_set": bool(username),
		"password_set": bool(password),
		"extension_set": bool(extension),
		"account_id": account_id
	}
	
	print(f"   Client ID: {'✅ Set' if client_id else '❌ Missing'}")
	print(f"   Client Secret: {'✅ Set' if client_secret else '❌ Missing'}")
	print(f"   Username: {'✅ Set' if username else '⚠️  Not set (needed for Password auth)'}")
	print(f"   Password: {'✅ Set' if password else '⚠️  Not set (needed for Password auth)'}")
	print(f"   Extension: {'✅ Set' if extension else '⚠️  Not set (needed for Password auth)'}")
	print(f"   Account ID: {account_id}")
	
	# 2. Test JWT Authentication
	print(f"\n🔑 Step 2: Testing JWT Authentication...")
	if client_id and client_secret:
		jwt_result = test_jwt_auth(client_id, client_secret, account_id)
		results["jwt_test"] = jwt_result
		
		if jwt_result["success"]:
			print(f"   ✅ JWT Authentication: SUCCESS")
			print(f"   Access Token: {jwt_result['access_token'][:30]}...")
			results["recommendations"].append("✅ JWT auth works! Use this method.")
		else:
			print(f"   ❌ JWT Authentication: FAILED")
			print(f"   Error: {jwt_result['error']}")
			print(f"   Status Code: {jwt_result.get('status_code', 'N/A')}")
			if jwt_result.get('response_text'):
				print(f"   Response: {jwt_result['response_text'][:200]}")
	else:
		print(f"   ⚠️  Skipped - Client ID or Secret missing")
		results["jwt_test"] = {"success": False, "error": "Credentials missing"}
	
	# 3. Test Password Flow Authentication
	print(f"\n🔒 Step 3: Testing Password Flow Authentication...")
	if client_id and client_secret and username and password and extension:
		password_result = test_password_auth(client_id, client_secret, username, password, extension)
		results["password_test"] = password_result
		
		if password_result["success"]:
			print(f"   ✅ Password Authentication: SUCCESS")
			print(f"   Access Token: {password_result['access_token'][:30]}...")
			results["recommendations"].append("✅ Password auth works! You can use this method.")
		else:
			print(f"   ❌ Password Authentication: FAILED")
			print(f"   Error: {password_result['error']}")
			print(f"   Status Code: {password_result.get('status_code', 'N/A')}")
			if password_result.get('response_text'):
				print(f"   Response: {password_result['response_text'][:200]}")
	else:
		print(f"   ⚠️  Skipped - Username, Password, or Extension missing")
		results["password_test"] = {"success": False, "error": "Credentials missing"}
	
	# 4. Recommendations
	print(f"\n" + "="*70)
	print("💡 RECOMMENDATIONS")
	print("="*70)
	
	if results["jwt_test"].get("success"):
		print("✅ Use JWT Authentication (currently configured)")
		results["success"] = True
		results["message"] = "JWT authentication is working"
	elif results["password_test"].get("success"):
		print("✅ Use Password Flow Authentication")
		print("   Update your code to use authenticate_password() instead of authenticate_jwt()")
		results["success"] = True
		results["message"] = "Password authentication is working"
		results["recommendations"].append("⚠️  Switch code to use Password Flow authentication")
	else:
		print("❌ Both authentication methods failed!")
		print("\n🔧 Troubleshooting Steps:")
		print("1. Check RingCentral App Configuration:")
		print("   - Go to: https://developers.ringcentral.com/my-account/apps")
		print("   - Check app permissions and settings")
		print("   - Ensure app is in Production (not Sandbox)")
		print(f"\n2. For JWT (Client Credentials):")
		print(f"   - App must have 'OAuth 2.0 Credentials Flow' enabled")
		print(f"   - Required scopes: ReadCallRecording, ReadMessages")
		print(f"\n3. For Password Flow:")
		print(f"   - App must have 'Password Flow' enabled in app settings")
		print(f"   - Username format: your RingCentral phone number (e.g., +17203316220)")
		print(f"   - Extension: your extension number (e.g., 3000)")
		print(f"\n4. Common Issues:")
		print(f"   - OAU-153: Invalid credentials")
		print(f"   - OAU-251: Grant type not allowed for this app")
		print(f"   - Check if app is approved and in production mode")
		
		results["success"] = False
		results["message"] = "Both authentication methods failed"
		results["recommendations"].extend([
			"❌ Check RingCentral app configuration",
			"❌ Verify client ID and secret are correct",
			"❌ Ensure app has proper permissions",
			"❌ Contact RingCentral support if app config is locked"
		])
	
	print("\n" + "="*70 + "\n")
	
	return results


def test_jwt_auth(client_id, client_secret, account_id="~"):
	"""Test JWT authentication"""
	try:
		server_url = "https://platform.ringcentral.com"
		
		# Basic auth
		auth_string = f"{client_id}:{client_secret}"
		auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
		
		headers = {
			"Authorization": f"Basic {auth_b64}",
			"Content-Type": "application/x-www-form-urlencoded"
		}
		
		data = {
			"grant_type": "client_credentials",
			"account_id": account_id
		}
		
		response = requests.post(
			f"{server_url}/restapi/oauth/token",
			headers=headers,
			data=data,
			timeout=30
		)
		
		if response.status_code == 200:
			result = response.json()
			return {
				"success": True,
				"access_token": result.get("access_token"),
				"token_type": result.get("token_type"),
				"expires_in": result.get("expires_in"),
				"status_code": 200
			}
		else:
			return {
				"success": False,
				"error": f"HTTP {response.status_code}",
				"status_code": response.status_code,
				"response_text": response.text
			}
	except Exception as e:
		return {
			"success": False,
			"error": str(e)
		}


def test_password_auth(client_id, client_secret, username, password, extension):
	"""Test Password Flow authentication"""
	try:
		server_url = "https://platform.ringcentral.com"
		
		# Basic auth
		auth_string = f"{client_id}:{client_secret}"
		auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
		
		headers = {
			"Authorization": f"Basic {auth_b64}",
			"Content-Type": "application/x-www-form-urlencoded"
		}
		
		data = {
			"grant_type": "password",
			"username": username,
			"password": password,
			"extension": extension
		}
		
		response = requests.post(
			f"{server_url}/restapi/oauth/token",
			headers=headers,
			data=data,
			timeout=30
		)
		
		if response.status_code == 200:
			result = response.json()
			return {
				"success": True,
				"access_token": result.get("access_token"),
				"token_type": result.get("token_type"),
				"expires_in": result.get("expires_in"),
				"status_code": 200
			}
		else:
			return {
				"success": False,
				"error": f"HTTP {response.status_code}",
				"status_code": response.status_code,
				"response_text": response.text
			}
	except Exception as e:
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def check_ringcentral_app_permissions():
	"""
	Check what the RingCentral app actually allows
	"""
	print("\n📱 RINGCENTRAL APP PERMISSION CHECK\n")
	print("This requires a valid access token. Run test_ringcentral_auth() first.")
	
	# TODO: Implement API call to check app permissions
	# Requires successful auth first
	
	return {
		"message": "Run test_ringcentral_auth() first to get access token"
	}

