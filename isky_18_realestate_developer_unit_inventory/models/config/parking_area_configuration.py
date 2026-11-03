from odoo import models, fields

class ParkingAreaConfiguration(models.Model):
    _name = "parking.area.configuration"
    _description = "Parking Slots Configuration by Gross Area"

    name = fields.Char(string="Name", required=True)
    unit_type = fields.Selection([
        ('retail', 'Retail'),
        ('office', 'Office'),
        ('medical', 'Medical'),
        ('entertainment', 'Entertainment'),
        ('industrial', 'Industrial'),
    ], string='Unit Type', required=True)
    area_per_slot = fields.Float(
        string="Area Per Slot",
        required=True,
    )



