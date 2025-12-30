import frappe
from frappe.model.document import Document

class WhatsAppInstance(Document):
    def on_update(self):
        # Sync to WhatsApp Customer's child table
        if self.whatsapp_customer:
            customer = frappe.get_doc("WhatsApp Customer", self.whatsapp_customer)
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
