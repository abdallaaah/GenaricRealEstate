from odoo import api, fields, models


class Counter(models.Model):
    _name = 'counter.counter'

    serial_no = fields.Char()
    Type = fields.Char()
    unit_id = fields.Many2one('broker.unit')
    meter_type = fields.Selection([
        ('electricity', 'Electricity'),
        ('gas', 'Gas'),
        ('water', 'Water')
    ])

class Gas(models.Model):
    _name = "gas.counter"
    serial_no = fields.Char()
    Type = fields.Char()
    unit_id = fields.Many2one('broker.unit')
    meter_type = fields.Selection([
        ('electricity', 'Electricity'),
        ('gas', 'Gas'),
        ('water', 'Water')
    ])

class Water(models.Model):
    _name = "water.counter"
    serial_no = fields.Char()
    Type = fields.Char()
    unit_id = fields.Many2one('broker.unit')
    meter_type = fields.Selection([
        ('electricity', 'Electricity'),
        ('gas', 'Gas'),
        ('water', 'Water')
    ])

class Landline(models.Model):
    _name = 'landline.counter'

    service_provider = fields.Char(string="Service Provider")
    activation_date = fields.Date(string="Activation Date")
    unit_id = fields.Many2one('broker.unit')

class Internet(models.Model):
    _name = 'internet'

    service_provider = fields.Char(string="Service Provider")
    type = fields.Char()
    unit_id = fields.Many2one('broker.unit')


