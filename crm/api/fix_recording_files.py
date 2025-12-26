"""
Utility to convert private recording files to public for audio playback
"""

import frappe
from frappe.utils.file_manager import save_file
import os


@frappe.whitelist()
def convert_private_recordings_to_public():
	"""
	Convert all private CRM Call Log recording files to public files.
	This allows HTML5 audio player to access them without auth issues.
	
	Returns:
		dict with conversion results
	"""
	try:
		# Find all private files attached to CRM Call Log
		private_files = frappe.get_all(
			"File",
			filters={
				"attached_to_doctype": "CRM Call Log",
				"is_private": 1,
			},
			fields=["name", "file_name", "file_url", "attached_to_name"]
		)
		
		converted_count = 0
		failed_count = 0
		errors = []
		
		for file_info in private_files:
			try:
				# Get full file document
				file_doc = frappe.get_doc("File", file_info.name)
				
				# Change to public
				file_doc.is_private = 0
				
				# Update file_url to public path
				if file_doc.file_url and file_doc.file_url.startswith('/private/'):
					file_doc.file_url = file_doc.file_url.replace('/private/', '/files/')
				
				# Save changes
				file_doc.save(ignore_permissions=True)
				
				# Move physical file from private to public folder
				old_path = file_doc.get_full_path()
				
				if os.path.exists(old_path):
					# Move file
					from frappe.utils import get_files_path
					public_path = os.path.join(get_files_path(), file_doc.file_name)
					
					# Copy file to public location
					import shutil
					shutil.copy2(old_path, public_path)
					
					# Remove old private file
					os.remove(old_path)
				
				converted_count += 1
				frappe.logger().info(f"Converted {file_info.file_name} to public")
				
			except Exception as e:
				failed_count += 1
				error_msg = f"Failed to convert {file_info.file_name}: {str(e)}"
				errors.append(error_msg)
				frappe.log_error(title=f"File Conversion Error: {file_info.name}", message=error_msg)
		
		frappe.db.commit()
		
		return {
			"success": True,
			"converted": converted_count,
			"failed": failed_count,
			"total": len(private_files),
			"errors": errors
		}
		
	except Exception as e:
		frappe.log_error(
			title="Recording File Conversion Error",
			message=frappe.get_traceback()
		)
		return {
			"success": False,
			"message": str(e)
		}


@frappe.whitelist()
def check_recording_file_status(call_log_name: str):
	"""
	Check the status of a recording file for debugging
	
	Args:
		call_log_name: Name of CRM Call Log
		
	Returns:
		dict with file status information
	"""
	try:
		# Get call log
		call_log = frappe.get_doc("CRM Call Log", call_log_name)
		
		# Get file
		file_doc = frappe.db.get_value(
			"File",
			{
				"attached_to_doctype": "CRM Call Log",
				"attached_to_name": call_log_name,
			},
			["name", "file_name", "file_url", "is_private", "file_size", "content_hash"],
			as_dict=True
		)
		
		if not file_doc:
			return {
				"success": False,
				"message": "No file found"
			}
		
		# Check if physical file exists
		full_file = frappe.get_doc("File", file_doc.name)
		file_path = full_file.get_full_path()
		file_exists = os.path.exists(file_path) if file_path else False
		
		return {
			"success": True,
			"call_log_name": call_log_name,
			"recording_url": call_log.recording_url,
			"file_info": {
				"name": file_doc.name,
				"file_name": file_doc.file_name,
				"file_url": file_doc.file_url,
				"is_private": file_doc.is_private,
				"file_size": file_doc.file_size,
				"content_hash": file_doc.content_hash,
				"physical_path": file_path,
				"file_exists": file_exists
			}
		}
		
	except Exception as e:
		frappe.log_error(
			title=f"Check File Status Error: {call_log_name}",
			message=frappe.get_traceback()
		)
		return {
			"success": False,
			"message": str(e)
		}

