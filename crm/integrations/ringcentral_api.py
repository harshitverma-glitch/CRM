import frappe
from frappe.utils import now
import uuid


@frappe.whitelist()
def create_manual_call_log(phone_number, contact_name=None):
	"""
	Create a manual call log when user clicks the RingCentral call button
	
	Args:
		phone_number: Phone number being called
		contact_name: Name of contact (if available)
		
	Returns:
		Name of created call log
	"""
	try:
		# Generate unique ID for manual call
		call_id = f"manual-{uuid.uuid4().hex[:12]}"
		
		# Try to find associated lead or contact
		reference_doctype = None
		reference_docname = None
		
		# Check for existing lead with this phone number
		from crm.integrations.ringcentral_utils import normalize_phone_number, find_lead_by_phone
		
		normalized_phone = normalize_phone_number(phone_number)
		lead = find_lead_by_phone(normalized_phone)
		
		if lead:
			reference_doctype = "CRM Lead"
			reference_docname = lead.get("name")
		
		# Get current user's full name for caller name
		current_user = frappe.session.user
		caller_full_name = frappe.get_value("User", current_user, "full_name") or current_user
		
		# For receiver, use the contact name being called if provided
		receiver_name = contact_name or phone_number
		
		# Create call log
		call_log = frappe.get_doc({
			"doctype": "CRM Call Log",
			"id": call_id,
			"from": current_user,  # Current user email making the call
			"to": phone_number,
			"caller": current_user,  # Link to User for outgoing calls
			"caller_name": caller_full_name,  # CRM user's full name
			"receiver": None,  # Not a User link for external calls
			"type": "Outgoing",
			"status": "Initiated",
			"duration": 0,
			"medium": "RingCentral",
			"telephony_medium": "Manual",
			"start_time": now(),
			"reference_doctype": reference_doctype,
			"reference_docname": reference_docname,
		})
		
		call_log.insert(ignore_permissions=True)
		frappe.db.commit()
		
		return {
			"success": True,
			"call_log_id": call_log.name,
			"message": "Call log created successfully"
		}
		
	except Exception as e:
		frappe.log_error(title="RingCentral Manual Call Log Error", message=str(e))
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def get_contact_by_phone(number):
	"""
	Get contact/lead information by phone number
	
	Args:
		number: Phone number to search for
		
	Returns:
		Dict with contact/lead information
	"""
	try:
		# Use existing function to get contact by phone
		from crm.integrations.api import get_contact_by_phone_number
		
		result = get_contact_by_phone_number(number)
		return result
		
	except Exception as e:
		frappe.log_error(title="RingCentral Get Contact Error", message=str(e))
		return {
			"mobile_no": number,
			"full_name": "Unknown"
		}

