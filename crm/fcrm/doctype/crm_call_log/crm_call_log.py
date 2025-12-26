# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from crm.integrations.api import get_contact_by_phone_number
from crm.utils import seconds_to_duration


class CRMCallLog(Document):
	def after_insert(self):
		"""Fetch call duration from RingCentral API if this is a RingCentral call"""
		# Only fetch duration for RingCentral calls
		if self.medium == "RingCentral" and self.id:
			# Enqueue background job with 10 second delay to allow call to complete
			frappe.enqueue(
				update_call_duration_from_ringcentral,
				queue='default',
				timeout=300,
				call_log_name=self.name,
				session_id=self.id,
				enqueue_after_commit=True,
				at_front=False,
				now=False
			)
		
		# Sync to Unified Call Log
		self.sync_to_unified_call_log()
	
	def on_update(self):
		"""Sync to Unified Call Log on update"""
		self.sync_to_unified_call_log()
	
	def sync_to_unified_call_log(self):
		"""Sync this call log to Unified Call Log in ERPNext"""
		try:
			# Check if erpnext is installed
			if not frappe.db.exists("DocType", "Unified Call Log"):
				return
			
			frappe.enqueue(
				'erpnext.telephony.doctype.unified_call_log.unified_call_log.sync_crm_call_log',
				queue='default',
				timeout=300,
				crm_call_log_name=self.name,
				enqueue_after_commit=True,
				now=False
			)
		except Exception as e:
			# Don't fail the main operation if sync fails
			frappe.log_error(
				title=f"Failed to sync CRM Call Log {self.name} to Unified Call Log",
				message=str(e)
			)
	
	@staticmethod
	def default_list_data():
		columns = [
			{
				"label": "Caller",
				"type": "Link",
				"key": "caller",
				"options": "User",
				"width": "9rem",
			},
			{
				"label": "Receiver",
				"type": "Link",
				"key": "receiver",
				"options": "User",
				"width": "9rem",
			},
			{
				"label": "Type",
				"type": "Select",
				"key": "type",
				"width": "9rem",
			},
			{
				"label": "Status",
				"type": "Select",
				"key": "status",
				"width": "9rem",
			},
			{
				"label": "Duration",
				"type": "Duration",
				"key": "duration",
				"width": "6rem",
			},
			{
				"label": "From (number)",
				"type": "Data",
				"key": "from",
				"width": "9rem",
			},
			{
				"label": "To (number)",
				"type": "Data",
				"key": "to",
				"width": "9rem",
			},
			{
				"label": "Created On",
				"type": "Datetime",
				"key": "creation",
				"width": "8rem",
			},
		]
		rows = [
			"name",
			"caller",
			"receiver",
			"type",
			"status",
			"duration",
			"from",
			"to",
			"note",
			"recording_url",
			"reference_doctype",
			"reference_docname",
			"creation",
		]
		return {"columns": columns, "rows": rows}

	def parse_list_data(calls):
		return [parse_call_log(call) for call in calls] if calls else []

	def has_link(self, doctype, name):
		for link in self.links:
			if link.link_doctype == doctype and link.link_name == name:
				return True

	def link_with_reference_doc(self, reference_doctype, reference_name):
		if self.has_link(reference_doctype, reference_name):
			return

		self.append("links", {"link_doctype": reference_doctype, "link_name": reference_name})


def parse_call_log(call):
	call["show_recording"] = False
	call["_duration"] = seconds_to_duration(call.get("duration"))
	if call.get("type") == "Incoming":
		call["activity_type"] = "incoming_call"
		contact = get_contact_by_phone_number(call.get("from"))
		receiver = (
			frappe.db.get_values("User", call.get("receiver"), ["full_name", "user_image"])[0]
			if call.get("receiver")
			else [None, None]
		)
		call["_caller"] = {
			"label": contact.get("full_name", "Unknown"),
			"image": contact.get("image"),
		}
		call["_receiver"] = {
			"label": receiver[0],
			"image": receiver[1],
		}
	elif call.get("type") == "Outgoing":
		call["activity_type"] = "outgoing_call"
		contact = get_contact_by_phone_number(call.get("to"))
		caller = (
			frappe.db.get_values("User", call.get("caller"), ["full_name", "user_image"])[0]
			if call.get("caller")
			else [None, None]
		)
		call["_caller"] = {
			"label": caller[0],
			"image": caller[1],
		}
		call["_receiver"] = {
			"label": contact.get("full_name", "Unknown"),
			"image": contact.get("image"),
		}

	return call


