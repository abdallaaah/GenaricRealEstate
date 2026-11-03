from odoo import models, fields, api


class OfficeTypeInherit(models.Model):
    _name = 'office.type'
    _description = 'Office Type'

    name = fields.Char(string='Office Type', required=True)