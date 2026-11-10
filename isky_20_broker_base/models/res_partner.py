from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_resale_seller = fields.Boolean()
    is_resale_buyer = fields.Boolean()
    is_developer = fields.Boolean()
    is_broker = fields.Boolean(string="Is Broker")
    is_ambassador = fields.Boolean(string="Is Ambassador")
    is_customer = fields.Boolean()
    is_vendor = fields.Boolean(string="Vendor")
    sale_portal_user = fields.Boolean()
    purchase_portal_user = fields.Boolean()
    lease_contract = fields.Boolean()
    facility_contract = fields.Boolean()
    is_portal = fields.Boolean(compute='_compute_is_portal', store=True)

    type = fields.Selection(
        selection_add=[('representative', "Representative"), ('media_buyer', "Media Buyer")],
        ondelete={'representative': 'cascade', 'media_buyer': 'cascade'},
    )

    whats_up_phone = fields.Char(string="WhatsApp Phone")
    phone1 = fields.Char(string="Extra Phone 2")
    phone2 = fields.Char(string="International Phone")
    phone3 = fields.Char(string="Extra International Phone")
    phone4 = fields.Char(string="Extra International Phone 2")

    national_id = fields.Char()
    national_id_attachment = fields.Binary()
    national_id_expiry_date = fields.Date()
    passport_number = fields.Char()
    passport_attachment = fields.Binary()
    passport_number_expiry_date = fields.Date()

    cr = fields.Char(string="Commercial Registration")
    cr_attachment = fields.Binary()
    cr_expiry_date = fields.Date()
    TRN = fields.Char(string="Vat Certificate")
    TRN_attachment = fields.Binary(string="Vat Certificate Attachment")
    TRN_expiry_date = fields.Date(string="Vat Certificate Expiry Date")
    tax_attachment = fields.Binary(string="Tax ID Attachment")
    tax_expiry_date = fields.Date(string="Tax ID Expiry Date")
    company_profile = fields.Binary()

    representative_id = fields.Char(string="Representative ID Number")
    representative_attachment = fields.Binary(string="Representative ID Attachment")
    representative_expiry_date = fields.Date(string="ID Number Expiration Date")

    def _compute_is_portal(self):
        users = self.env['res.users'].search([('partner_id', 'in', self.ids)])
        share_by_partner = {user.partner_id.id: user.share for user in users}
        for partner in self:
            partner.is_portal = share_by_partner.get(partner.id, False)

    @api.onchange('customer_rank')
    def _onchange_customer_rank(self):
        if self.customer_rank:
            self.is_customer = True
