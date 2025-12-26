#!/usr/bin/env python3
"""
Quick one-liner commands to test and fix RingCentral recordings
Run from bench directory
"""

# TEST: Check all recordings status
# bench execute "crm.scripts.quick_test.test"

# FIX: Convert private files to public  
# bench execute "crm.scripts.quick_test.fix"

# CHECK: Check specific call log
# bench execute "crm.scripts.quick_test.check" --kwargs "{'call_log':'CL-00001'}"

import frappe


def test():
	"""Quick test - shows status of all recordings"""
	print("\n" + "="*60)
	print("🎵 RECORDING STATUS CHECK")
	print("="*60 + "\n")
	
	# Count files
	total = frappe.db.count("File", {"attached_to_doctype": "CRM Call Log"})
	private = frappe.db.count("File", {"attached_to_doctype": "CRM Call Log", "is_private": 1})
	public = frappe.db.count("File", {"attached_to_doctype": "CRM Call Log", "is_private": 0})
	
	print(f"Total recording files: {total}")
	print(f"  - Public (playable): {public} ✅")
	print(f"  - Private (need fix): {private} {'⚠️' if private > 0 else ''}")
	
	if private > 0:
		print(f"\n⚠️  You have {private} private file(s) that won't play!")
		print("   Run: bench execute 'crm.scripts.quick_test.fix'")
	else:
		print("\n✅ All recordings are public - should work!")
	
	# Show recent recordings
	recent = frappe.get_all(
		"File",
		filters={"attached_to_doctype": "CRM Call Log"},
		fields=["name", "file_name", "file_url", "is_private", "creation"],
		order_by="creation desc",
		limit=3
	)
	
	if recent:
		print(f"\nRecent recordings:")
		for f in recent:
			status = "🔒 Private" if f.is_private else "✅ Public"
			print(f"  {status} - {f.file_name}")
			print(f"           {f.file_url}")
	
	print("\n" + "="*60 + "\n")


def fix():
	"""Quick fix - convert private to public"""
	print("\n🔧 Converting private recordings to public...\n")
	
	from crm.api.fix_recording_files import convert_private_recordings_to_public
	result = convert_private_recordings_to_public()
	
	if result['success']:
		print(f"✅ Success!")
		print(f"   Converted: {result['converted']}")
		print(f"   Failed: {result['failed']}")
		print(f"   Total: {result['total']}")
		
		if result['errors']:
			print(f"\n⚠️  Errors:")
			for error in result['errors']:
				print(f"   {error}")
	else:
		print(f"❌ Failed: {result['message']}")
	
	print()


def check(call_log=None):
	"""Check specific call log recording"""
	if not call_log:
		print("❌ Provide call_log name: --kwargs \"{'call_log':'CL-00001'}\"")
		return
	
	print(f"\n🔍 Checking call log: {call_log}\n")
	
	from crm.api.fix_recording_files import check_recording_file_status
	status = check_recording_file_status(call_log)
	
	if status['success']:
		info = status['file_info']
		print(f"✅ Found recording file")
		print(f"   File Name: {info['file_name']}")
		print(f"   File URL: {info['file_url']}")
		print(f"   Is Private: {'Yes 🔒' if info['is_private'] else 'No ✅'}")
		print(f"   File Size: {info['file_size']} bytes")
		print(f"   Physical Path: {info['physical_path']}")
		print(f"   File Exists: {'Yes ✅' if info['file_exists'] else 'No ❌'}")
		
		if info['is_private']:
			print(f"\n⚠️  File is PRIVATE - won't play!")
			print(f"   Run: bench execute 'crm.scripts.quick_test.fix'")
		elif not info['file_exists']:
			print(f"\n⚠️  File missing from disk!")
		else:
			print(f"\n✅ File looks good - should play!")
	else:
		print(f"❌ {status['message']}")
	
	print()


# For direct execution
if __name__ == "__main__":
	test()

