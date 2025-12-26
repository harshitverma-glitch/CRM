"""
RingCentral Integration Utilities for CRM
Handles parsing and processing of RingCentral webhook payloads
"""

import frappe
import json
import re
from typing import Dict, Any, Optional


def parse_ringcentral_payload(raw_payload: str) -> Dict[str, Any]:
	"""
	Parse RingCentral JSON payload and extract call details
	
	Args:
		raw_payload: JSON string or dict from RingCentral webhook (Body Parties array)
		
	Returns:
		dict with extracted fields: session_id, caller_number, 
		called_number, direction, duration, status, timestamps, etc.
	"""
	try:
		# Handle if already dict
		if isinstance(raw_payload, str):
			payload_data = json.loads(raw_payload)
		else:
			payload_data = raw_payload
			
		# RingCentral sends an array of parties - get the first one
		if isinstance(payload_data, list) and len(payload_data) > 0:
			party = payload_data[0]
		elif isinstance(payload_data, dict):
			party = payload_data
		else:
			frappe.throw("Invalid payload format")
			
		# Extract call details
		call_data = {
			"party_id": party.get("id", ""),
			"account_id": party.get("accountId", ""),
			"extension_id": party.get("extensionId", ""),
			"direction": party.get("direction", ""),
			"caller_number": party.get("from", {}).get("phoneNumber", ""),
			"caller_name": party.get("from", {}).get("name", ""),
			"caller_extension_id": party.get("from", {}).get("extensionId", ""),
			"caller_device_id": party.get("from", {}).get("deviceId", ""),
			"called_number": party.get("to", {}).get("phoneNumber", ""),
			"called_name": party.get("to", {}).get("name", ""),
			"called_extension_id": party.get("to", {}).get("extensionId", ""),
			"status_code": party.get("status", {}).get("code", ""),
			"status_reason": party.get("status", {}).get("reason", ""),
			"status_rcc": party.get("status", {}).get("rcc", False),
			"missed_call": party.get("missedCall", False),
			"stand_alone": party.get("standAlone", False),
			"muted": party.get("muted", False),
			"park": party.get("park", []),
			# Extract voicemail/message data
			"message": party.get("message", {}),
			"vm_duration": party.get("message", {}).get("vmDuration", 0) if party.get("message") else 0,
			"message_id": party.get("message", {}).get("messageId", "") if party.get("message") else "",
			# Extract recording data
			"recordings": party.get("recordings", []),
			"recording_id": party.get("recordings", [{}])[0].get("id", "") if party.get("recordings") else "",
			"recording_mode": party.get("recordings", [{}])[0].get("mode", "") if party.get("recordings") else "",
		}
		
		return call_data
		
	except json.JSONDecodeError as e:
		frappe.log_error(
			title="RingCentral Payload Parse Error",
			message=f"Failed to parse JSON: {str(e)}\n\nPayload: {raw_payload[:500]}"
		)
		frappe.throw(f"Invalid JSON payload: {str(e)}")
	except Exception as e:
		frappe.log_error(
			title="RingCentral Payload Parse Error",
			message=f"Error: {str(e)}\n\nPayload: {raw_payload[:500] if isinstance(raw_payload, str) else str(raw_payload)[:500]}"
		)
		frappe.throw(f"Error parsing payload: {str(e)}")


def normalize_phone_number(phone: str) -> str:
	"""
	Normalize phone number for matching
	Removes +, spaces, dashes, parentheses
	
	Args:
		phone: Raw phone number string
		
	Returns:
		Normalized phone string (digits only)
	"""
	if not phone:
		return ""
	
	# Remove all non-digit characters
	normalized = re.sub(r'[^\d]', '', phone)
	
	# Remove leading 1 for US numbers if present (optional)
	# if normalized.startswith('1') and len(normalized) == 11:
	#     normalized = normalized[1:]
	
	return normalized


def format_duration(seconds: int) -> str:
	"""
	Format duration in human readable format
	
	Args:
		seconds: Duration in seconds (int)
		
	Returns:
		Formatted string like "2m 30s" or "1h 15m 30s"
	"""
	if not seconds or seconds == 0:
		return "0s"
		
	hours = seconds // 3600
	minutes = (seconds % 3600) // 60
	secs = seconds % 60
	
	parts = []
	if hours > 0:
		parts.append(f"{hours}h")
	if minutes > 0:
		parts.append(f"{minutes}m")
	if secs > 0 or not parts:  # Always show seconds if no other parts
		parts.append(f"{secs}s")
		
	return " ".join(parts)


def get_call_status_mapping(ringcentral_status: str) -> str:
	"""
	Map RingCentral call status to CRM Call Log status options
	
	Args:
		ringcentral_status: Status from RingCentral (e.g., "Disconnected", "Connected")
		
	Returns:
		One of: Initiated, Ringing, In Progress, Completed, Failed, Busy, No Answer, Queued, Canceled
	"""
	status_map = {
		"Disconnected": "Completed",
		"Connected": "In Progress",
		"Gone": "No Answer",
		"Busy": "Busy",
		"NoAnswer": "No Answer",
		"Failed": "Failed",
		"Rejected": "Canceled",
		"Replied": "Completed",
		"Received": "Completed",
		"FaxOnDemand": "Completed",
		"VoiceMail": "No Answer",
		"Setup": "Initiated",
		"Proceeding": "Ringing",
	}
	
	return status_map.get(ringcentral_status, "Completed")


