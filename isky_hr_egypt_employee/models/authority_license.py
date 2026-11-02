from odoo import models, fields, api


class AuthorityLicense(models.Model):
    _name = 'authority.license'
    _description = 'Authority License'

    include = fields.Boolean(string='Include?')
    license_name = fields.Char(string='License Name', translate=True)
    expiry_date = fields.Date(string='Expiry Date')
    employee_id = fields.Many2one("hr.employee", string="Employee")