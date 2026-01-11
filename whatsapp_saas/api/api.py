import frappe
import requests
import json
from frappe.utils import add_months, today
from frappe.auth import LoginManager
from frappe import _

@frappe.whitelist(allow_guest=False)
def proxy(**kwargs):
    """
    Proxy API calls to the internal WhatsApp Baileys container.
    Authentication is handled by Frappe's standard API Key/Secret mechanism.
    
    Expected Headers:
    - Authorization: token api_key:api_secret
    
    Expected Body (JSON):
    - instance_id: The ID of the WhatsApp Instance
    - method: HTTP method (GET, POST, PUT, DELETE)
    - endpoint: The API endpoint (e.g., /chat/send)
    - data: Payload for the request
    """
    try:
        user = frappe.session.user
        if user == 'Guest':
            frappe.throw(_("Authentication required"), frappe.PermissionError)
            
        # Determine request data source
        req_data = {}
        # 1. Query Parameters (GET requests often use these)
        if frappe.request.args:
            req_data.update(frappe.request.args)

        # 2. JSON Body
        if frappe.request.content_type == 'application/json':
            try:
                if frappe.request.data:
                    req_data.update(frappe.request.json)
            except:
                pass
        else:
            # 3. Form Data (multipart/form-data or application/x-www-form-urlencoded)
            try:
                if frappe.request.form:
                    req_data.update(frappe.request.form)
                # Fallback for raw data if not parsed
                if frappe.request.data and not req_data:
                     req_data.update(json.loads(frappe.request.data))
            except:
                pass
            
        instance_id = req_data.get('instance_id')
        endpoint = req_data.get('endpoint')
        method = req_data.get('method', frappe.request.method if frappe.request.method != 'POST' else 'POST').upper()
        
        # 'data' in body is priority for the payload sent to Baileys
        payload = req_data.get('data') 
        
        if payload is None:
             # Basic payload construction: remove proxy-specific fields
             payload = {k:v for k,v in req_data.items() if k not in ['instance_id', 'endpoint', 'method', 'cmd', 'sid', 'csrf_token']}

        if not instance_id or not endpoint:
            frappe.throw(_("Missing instance_id or endpoint"))
            
        # 1. Verification
        customer_name = frappe.db.get_value("WhatsApp Customer", {"user": user}, "name")
        if not customer_name:
            frappe.throw(_("No WhatsApp Customer account linked to this user"))
            
        instance = frappe.get_doc("WhatsApp Instance", {"instance_id": instance_id})
        if not instance:
             frappe.throw(_("Instance not found"))
             
        if instance.whatsapp_customer != customer_name:
            frappe.throw(_("Unauthorized access to this instance"))
            
        subscription = frappe.get_doc("WhatsApp Subscription", instance.subscription)
        if subscription.status != 'Active':
            frappe.throw(_("Subscription is not active"))
            
        # 2. Rate Limiting
        plan = frappe.get_doc("WhatsApp Plan", subscription.plan)
        max_messages = plan.max_messages_per_month
        
        from frappe.utils import get_first_day, get_last_day, today
        current_usage = frappe.db.count("WhatsApp Message Log", {
            "subscription": subscription.name,
            "creation": ["between", [get_first_day(today()), get_last_day(today())]]
        })
        
        if current_usage >= max_messages:
            frappe.throw(_("Monthly message limit reached"))
            
        # 3. Forward to Baileys
        # Clean endpoint
        endpoint = endpoint.lstrip('/')
        baileys_url = f"http://whatsapp-baileys:3000/api/instance/{instance_id}/{endpoint}"
        
        headers = {}
        files = None
        
        if frappe.request.files:
            files = {}
            for key, file_storage in frappe.request.files.items():
                files[key] = (file_storage.filename, file_storage.stream, file_storage.content_type)
        
        req_params = None
        req_json = None
        req_data_body = None
        
        if method == 'GET':
            req_params = payload
        else:
            if files:
                req_data_body = payload # fields alongside files
            else:
                req_json = payload

        try:
            response = requests.request(
                method=method,
                url=baileys_url,
                params=req_params,
                json=req_json,
                data=req_data_body,
                files=files,
                headers=headers,
                timeout=60
            )
        except Exception as conn_err:
             frappe.throw(_(f"Connection to WhatsApp Service failed: {str(conn_err)}"))
        
        # 4. Logging
        log_all = True 
        if log_all or method in ['POST', 'PUT', 'DELETE']:
            msg_id = None
            try:
                # Try to get Message ID from response
                resp_json = response.json()
                if isinstance(resp_json, dict):
                    msg_id = resp_json.get('key', {}).get('id') or resp_json.get('id') or resp_json.get('messageId')
            except:
                pass
            
            if not msg_id:
                 # Generate a tracking ID if none returned
                 msg_id = "LOG-" + frappe.generate_hash(length=10)

            doc = frappe.get_doc({
                "doctype": "WhatsApp Message Log",
                "instance": instance.name,
                "message_id": msg_id,
                "timestamp": frappe.utils.now(),
                "status": "Sent" if response.ok else "Failed",
                "direction": "Outbound",
                "whatsapp_customer": customer_name,
                "subscription": subscription.name
            })
            doc.insert(ignore_permissions=True)

        try:
            return response.json()
        except:
             return response.content

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "WhatsApp Proxy Error")
        return {"error": str(e), "traceback": frappe.get_traceback()}

