from odoo import fields, models


class BrokerUnitCounter(models.Model):
    """Unit utility connection (electricity/gas/water/landline/internet).

    Replaces the v17 system's five near-identical models (counter.counter,
    gas.counter, water.counter, landline.counter, internet) with one model
    distinguished by counter_type, instead of duplicating the same three
    fields five times.
    """
    _name = 'broker.unit.counter'
    _description = "Unit Utility Counter"

    unit_id = fields.Many2one('broker.unit', required=True, ondelete='cascade')
    counter_type = fields.Selection([
        ('electricity', "Electricity"),
        ('gas', "Gas"),
        ('water', "Water"),
        ('landline', "Landline"),
        ('internet', "Internet"),
    ], required=True)
    serial_no = fields.Char()
    service_provider = fields.Char()
    activation_date = fields.Date()
