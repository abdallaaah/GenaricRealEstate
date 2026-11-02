from odoo import models, fields


class ParkingTemplate(models.Model):

    _name = 'parking.template'
    name = fields.Char()