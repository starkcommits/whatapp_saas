"""
WhatsApp SaaS API Endpoints
Individual whitelisted methods for all WhatsApp Baileys endpoints
"""
import frappe
import requests
import json
from frappe import _

def _proxy_request(endpoint, method="POST", require_instance=True, **kwargs):
    """Internal helper to proxy requests to Baileys service with auth & limits"""
    try:
        user = frappe.session.user
        if user == 'Guest':
            frappe.throw(_("Authentication required"), frappe.PermissionError)
        
        # Verify customer exists
        # customer_name = frappe.db.get_value("WhatsApp Customer", {"user": user}, "name")
        
        
        # Get instance_id from kwargs or form
        instance_id = kwargs.get('instance_id') or frappe.form_dict.get('instance_id')
            
        # Some endpoints don't require instance_id (like instance_list, instance_create)
        if require_instance:
            if not instance_id:
                frappe.throw(_("instance_id is required"))
            
            customer_name = frappe.db.get_value("WhatsApp Instance", {"instance_id": instance_id}, "whatsapp_customer")
            if not customer_name:
                frappe.throw(_("No WhatsApp Customer linked to this user"))

            # Verify instance ownership
            instance = frappe.get_doc("WhatsApp Instance", {"instance_id": instance_id})
            if not instance or instance.whatsapp_customer != customer_name:
                frappe.throw(_("Unauthorized access to instance"))
            
            subscription = frappe.get_doc("WhatsApp Subscription", instance.subscription)
            if subscription.status != 'Active':
                frappe.throw(_("Subscription not active"))
            
            # Check rate limits
            plan = frappe.get_doc("WhatsApp Plan", subscription.plan)
            from frappe.utils import get_first_day, get_last_day, today
            current_usage = frappe.db.count("WhatsApp Message Log", {
                "subscription": subscription.name,
                "creation": ["between", [get_first_day(today()), get_last_day(today())]]
            })
            
            if current_usage >= plan.max_messages_per_month:
                frappe.throw(_("Monthly message limit reached"))
        
        # Forward to Baileys
        url = f"http://whatsapp-baileys:3000/api/{endpoint}"
        
        # Prepare request data
        data = {k: v for k, v in kwargs.items() if k != 'instance_id'}
        data.update(frappe.form_dict)
        data.pop('cmd', None)
        data.pop('instance_id', None)
        
        files = None
        if frappe.request.files:
            files = {k: (v.filename, v.stream, v.content_type) for k, v in frappe.request.files.items()}
        
        # Store request data for logging
        request_data = json.dumps(data) if not files else str(data)
        
        response = requests.request(
            method=method,
            url=url,
            json=data if not files else None,
            data=data if files else None,
            files=files,
            timeout=60
        )
        
        # Parse response
        response_data = None
        try:
            response_data = response.json()
        except:
            response_data = response.content.decode('utf-8') if response.content else ""
        
        # Log the request with both request and response
        if method in ['POST', 'PUT', 'DELETE'] and require_instance:
            msg_id = "LOG-" + frappe.generate_hash(length=10)
            if isinstance(response_data, dict):
                msg_id = response_data.get('key', {}).get('id') or response_data.get('id') or msg_id
            
            frappe.get_doc({
                "doctype": "WhatsApp Message Log",
                "instance": instance.name,
                "message_id": msg_id,
                "timestamp": frappe.utils.now(),
                "status": "Sent" if response.ok else "Failed",
                "direction": "Outbound",
                "whatsapp_customer": customer_name,
                "subscription": subscription.name,
                "request_data": request_data,
                "response_data": json.dumps(response_data) if isinstance(response_data, dict) else str(response_data)
            }).insert(ignore_permissions=True)
        
        return response_data
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "WhatsApp API Error")
        frappe.throw(str(e))

