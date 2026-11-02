from .selections import meter_type_selection
from odoo import api, fields, models


class Counter(models.Model):
    _name = 'realestate.counter'
    _description = 'Realestate Counter'

    serial_no = fields.Char()
    Type = fields.Char()
    unit_id = fields.Many2one('real.estate.unit', domain=[('unit_status', '=', 'available')])
    meter_type = fields.Selection(selection=meter_type_selection)

class Gas(models.Model):
    _name = "realestate.gas.counter"
    _description = "Realestate Gas Counter"
    serial_no = fields.Char()
    Type = fields.Char()
    unit_id = fields.Many2one('real.estate.unit', domain=[('unit_status', '=', 'available')])
    meter_type = fields.Selection(selection=meter_type_selection)

class Water(models.Model):
    _name = "realestate.water.counter"
    _description = "Realestate Water Counter"
    serial_no = fields.Char()
    Type = fields.Char()
    unit_id = fields.Many2one('real.estate.unit', domain=[('unit_status', '=', 'available')])
    meter_type = fields.Selection(selection=meter_type_selection)
