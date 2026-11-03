from odoo import api, fields, models


class Internet(models.Model):
    _name = 'realestate.internet'
    _description = 'Realestate Internet'

    service_provider = fields.Char(string="Service Provider")
    type = fields.Char()
    unit_id = fields.Many2one('real.estate.unit', domain=[('unit_status', '=', 'available')])
