# -*- coding: utf-8 -*-
from odoo import fields, models, api

class AccountAccount(models.Model):
    _inherit = "account.account"
    
    is_under_collection = fields.Boolean(string="Is Under Collection", default=False, 
                                         help="Check this box if this account is used for cheques under collection")
    is_hermes = fields.Boolean(string="Is Hermes")