# Instance Management
@frappe.whitelist(allow_guest=False)
def instance_create(**kwargs):
    """Create new instance - checks max instance limit from plan"""
    frappe.db.savepoint(save_point="instance_create")
    try:
        user = frappe.session.user
        if user == 'Guest':
            frappe.throw(_("Authentication required"), frappe.PermissionError)
        
        # Get customer
        customer_name, current_plan = frappe.db.get_value("WhatsApp Customer", {"user": user}, ["name","current_plan"])
        if not customer_name:
            frappe.throw(_("No WhatsApp Customer linked to this user"))
        
        # # Get active subscription
        # subscriptions = frappe.get_all("WhatsApp Subscription", 
        #     filters={"customer": customer_name, "status": "Active"},
        #     fields=["name", "plan"]
        # )
        
        # if not subscriptions:
        #     frappe.throw(_("No active subscription found"))
        
        # subscription = subscriptions[0]
        plan = frappe.get_doc("WhatsApp Plan", current_plan)
        
        # Check current instance count
        current_instances = frappe.db.count("WhatsApp Instance", {
            "whatsapp_customer": customer_name,
            "status": ["!=", "Deleted"]
        })
        
        if current_instances >= plan.max_instances:
            frappe.throw(_(f"Maximum instance limit reached ({plan.max_instances} instances allowed)"))
        
        subscription = frappe.db.get_value("WhatsApp Subscription", {"plan": plan.name, "customer": customer_name}, "name")
        # Create instance via Baileys
        url = "http://whatsapp-baileys:3000/api/instance/create"
        data = {k: v for k, v in kwargs.items()}
        data.update(frappe.form_dict)
        data.pop('cmd', None)
        
        response = requests.post(url, json=data, timeout=60)
        response_data = response.json()
        
        # Create instance record in Frappe
        if response_data.get('success'):
            frappe.get_doc({
                "doctype": "WhatsApp Instance",
                "instance_name": data.get('name', 'New Instance'),
                "instance_id": response_data.get("data", {}).get('id'),
                "status": "Disconnected",
                "subscription": subscription,
                "whatsapp_customer": customer_name
            }).insert(ignore_permissions=True)
        
        return response_data
        
    except Exception as e:
        frappe.db.rollback(save_point="instance_create")
        frappe.log_error(frappe.get_traceback(), "Instance Create Error")
        frappe.throw(str(e))

@frappe.whitelist(allow_guest=False)
def instance_list(**kwargs):
    """List all instances - doesn't require instance_id"""
    return _proxy_request("instance/list", "GET", require_instance=False, **kwargs)

@frappe.whitelist(allow_guest=False)
def instance_get(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}", "GET", **kwargs)

