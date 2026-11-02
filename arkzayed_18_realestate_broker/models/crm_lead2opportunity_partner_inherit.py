from odoo import fields, models, api

class lead2opportunity(models.TransientModel):

    _inherit = 'crm.lead2opportunity.partner'

    partner_id = fields.Many2one(
        'res.partner', 'Customer', domain="[('is_customer','=', True)]", readonly=False, store=True, compute=False)
    contact_name = fields.Char(related='lead_id.contact_name', readonly=True)
    phone = fields.Char(compute='_compute_phone_number', readonly=True)
    other = fields.Char(related='lead_id.other', readonly=False)

    @api.depends('lead_id')
    def _compute_phone_number(self):
        for rec in self:
            if rec.lead_id:
                if rec.lead_id.phone:
                    rec.phone = rec.lead_id.phone
                elif rec.lead_id.phone2:
                    rec.phone = rec.lead_id.phone2
                elif rec.lead_id.mobile:
                    rec.phone = rec.lead_id.mobile
                else:
                    rec.phone = False