def get_call_type(direction: str) -> str:
	"""
	Map RingCentral direction to CRM Call Log type
	
	Args:
		direction: "Inbound" or "Outbound"
		
	Returns:
		"Incoming" or "Outgoing"
	"""
	if direction and direction.lower() == "inbound":
		return "Incoming"
	elif direction and direction.lower() == "outbound":
		return "Outgoing"
	else:
		return "Incoming"  # Default


def find_lead_by_phone(phone_number: str) -> Optional[Dict[str, Any]]:
	"""
	Find an existing CRM Lead by phone number
	
	Args:
		phone_number: Phone number to search for (will be normalized)
		
	Returns:
		Dict with lead details if found, None otherwise
	"""
	if not phone_number:
		return None
		
	normalized = normalize_phone_number(phone_number)
	
	if not normalized:
		return None
	
	# Try to find by mobile_no field
	lead = frappe.db.get_value(
		"CRM Lead",
		{"mobile_no": ["like", f"%{normalized}%"]},
		["name", "lead_name", "mobile_no", "email", "status"],
		as_dict=True
	)
	
	if lead:
		return lead
	
	# Try alternate phone fields if available
	# You can add more phone field searches here if needed
	
	return None


def create_lead_from_call(call_data: Dict[str, Any], caller_number: str) -> Dict[str, Any]:
	"""
	Create a new CRM Lead from call data
	
	Args:
		call_data: Parsed call data from RingCentral
		caller_number: Normalized caller phone number
		
	Returns:
		Dict with created lead details
	"""
	caller_name = call_data.get("caller_name") or "Unknown Caller"
	
	# Remove company prefix if present (e.g., "Zip Cushions Sales - DAMATO LARITZA" -> "DAMATO LARITZA")
	if " - " in caller_name:
		# Take the part after the last dash (usually the person's name)
		caller_name = caller_name.split(" - ")[-1].strip()
	
	# Parse first and last name from caller name
	name_parts = caller_name.split(" ", 1)
	first_name = name_parts[0] if name_parts else caller_name
	last_name = name_parts[1] if len(name_parts) > 1 else ""
	
	lead = frappe.get_doc({
		"doctype": "CRM Lead",
		"first_name": first_name,
		"last_name": last_name,
		"mobile_no": caller_number,
		"source": "RingCentral",
		"status": "New",  # Default status for new leads from calls
		"lead_owner": None,  # Can be set based on extension routing
	})
	
	lead.insert(ignore_permissions=True)
	frappe.db.commit()
	
	return {
		"name": lead.name,
		"lead_name": f"{first_name} {last_name}".strip(),
		"mobile_no": lead.mobile_no
	}


def create_call_log(call_data: Dict[str, Any], lead_name: str, session_id: str) -> str:
	"""
	Create a CRM Call Log entry
	
	Args:
		call_data: Parsed call data from RingCentral
		lead_name: Name of the linked CRM Lead
		session_id: RingCentral session ID
		
	Returns:
		Name of created call log
	"""
	from frappe.utils import now, add_to_date
	
	# Get duration (use vmDuration if available, otherwise 0)
	# Duration will be fetched via background job from RingCentral API
	duration_seconds = int(call_data.get("vm_duration", 0))
	
	# Set start time to current time (will be updated by background job)
	start_time = now()
	
	# Calculate end time if we have duration
	end_time = None
	if duration_seconds > 0:
		end_time = add_to_date(start_time, seconds=duration_seconds)
	
	# Build recording URL
	recording_url = None
	recording_id = call_data.get("recording_id", "")
	message_id = call_data.get("message_id", "")
	account_id = call_data.get("account_id", "")
	extension_id = call_data.get("extension_id", "")
	
	# Option 1: Direct recording URL (if recording ID exists)
	if recording_id and account_id:
		recording_url = f"https://platform.ringcentral.com/restapi/v1.0/account/{account_id}/recording/{recording_id}/content"
	
	# Option 2: Voicemail message - Use RingCentral App deep link
	elif message_id and extension_id:
		# Deep link to voicemail in RingCentral app (most reliable)
		recording_url = f"https://app.ringcentral.com/messages/{message_id}"
	
	call_log = frappe.get_doc({
		"doctype": "CRM Call Log",
		"id": call_data.get("party_id") or session_id,
		"from": call_data.get("caller_number", ""),
		"to": call_data.get("called_number", ""),
		"caller_name": call_data.get("caller_name", ""),  # Text field for caller name
		"type": get_call_type(call_data.get("direction", "")),
		"status": get_call_status_mapping(call_data.get("status_code", "")),
		"duration": duration_seconds,  # Duration in seconds (integer)
		"start_time": start_time,
		"end_time": end_time,
		"recording_url": recording_url,  # RingCentral recording URL
		"medium": "RingCentral",
		"telephony_medium": "",  # Leave blank (RingCentral not in allowed values)
		"reference_doctype": "CRM Lead",
		"reference_docname": lead_name,
	})
	
	call_log.insert(ignore_permissions=True)
	frappe.db.commit()
	
	return call_log.name

