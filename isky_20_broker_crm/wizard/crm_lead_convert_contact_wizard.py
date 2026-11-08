from odoo import fields, models


class CrmLeadConvertContactWizard(models.TransientModel):
    _name = 'crm.lead.convert.contact.wizard'
    _description = "Create Contact on Lead Conversion"

    lead_id = fields.Many2one('crm.lead', required=True)
    name = fields.Char(string="Contact Name", required=True)
    phone = fields.Char()
    email = fields.Char()
    company_name = fields.Char(string="Company Name")

    def action_confirm(self):
        self.ensure_one()
        partner = self.env['res.partner'].create({
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'parent_name': self.company_name,
            'type': 'contact',
        })
        self.lead_id.convert_opportunity(partner)
        return {'type': 'ir.actions.act_window_close'}
