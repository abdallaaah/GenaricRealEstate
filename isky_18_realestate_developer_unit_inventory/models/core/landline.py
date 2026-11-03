from odoo import api, fields, models


class Landline(models.Model):
    _name = 'realestate.landline.counter'
    _description = 'Realestate Landline Counter'

    service_provider = fields.Char(string="Service Provider")
    activation_date = fields.Date(string="Activation Date")
    unit_id = fields.Many2one('real.estate.unit', domain=[('unit_status', '=', 'available')])
