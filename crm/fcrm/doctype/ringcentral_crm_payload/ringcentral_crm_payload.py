# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from crm.integrations.ringcentral_utils import (
	parse_ringcentral_payload,
	normalize_phone_number,
	find_lead_by_phone,
	create_lead_from_call,
	create_call_log
)


class RingCentralCRMPayload(Document):
	def after_insert(self):
		"""Process payload immediately after creation"""
		# Enqueue processing to avoid blocking the webhook response
		frappe.enqueue(
			process_crm_payload,
			queue='default',
			timeout=300,
			payload_name=self.name
		)


def process_crm_payload(payload_name: str):
	"""
	Background job to process CRM payload
	
	Args:
		payload_name: Name of the RingCentral CRM Payload document
	"""
	try:
		# Check if document exists first
		if not frappe.db.exists("RingCentral CRM Payload", payload_name):
			frappe.logger().warning(f"Payload {payload_name} not found, may have been deleted")
			return
		
		payload = frappe.get_doc("RingCentral CRM Payload", payload_name)
		
		# Skip if already processed
		if payload.processed:
			frappe.logger().info(f"Payload {payload_name} already processed, skipping")
			return
		
		# Mark as processing
		payload.db_set('processing_status', 'Processing', update_modified=False)
		frappe.db.commit()
		
		# Parse the raw payload
		if not payload.raw_payload:
			raise Exception("No raw_payload data found")
		
		call_data = parse_ringcentral_payload(payload.raw_payload)
		
		# Get caller phone number
		caller_number = call_data.get('caller_number', '')
		normalized_caller = normalize_phone_number(caller_number)
		
		if not normalized_caller:
			raise Exception("No valid caller number found in payload")
		
		# Search for existing lead by phone
		lead = find_lead_by_phone(normalized_caller)
		
		# Create lead if not found
		if not lead:
			frappe.logger().info(f"No lead found for {normalized_caller}, creating new lead")
			lead = create_lead_from_call(call_data, normalized_caller)
		else:
			frappe.logger().info(f"Found existing lead: {lead['name']} for {normalized_caller}")
		
		# Create CRM Call Log
		call_log_name = create_call_log(
			call_data=call_data,
			lead_name=lead['name'],
			session_id=payload.session_id or payload.uuid
		)
		
		# Update payload record with processing results
		payload.db_set('processed', 1, update_modified=False)
		payload.db_set('processing_status', 'Processed', update_modified=False)
		payload.db_set('processed_at', frappe.utils.now(), update_modified=False)
		payload.db_set('crm_lead_created', lead['name'], update_modified=False)
		payload.db_set('crm_call_log_created', call_log_name, update_modified=False)
		payload.db_set('processing_notes', 
			f"Lead: {lead.get('name', 'N/A')} ({lead.get('lead_name', 'N/A')}), Call Log: {call_log_name}",
			update_modified=False
		)
		
		frappe.db.commit()
		
		frappe.logger().info(f"Successfully processed payload {payload_name}: Lead={lead['name']}, CallLog={call_log_name}")
		
	except Exception as e:
		error_message = str(e)
		frappe.logger().error(f"Error processing CRM payload {payload_name}: {error_message}")
		frappe.log_error(
			title=f"RingCentral CRM Payload Processing Error - {payload_name}",
			message=frappe.get_traceback()
		)
		
		# Update payload with error status (only if it still exists)
		try:
			if frappe.db.exists("RingCentral CRM Payload", payload_name):
				payload = frappe.get_doc("RingCentral CRM Payload", payload_name)
				payload.db_set('processing_status', 'Error', update_modified=False)
				payload.db_set('error_message', error_message[:500], update_modified=False)
				frappe.db.commit()
		except Exception as update_error:
			frappe.logger().error(f"Failed to update error status for {payload_name}: {str(update_error)}")
