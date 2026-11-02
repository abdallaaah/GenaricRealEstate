from odoo import api, fields, models


class ReturnReason(models.Model):
    _name = 'return.reason'
    _description = 'Return Reason'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True)
