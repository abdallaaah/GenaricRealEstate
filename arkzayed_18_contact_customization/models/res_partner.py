from odoo import fields, models, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_resale_seller = fields.Boolean()
    is_resale_buyer = fields.Boolean()
    is_developer = fields.Boolean()
    is_broker = fields.Boolean(string='Is Broker')
    is_ambassador = fields.Boolean(string='Is Ambassador')
    whats_up_phone = fields.Char('What\'s Up Phone')
    customer_code = fields.Char(string='Customer Code')
    mobile = fields.Char(string='Mobile Number')
    email = fields.Char(string='Email Address')
    address_1 = fields.Text(string='Address 1')
    address_2 = fields.Text(string='Address 2')

    type = fields.Selection(
        selection_add=[("representative", "Representative")], ondelete={"representative": "cascade"}
    )

    national_id = fields.Char(string='National ID Number')
    passport_number = fields.Char()
    passport_attachment = fields.Binary()
    national_id_attachment = fields.Binary()
    national_id_expiry_date = fields.Date()
    passport_number_expiry_date = fields.Date()

    cr = fields.Char()
    TRN = fields.Char(string='Vat Certificate')
    cr_attachment = fields.Binary()
    TRN_attachment = fields.Binary(string='Vat Certificate Attachment')
    tax_attachment = fields.Binary(string='Tax ID Attachment')
    cr_expiry_date = fields.Date()
    TRN_expiry_date = fields.Date(string='Vat Certificate Expiry Date')
    tax_expiry_date = fields.Date(string='Tax ID Expiry Date')

    company_profile = fields.Binary()

    representative_id = fields.Char(string='Representative ID Number')
    representative_attachment = fields.Binary(string='Representative ID Attachment')
    representative_expiry_date = fields.Date(string='ID Number Expiration Date')
    is_portal = fields.Boolean(compute="_compute_is_portal", store=True)
    is_customer = fields.Boolean()
    is_vendor = fields.Boolean()
    is_facility_company = fields.Boolean(string='facility company')
    sale_portal_user = fields.Boolean()
    purchase_portal_user = fields.Boolean()
    lease_contract = fields.Boolean()
    facility_contract = fields.Boolean()

    phone1 = fields.Char('Extra Phone 2')
    phone2 = fields.Char('International Phone')
    phone3 = fields.Char('Extra International Phone')
    phone4 = fields.Char('Extra International Phone 2')

    _sql_constraints = [
        ('unique_national_id', 'UNIQUE(national_id)',
         'The National ID must be unique! Another contact already uses this value.'),
        ('unique_passport_number', 'UNIQUE(passport_number)',
         'The Passport Number must be unique! Another contact already uses this value.'),
    ]

    @api.onchange('customer_rank')
    def _onchange_rank(self):
        if self.customer_rank:
            self.is_customer = True

    def _compute_is_portal(self):
        users = self.env['res.users'].search([('partner_id', 'in', self.ids)])
        data = {
            user.partner_id.id: user.share
            for user in users
        }
        for partner_id in self:
            partner_id.is_portal = data.get(partner_id.id)