@frappe.whitelist()
def get_call_log(name):
	call = frappe.get_cached_doc(
		"CRM Call Log",
		name,
		fields=[
			"name",
			"caller",
			"receiver",
			"duration",
			"type",
			"status",
			"from",
			"to",
			"note",
			"recording_url",
			"reference_doctype",
			"reference_docname",
			"creation",
		],
	).as_dict()

	call = parse_call_log(call)

	notes = []
	tasks = []

	if call.get("note"):
		note = frappe.get_cached_doc("FCRM Note", call.get("note")).as_dict()
		notes.append(note)

	if call.get("reference_doctype") and call.get("reference_docname"):
		if call.get("reference_doctype") == "CRM Lead":
			call["_lead"] = call.get("reference_docname")
		elif call.get("reference_doctype") == "CRM Deal":
			call["_deal"] = call.get("reference_docname")

	if call.get("links"):
		for link in call.get("links"):
			if link.get("link_doctype") == "CRM Task":
				task = frappe.get_cached_doc("CRM Task", link.get("link_name")).as_dict()
				tasks.append(task)
			elif link.get("link_doctype") == "FCRM Note":
				note = frappe.get_cached_doc("FCRM Note", link.get("link_name")).as_dict()
				notes.append(note)
			elif link.get("link_doctype") == "CRM Lead":
				call["_lead"] = link.get("link_name")
			elif link.get("link_doctype") == "CRM Deal":
				call["_deal"] = link.get("link_name")

	call["_tasks"] = tasks
	call["_notes"] = notes
	return call


@frappe.whitelist()
def create_lead_from_call_log(call_log, lead_details=None):
	lead = frappe.new_doc("CRM Lead")
	lead_details = frappe.parse_json(lead_details or "{}")

	if not lead_details.get("lead_owner"):
		lead_details["lead_owner"] = frappe.session.user
	if not lead_details.get("mobile_no"):
		lead_details["mobile_no"] = call_log.get("from") or ""
	if not lead_details.get("first_name"):
		lead_details["first_name"] = "Lead from call " + (
			lead_details.get("mobile_no") or call_log.get("name")
		)

	lead.update(lead_details)
	lead.save(ignore_permissions=True)

	# link call log with lead
	call_log = frappe.get_doc("CRM Call Log", call_log.get("name"))
	call_log.link_with_reference_doc("CRM Lead", lead.name)
	call_log.save(ignore_permissions=True)

	return lead.name


def update_call_duration_from_ringcentral(call_log_name: str, session_id: str):
	"""
	Background job to fetch and update call duration from RingCentral API
	
	Args:
		call_log_name: Name of the CRM Call Log document
		session_id: RingCentral session ID (telephonySessionId)
	"""
	import time
	from crm.integrations.ringcentral_client import RingCentralClient
	from frappe.utils import get_datetime
	
	try:
		# Wait 10 seconds to allow call to complete and appear in RingCentral API
		time.sleep(10)
		
		# Get the call log
		call_log = frappe.get_doc("CRM Call Log", call_log_name)
		
		# Skip if duration already set (manual update)
		if call_log.duration and call_log.duration > 0:
			frappe.logger().info(f"Call log {call_log_name} already has duration, skipping")
			return
		
		# Initialize RingCentral client and authenticate
		client = RingCentralClient()
		if not client.authenticate_jwt():
			frappe.logger().error(f"Failed to authenticate with RingCentral for call log {call_log_name}")
			return
		
		# Fetch call log details from RingCentral
		call_details = client.get_call_log_details(session_id)
		
		if not call_details:
			frappe.logger().info(f"No call details found in RingCentral for session {session_id}")
			return
		
		# Extract duration and timestamps
		duration = call_details.get("duration", 0)
		start_time = call_details.get("startTime")  # ISO 8601 format
		
		# Update call log
		updates = {}
		if duration and duration > 0:
			updates["duration"] = duration
			
		if start_time:
			try:
				# Convert ISO 8601 to datetime
				start_dt = get_datetime(start_time)
				updates["start_time"] = start_dt
				
				# Calculate end time
				if duration:
					from frappe.utils import add_to_date
					end_dt = add_to_date(start_dt, seconds=duration)
					updates["end_time"] = end_dt
			except:
				pass
		
		if updates:
			for field, value in updates.items():
				call_log.db_set(field, value, update_modified=False)
			frappe.db.commit()
			frappe.logger().info(f"✅ Updated call log {call_log_name} with duration: {duration}s")
		else:
			frappe.logger().info(f"No duration data available for call log {call_log_name}")
			
	except Exception as e:
		frappe.log_error(
			title=f"Failed to update call duration for {call_log_name}",
			message=f"Session ID: {session_id}\nError: {str(e)}\n{frappe.get_traceback()}"
		)