@frappe.whitelist(allow_guest=True)
def signup():
    frappe.db.savepoint(save_point="whatsapp_signup")
    try:
        data = {}
        if frappe.request.content_type == 'application/json':
            data = frappe.request.json
        else:
            data = frappe.request.form.to_dict()
        
        required_fields = ['customer_name', 'email', 'phone','password']
        for field in required_fields:
            if field not in data:
                frappe.throw(_(f"Missing required field: {field}"))
        
        user = frappe.get_doc({
            "doctype": "User",
            "email": data['email'],
            "first_name": data['customer_name'],
            "enabled": 1,
            "role_profile_name": "Customer",
            "module_profile": "WhatsApp",
            "new_password": data['password']
        }).insert(ignore_permissions=True)
        
        user.api_key = frappe.generate_hash(length=15)
        api_secret = frappe.generate_hash(length=32)
        user.api_secret = api_secret
        user.save(ignore_permissions=True)

        token = f"{user.api_key}:{api_secret}"

        login_manager = LoginManager()
        login_manager.authenticate(user=data["email"], pwd=data["password"])
        login_manager.post_login()
        
        frappe.set_user(user.name)
        # Create WhatsApp Customer
        customer = frappe.get_doc({
            "doctype": "WhatsApp Customer",
            "customer_name": data['customer_name'],
            "email": data['email'],
            "phone": data['phone'],
            "token": token,
            "current_plan": data.get("plan") or "Free Plan",
            "user": user.name
        })
        customer.insert(ignore_permissions=True)
        
        # Create Subscription
        subscription = frappe.get_doc({
            "doctype": "WhatsApp Subscription",
            "customer": customer.name,
            "plan": data.get("plan") or "Free Plan",
            "start_date": today(),
            "end_date": add_months(today(), 1),
            "status": "Active"
        })
        subscription.insert(ignore_permissions=True)
        

        return {
            "message": "Signup successful",
            "customer": customer.name,
            "subscription": subscription.name
        }

    except Exception as e:
        frappe.db.rollback(save_point="whatsapp_signup")
        frappe.log_error(frappe.get_traceback(), "WhatsApp Signup Error")
        return {"error": str(e), "traceback": frappe.get_traceback()}

@frappe.whitelist(allow_guest=True, methods=['POST'])
def webhook():
    try:
        frappe.log_error("WhatsApp Webhook Received",frappe.request.data)
        data = {}
        if frappe.request.content_type == 'application/json':
            data = frappe.request.json
        else:
            data = frappe.request.form.to_dict()
        # Process webhook data as needed
        
        if frappe.db.exists("WhatsApp Instance",{"instance_id":data.get("instanceId")}):
            
            instance = frappe.get_doc("WhatsApp Instance",{"instance_id":data.get("instanceId")})
            if data.get("event") == "connection.update":
                webhook_data = data.get("data",{})
                if webhook_data.get("status") == "connected":
                    instance.status = "Connected"
                    instance.phone_number = webhook_data.get("phoneNumber")
                    instance.save(ignore_permissions=True)
                    frappe.db.commit()

                elif webhook_data.get("status") == "logged_out":
                    
                    instance.status = "Disconnected"
                    instance.save(ignore_permissions=True)
                    frappe.db.commit()
        else:
            frappe.throw(_("Instance not found"))

        return {"message": "Webhook processed successfully"}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "WhatsApp Webhook Error")
        return {"error": str(e), "traceback": frappe.get_traceback()}