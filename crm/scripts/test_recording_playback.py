#!/usr/bin/env python3
"""
Quick test script to verify recording playback is working
Run from bench directory: bench execute crm.scripts.test_recording_playback.test_recordings
"""

import frappe
from frappe import _


def test_recordings():
	"""Test recording files and provide diagnostic information"""
	
	print("\n" + "="*70)
	print("🎵 RECORDING PLAYBACK DIAGNOSTIC TEST")
	print("="*70 + "\n")
	
	# 1. Check for call logs with recordings
	print("📋 Step 1: Finding call logs with recordings...")
	call_logs = frappe.get_all(
		"CRM Call Log",
		filters={"recording_url": ["!=", ""]},
		fields=["name", "recording_url", "creation"],
		order_by="creation desc",
		limit=5
	)
	
	if not call_logs:
		print("❌ No call logs with recordings found.")
		print("   Create a call log with a recording first.\n")
		return
	
	print(f"✅ Found {len(call_logs)} call log(s) with recordings\n")
	
	# 2. Check each recording file
	for i, log in enumerate(call_logs, 1):
		print(f"\n{'='*70}")
		print(f"📞 Call Log #{i}: {log.name}")
		print(f"{'='*70}")
		print(f"   Recording URL: {log.recording_url}")
		
		# Check if file exists in database
		file_doc = frappe.db.get_value(
			"File",
			{
				"attached_to_doctype": "CRM Call Log",
				"attached_to_name": log.name,
			},
			["name", "file_name", "file_url", "is_private", "file_size"],
			as_dict=True
		)
		
		if not file_doc:
			print("   ⚠️  No file document found in ERPNext")
			print(f"   Suggestion: Click 'Load Recording' in the CRM UI for {log.name}")
			continue
		
		print(f"\n   📄 File Document: {file_doc.name}")
		print(f"   📁 File Name: {file_doc.file_name}")
		print(f"   🔗 File URL: {file_doc.file_url}")
		print(f"   🔒 Is Private: {'Yes' if file_doc.is_private else 'No'}")
		print(f"   💾 File Size: {file_doc.file_size} bytes")
		
		# Check physical file
		import os
		full_file_doc = frappe.get_doc("File", file_doc.name)
		file_path = full_file_doc.get_full_path()
		file_exists = os.path.exists(file_path) if file_path else False
		
		print(f"   📂 Physical Path: {file_path}")
		print(f"   ✓ File Exists: {'Yes' if file_exists else 'No'}")
		
		# Assess status
		print("\n   🔍 DIAGNOSIS:")
		if file_doc.is_private:
			print("   ❌ ISSUE FOUND: File is PRIVATE")
			print("   ⚠️  HTML5 audio cannot access private files without auth")
			print("   💡 FIX: Run convert_private_recordings_to_public()")
		elif not file_exists:
			print("   ❌ ISSUE FOUND: Physical file missing from disk")
			print("   💡 FIX: Re-download recording from RingCentral")
		elif file_doc.file_url.startswith('/private/'):
			print("   ❌ ISSUE FOUND: File URL points to /private/ directory")
			print("   💡 FIX: Update file_url to /files/ and move file")
		else:
			print("   ✅ File looks GOOD! Should be playable")
			print(f"   🔗 Test URL: {frappe.utils.get_url()}{file_doc.file_url}")
	
	# 3. Summary and recommendations
	print("\n" + "="*70)
	print("📊 SUMMARY & RECOMMENDATIONS")
	print("="*70)
	
	private_count = frappe.db.count(
		"File",
		{"attached_to_doctype": "CRM Call Log", "is_private": 1}
	)
	public_count = frappe.db.count(
		"File",
		{"attached_to_doctype": "CRM Call Log", "is_private": 0}
	)
	
	print(f"\n   Total recording files:")
	print(f"   - Private: {private_count}")
	print(f"   - Public: {public_count}")
	
	if private_count > 0:
		print("\n   ⚠️  ACTION REQUIRED:")
		print(f"   You have {private_count} private recording file(s)")
		print("   These won't play in the audio player!")
		print("\n   To fix, run in console:")
		print("   >>> from crm.api.fix_recording_files import convert_private_recordings_to_public")
		print("   >>> convert_private_recordings_to_public()")
	else:
		print("\n   ✅ All recordings are public - should work!")
	
	print("\n" + "="*70 + "\n")


def quick_fix():
	"""Quick fix for recording playback issues"""
	print("\n🔧 Running Quick Fix for Recording Playback...\n")
	
	from crm.api.fix_recording_files import convert_private_recordings_to_public
	result = convert_private_recordings_to_public()
	
	if result['success']:
		print(f"✅ Conversion complete!")
		print(f"   Converted: {result['converted']}")
		print(f"   Failed: {result['failed']}")
		print(f"   Total: {result['total']}")
		
		if result['errors']:
			print(f"\n⚠️  Errors encountered:")
			for error in result['errors']:
				print(f"   - {error}")
	else:
		print(f"❌ Conversion failed: {result['message']}")
	
	print("\n")


if __name__ == "__main__":
	# When run directly
	test_recordings()