@frappe.whitelist(allow_guest=False)
def instance_qr(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/qr", "GET", **kwargs)

@frappe.whitelist(allow_guest=False)
def instance_status(**kwargs):
    instance_id = kwargs.get('instance_id')
    response = _proxy_request(f"instance/{instance_id}/status", "GET", **kwargs)
    # Update instance status in Frappe
    try:
        instance = frappe.get_doc("WhatsApp Instance", {"instance_id": instance_id})
        if response.get('success'):
            data = response.get('data', {})
            status = data.get('status', instance.status)
            if status == "connected":
                instance.status = "Connected"
                instance.phone_number = data.get('phoneNumber', instance.phone_number)
                instance.qr_available = False

            elif status == "connecting":
                instance.status = "Connecting"
            elif status == "disconnected" or status == "qr":
                instance.status = "Disconnected"
                instance.qr_available = True
                instance.phone_number = None
            else:
                instance.status = status
                
            instance.save(ignore_permissions=True)
            frappe.db.commit()
            return response
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Instance Status Update Error")

    return {
        "error": "Failed to check instance status"
    }

@frappe.whitelist(allow_guest=False)
def instance_delete(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}", "DELETE", **kwargs)

@frappe.whitelist(allow_guest=False)
def instance_logout(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/logout", "POST", **kwargs)

# Core Messaging
@frappe.whitelist(allow_guest=False)
def send_text(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/send/text", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def send_media(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/send/media", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def send_location(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/send/location", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def send_reaction(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/send/reaction", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def delete_message(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/message", "DELETE", **kwargs)

# Enhanced Messaging
@frappe.whitelist(allow_guest=False)
def send_reply(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/send/reply", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def send_mention(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/send/mention", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def forward_message(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/message/forward", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def edit_message(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/message/edit", "PUT", **kwargs)

@frappe.whitelist(allow_guest=False)
def pin_message(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/message/pin", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def unpin_message(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/message/unpin", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def send_viewonce(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/send/viewonce", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def send_poll(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/send/poll", "POST", **kwargs)

# Media Operations
@frappe.whitelist(allow_guest=False)
def download_media(**kwargs):
    instance_id = kwargs.get('instance_id')
    message_id = kwargs.get('message_id')
    return _proxy_request(f"instance/{instance_id}/media/{message_id}/download", "GET", **kwargs)

@frappe.whitelist(allow_guest=False)
def generate_thumbnail(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/media/thumbnail", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def optimize_image(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/media/optimize", "POST", **kwargs)

# Chat Management
@frappe.whitelist(allow_guest=False)
def archive_chat(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/chat/archive", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def mute_chat(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/chat/mute", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def mark_read(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/chat/read", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def pin_chat(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/chat/pin", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def delete_chat(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/chat", "DELETE", **kwargs)

@frappe.whitelist(allow_guest=False)
def star_message(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/chat/star", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def set_disappearing(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/chat/disappearing", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def chat_history(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/chat/history", "GET", **kwargs)

# Presence & Status
@frappe.whitelist(allow_guest=False)
def update_presence(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/presence/update", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def set_typing(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/presence/typing", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def set_online(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/presence/online", "POST", **kwargs)

# Profile Management
@frappe.whitelist(allow_guest=False)
def update_name(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/profile/name", "PUT", **kwargs)

@frappe.whitelist(allow_guest=False)
def update_status(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/profile/status", "PUT", **kwargs)

@frappe.whitelist(allow_guest=False)
def update_picture(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/profile/picture", "PUT", **kwargs)

@frappe.whitelist(allow_guest=False)
def get_picture(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/profile/picture", "GET", **kwargs)

# Privacy Settings
@frappe.whitelist(allow_guest=False)
def block_user(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/privacy/block", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def unblock_user(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/privacy/unblock", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def get_blocklist(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/privacy/blocklist", "GET", **kwargs)

@frappe.whitelist(allow_guest=False)
def update_privacy(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/privacy/settings", "PUT", **kwargs)

@frappe.whitelist(allow_guest=False)
def get_privacy(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/privacy/settings", "GET", **kwargs)

# Broadcast & Stories
@frappe.whitelist(allow_guest=False)
def send_broadcast(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/broadcast/send", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def send_status(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/status/send", "POST", **kwargs)

# Group Management
@frappe.whitelist(allow_guest=False)
def create_group(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/group/create", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def list_groups(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/groups", "GET", **kwargs)

@frappe.whitelist(allow_guest=False)
def get_group(**kwargs):
    instance_id = kwargs.get('instance_id')
    group_jid = kwargs.get('group_jid')
    return _proxy_request(f"instance/{instance_id}/group/{group_jid}", "GET", **kwargs)

@frappe.whitelist(allow_guest=False)
def update_group_subject(**kwargs):
    instance_id = kwargs.get('instance_id')
    group_jid = kwargs.get('group_jid')
    return _proxy_request(f"instance/{instance_id}/group/{group_jid}/subject", "PUT", **kwargs)

@frappe.whitelist(allow_guest=False)
def update_group_description(**kwargs):
    instance_id = kwargs.get('instance_id')
    group_jid = kwargs.get('group_jid')
    return _proxy_request(f"instance/{instance_id}/group/{group_jid}/description", "PUT", **kwargs)

@frappe.whitelist(allow_guest=False)
def group_participants(**kwargs):
    instance_id = kwargs.get('instance_id')
    group_jid = kwargs.get('group_jid')
    return _proxy_request(f"instance/{instance_id}/group/{group_jid}/participants", "PUT", **kwargs)

@frappe.whitelist(allow_guest=False)
def leave_group(**kwargs):
    instance_id = kwargs.get('instance_id')
    group_jid = kwargs.get('group_jid')
    return _proxy_request(f"instance/{instance_id}/group/{group_jid}/leave", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def get_invite_code(**kwargs):
    instance_id = kwargs.get('instance_id')
    group_jid = kwargs.get('group_jid')
    return _proxy_request(f"instance/{instance_id}/group/{group_jid}/invite", "GET", **kwargs)

# Utilities
@frappe.whitelist(allow_guest=False)
def check_number(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/utils/check-number", "GET", **kwargs)

@frappe.whitelist(allow_guest=False)
def validate_jid(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/utils/validate-jid", "GET", **kwargs)

@frappe.whitelist(allow_guest=False)
def format_number(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/utils/format-number", "GET", **kwargs)

@frappe.whitelist(allow_guest=False)
def device_info(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/utils/device-info", "GET", **kwargs)

# Advanced Features
@frappe.whitelist(allow_guest=False)
def send_link_preview(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/advanced/link-preview", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def send_sticker(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/advanced/sticker", "POST", **kwargs)

@frappe.whitelist(allow_guest=False)
def search_messages(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/advanced/search", "GET", **kwargs)

@frappe.whitelist(allow_guest=False)
def export_chat(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/advanced/export", "POST", **kwargs)

# Health & Monitoring
@frappe.whitelist(allow_guest=False)
def health_check(**kwargs):
    return _proxy_request("health", "GET", require_instance=False, **kwargs)

@frappe.whitelist(allow_guest=False)
def get_messages(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/messages", "GET", **kwargs)

# Template & Buttons
@frappe.whitelist(allow_guest=False)
def send_template_buttons(**kwargs):
    instance_id = kwargs.get('instance_id')
    return _proxy_request(f"instance/{instance_id}/send/template-buttons", "POST", **kwargs)
