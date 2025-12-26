"""
RingCentral Webhook API Endpoints for CRM
Receives webhook data from Pabbly Connect
"""

import frappe
import json
from typing import Dict, Any


@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_crm_payload(**kwargs) -> Dict[str, Any]:
	"""
	Custom endpoint to receive RingCentral webhooks for CRM
	URL: /api/method/crm.api.ringcentral_webhook.create_crm_payload
	
	This endpoint properly handles the raw_payload JSON from Pabbly
	
	Args:
		**kwargs: Webhook data from Pabbly:
			- session_id: RingCentral session ID
			- uuid: RingCentral UUID
			- extension_id: Extension ID
			- caller_number: Caller phone number
			- called_number: Called phone number
			- caller_name: Caller name
			- call_direction: Inbound/Outbound
			- raw_payload: Body Parties JSON (string or object)
			
	Returns:
		Dict with success status and created payload name
	"""
	try:
		# Extract raw_payload and convert to string if needed
		raw_payload = kwargs.get("raw_payload")
		
		if raw_payload:
			# If it's already a dict/list, convert to JSON string
			if isinstance(raw_payload, (dict, list)):
				raw_payload_str = json.dumps(raw_payload)
			else:
				raw_payload_str = raw_payload
		else:
			raw_payload_str = ""
		
		# Create the RingCentral CRM Payload document
		payload_doc = frappe.get_doc({
			"doctype": "RingCentral CRM Payload",
			"session_id": kwargs.get("session_id", ""),
			"uuid": kwargs.get("uuid", ""),
			"extension_id": kwargs.get("extension_id", ""),
			"caller_number": kwargs.get("caller_number", ""),
			"called_number": kwargs.get("called_number", ""),
			"caller_name": kwargs.get("caller_name", ""),
			"call_direction": kwargs.get("call_direction", ""),
			"raw_payload": raw_payload_str,
			"processing_status": "Pending",
			"processed": 0
		})
		
		payload_doc.insert(ignore_permissions=True)
		frappe.db.commit()
		
		return {
			"success": True,
			"message": "Payload created successfully",
			"name": payload_doc.name,
			"session_id": payload_doc.session_id
		}
		
	except Exception as e:
		frappe.log_error(
			title="RingCentral CRM Webhook Error",
			message=f"Error: {str(e)}\n\nKwargs: {json.dumps(kwargs, indent=2, default=str)}"
		)
		frappe.db.rollback()
		
		return {
			"success": False,
			"error": str(e),
			"message": "Failed to create payload"
		}


@frappe.whitelist(allow_guest=False, methods=["POST"])
def process_pending_payloads() -> Dict[str, Any]:
	"""
	Manual endpoint to process all pending payloads
	URL: /api/method/crm.api.ringcentral_webhook.process_pending_payloads
	
	Useful for reprocessing failed payloads or batch processing
	
	Returns:
		Dict with processing results
	"""
	try:
		pending_payloads = frappe.get_all(
			"RingCentral CRM Payload",
			filters={"processing_status": "Pending", "processed": 0},
			fields=["name"],
			limit=100
		)
		
		results = {
			"total": len(pending_payloads),
			"processed": 0,
			"failed": 0,
			"errors": []
		}
		
		for payload in pending_payloads:
			try:
				payload_doc = frappe.get_doc("RingCentral CRM Payload", payload.name)
				# The after_insert hook will handle processing
				# Or manually call process function here if needed
				from crm.fcrm.doctype.ringcentral_crm_payload.ringcentral_crm_payload import process_crm_payload
				process_crm_payload(payload.name)
				results["processed"] += 1
			except Exception as e:
				results["failed"] += 1
				results["errors"].append({
					"payload": payload.name,
					"error": str(e)
				})
		
		return {
			"success": True,
			"results": results
		}
		
	except Exception as e:
		frappe.log_error(
			title="Process Pending Payloads Error",
			message=str(e)
		)
		return {
			"success": False,
			"error": str(e)
		}

