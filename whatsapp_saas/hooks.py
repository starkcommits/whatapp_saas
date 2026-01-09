app_name = "whatsapp_saas"
app_title = "WhatsApp SaaS"
app_publisher = "Frappe Baileys"
app_description = "WhatsApp SaaS Management"
app_email = "admin@example.com"
app_license = "mit"

# Overriding Methods
# ------------------------------
# All WhatsApp API endpoints whitelisted with short names (using underscores)
override_whitelisted_methods = {
	# Onboarding & Account Management
	"onboard": "whatsapp_saas.api.api.signup",
	"whatsapp.webhook": "whatsapp_saas.api.api.webhook",
	
	# Instance Management
	"instance_create": "whatsapp_saas.api.endpoints.instance_create",
	"instance_list": "whatsapp_saas.api.endpoints.instance_list",
	"instance_get": "whatsapp_saas.api.endpoints.instance_get",
	"instance_qr": "whatsapp_saas.api.endpoints.instance_qr",
	"instance_status": "whatsapp_saas.api.endpoints.instance_status",
	"instance_delete": "whatsapp_saas.api.endpoints.instance_delete",
	"instance_logout": "whatsapp_saas.api.endpoints.instance_logout",
	
	# Core Messaging
	"send_text": "whatsapp_saas.api.endpoints.send_text",
	"send_media": "whatsapp_saas.api.endpoints.send_media",
	"send_location": "whatsapp_saas.api.endpoints.send_location",
	"send_reaction": "whatsapp_saas.api.endpoints.send_reaction",
	"message_delete": "whatsapp_saas.api.endpoints.delete_message",
	
	# Enhanced Messaging
	"send_reply": "whatsapp_saas.api.endpoints.send_reply",
	"send_mention": "whatsapp_saas.api.endpoints.send_mention",
	"message_forward": "whatsapp_saas.api.endpoints.forward_message",
	"message_edit": "whatsapp_saas.api.endpoints.edit_message",
	"message_pin": "whatsapp_saas.api.endpoints.pin_message",
	"message_unpin": "whatsapp_saas.api.endpoints.unpin_message",
	"send_viewonce": "whatsapp_saas.api.endpoints.send_viewonce",
	"send_poll": "whatsapp_saas.api.endpoints.send_poll",
	
	# Media Operations
	"media_download": "whatsapp_saas.api.endpoints.download_media",
	"media_thumbnail": "whatsapp_saas.api.endpoints.generate_thumbnail",
	"media_optimize": "whatsapp_saas.api.endpoints.optimize_image",
	
	# Chat Management
	"chat_archive": "whatsapp_saas.api.endpoints.archive_chat",
	"chat_mute": "whatsapp_saas.api.endpoints.mute_chat",
	"chat_read": "whatsapp_saas.api.endpoints.mark_read",
	"chat_pin": "whatsapp_saas.api.endpoints.pin_chat",
	"chat_delete": "whatsapp_saas.api.endpoints.delete_chat",
	"chat_star": "whatsapp_saas.api.endpoints.star_message",
	"chat_disappearing": "whatsapp_saas.api.endpoints.set_disappearing",
	"chat_history": "whatsapp_saas.api.endpoints.chat_history",
	
	# Presence & Status
	"presence_update": "whatsapp_saas.api.endpoints.update_presence",
	"presence_typing": "whatsapp_saas.api.endpoints.set_typing",
	"presence_online": "whatsapp_saas.api.endpoints.set_online",
	
	# Profile Management
	"profile_name": "whatsapp_saas.api.endpoints.update_name",
	"profile_status": "whatsapp_saas.api.endpoints.update_status",
	"profile_picture_update": "whatsapp_saas.api.endpoints.update_picture",
	"profile_picture_get": "whatsapp_saas.api.endpoints.get_picture",
	
	# Privacy Settings
	"privacy_block": "whatsapp_saas.api.endpoints.block_user",
	"privacy_unblock": "whatsapp_saas.api.endpoints.unblock_user",
	"privacy_blocklist": "whatsapp_saas.api.endpoints.get_blocklist",
	"privacy_update": "whatsapp_saas.api.endpoints.update_privacy",
	"privacy_get": "whatsapp_saas.api.endpoints.get_privacy",
	
	# Broadcast & Stories
	"broadcast_send": "whatsapp_saas.api.endpoints.send_broadcast",
	"status_send": "whatsapp_saas.api.endpoints.send_status",
	
	# Group Management
	"group_create": "whatsapp_saas.api.endpoints.create_group",
	"group_list": "whatsapp_saas.api.endpoints.list_groups",
	"group_get": "whatsapp_saas.api.endpoints.get_group",
	"group_subject": "whatsapp_saas.api.endpoints.update_group_subject",
	"group_description": "whatsapp_saas.api.endpoints.update_group_description",
	"group_participants": "whatsapp_saas.api.endpoints.group_participants",
	"group_leave": "whatsapp_saas.api.endpoints.leave_group",
	"group_invite": "whatsapp_saas.api.endpoints.get_invite_code",
	
	# Utilities
	"utils_check": "whatsapp_saas.api.endpoints.check_number",
	"utils_validate": "whatsapp_saas.api.endpoints.validate_jid",
	"utils_format": "whatsapp_saas.api.endpoints.format_number",
	"utils_device": "whatsapp_saas.api.endpoints.device_info",
	
	# Advanced Features
	"advanced_link": "whatsapp_saas.api.endpoints.send_link_preview",
	"advanced_sticker": "whatsapp_saas.api.endpoints.send_sticker",
	"advanced_search": "whatsapp_saas.api.endpoints.search_messages",
	"advanced_export": "whatsapp_saas.api.endpoints.export_chat",
	
	# Health & Monitoring
	"health": "whatsapp_saas.api.endpoints.health_check",
	"messages_get": "whatsapp_saas.api.endpoints.get_messages",
	
	# Template & Buttons
	"send_buttons": "whatsapp_saas.api.endpoints.send_template_buttons",
}
