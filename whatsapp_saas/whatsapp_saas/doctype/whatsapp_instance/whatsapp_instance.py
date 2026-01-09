import frappe
from frappe.model.document import Document
import requests

class WhatsAppInstance(Document):
    def before_insert(self):
        try:
            user = frappe.session.user
            if self.instance_name:
                existing = frappe.db.get_value("WhatsApp Instance", {"instance_name": self.instance_name, "owner": user})
                if existing:
                    frappe.log_error(f"Instance with name {self.instance_name} already exists.")
                    return {
                        "status": "error",
                        "message": f"Instance with name {self.instance_name} already exists."
                    }
             
            current_plan = frappe.db.get_value("WhatsApp Customer", {"user": user}, "current_plan")
            instance_limit = frappe.db.get_value("WhatsApp Plan", current_plan, "max_instances") or 0
            existing_instances = frappe.db.count("WhatsApp Instance", {"owner": user})
            if existing_instances >= instance_limit:
                frappe.log_error(f"You have reached the maximum limit of {instance_limit} instances for your current plan.")
                return {
                    "status": "error",
                    "message": f"You have reached the maximum limit of {instance_limit} instances for your current plan."
                }
        except Exception as e:
            frappe.log_error(f"Error checking instance limit: {str(e)}")
            return {
                "status": "error",
                "message": "An error occurred while creating instance."
            }
        

    def after_insert(self):
        try:
            user = frappe.session.user
            url = "http://whatsapp-baileys:3000/api/instance/create"
            data = {
                "name": self.instance_name
            }

            response = requests.post(url, json=data, timeout=60)
            response_data = response.json()
            
            # Create instance record in Frappe
            if response_data.get('success'):
                self.instance_id = response_data.get("data", {}).get('id')
                self.status = "Disconnected"
                self.save()
                frappe.db.commit()
                # frappe.get_doc({
                #     "doctype": "WhatsApp Instance",
                #     "instance_name": data.get('name', 'New Instance'),
                #     "instance_id": response_data.get("data", {}).get('id'),
                #     "status": "Disconnected",
                #     "subscription": subscription,
                #     "whatsapp_customer": customer_name
                # }).insert(ignore_permissions=True)
            
            return {
                "status": "success",
                "message": "Instance created successfully.",
                "instance_id": self.instance_id
            }
        except Exception as e:
            frappe.log_error(f"Error creating WhatsApp instance: {str(e)}")
            return {
                "status": "error",
                "message": "An error occurred while creating WhatsApp instance."
            }

    def on_update(self):
        # Sync to WhatsApp Customer's child table
        # if self.whatsapp_customer:
            customer = frappe.get_doc("WhatsApp Customer", {"user":self.owner})
            # Check if row exists
            found = False
            for row in customer.instances:
                if row.instance == self.name:
                    row.status = self.status
                    row.instance_id = self.instance_id
                    found = True
                    break
            
            if not found:
                customer.append("instances", {
                    "instance": self.name,
                    "instance_id": self.instance_id,
                    "status": self.status
                })
            
            customer.save(ignore_permissions=True)
