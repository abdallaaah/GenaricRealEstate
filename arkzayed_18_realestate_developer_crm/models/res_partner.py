from odoo import models, fields

class ResPartnerInerit(models.Model):

    _inherit = "res.partner"
    _rec_names_search = ['complete_name', 'email', 'ref', 'vat', 'company_registry', 'mobile', 'phone']
