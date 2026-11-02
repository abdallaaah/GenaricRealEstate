from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from .selections import unit_type_selection

class UnitTypeConfiguration(models.Model):
    _name = "real.estate.unit.type.configuration"
    _description = "Unit Type Configuration"
    _rec_name = "name"

    name = fields.Char(string="Name")
    building_id = fields.Many2one("real.estate.building", string="Building", required=True)
    unit_type = fields.Selection(selection=unit_type_selection, string='Unit Type', required=True,default='residential')

    outdoor_price_percentage = fields.Float(
        string="Outdoor Price %",
        required=True,
    )

    indoor_price_sqm = fields.Float(
        string="Indoor Price/SQM",
        help="Default indoor price per square meter for units of this type in this building",
    )

    terrace_price_sqm = fields.Float(
        string="Terrace Price/SQM",
        help="Default terrace price per square meter for units of this type in this building",
    )

    indoor_gross_ratio = fields.Float(
        string="Indoor Gross Ratio",
        default=1.0,
    )
    terrace_gross_ratio = fields.Float(
        string="Terrace Gross Ratio",
        default=1.0,
    )
    garden_gross_ratio = fields.Float(
        string="Garden Gross Ratio",
        default=1.0,
    )
    outdoor_gross_ratio = fields.Float(
        string="Outdoor Gross Ratio",
        default=1.0,
    )

    _sql_constraints = [
        ('unique_building_unit_type',
         'unique(building_id, unit_type)',
         'Configuration already exists for this Building and Unit Type')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            unit_vals = {}
            if rec.indoor_price_sqm and rec.indoor_price_sqm > 0:
                unit_vals['indoor_price_sqm'] = rec.indoor_price_sqm
                if rec.outdoor_price_percentage:
                    unit_vals['outdoor_price_sqm'] = rec.indoor_price_sqm * rec.outdoor_price_percentage
            if rec.terrace_price_sqm and rec.terrace_price_sqm > 0:
                unit_vals['terrace_price_sqm'] = rec.terrace_price_sqm
            if unit_vals:
                units = self.env['real.estate.unit'].search([
                    ('building_id', '=', rec.building_id.id),
                    ('unit_type', '=', rec.unit_type),
                ])
                if units:
                    units.write(unit_vals)
        return records

    def write(self, vals):
        res = super().write(vals)
        price_fields = ['indoor_price_sqm', 'terrace_price_sqm', 'outdoor_price_percentage']
        if any(f in vals for f in price_fields):
            for rec in self:
                unit_vals = {}
                if 'indoor_price_sqm' in vals and rec.indoor_price_sqm and rec.indoor_price_sqm > 0:
                    unit_vals['indoor_price_sqm'] = rec.indoor_price_sqm
                if 'terrace_price_sqm' in vals and rec.terrace_price_sqm and rec.terrace_price_sqm > 0:
                    unit_vals['terrace_price_sqm'] = rec.terrace_price_sqm
                if ('indoor_price_sqm' in vals or 'outdoor_price_percentage' in vals) and rec.indoor_price_sqm and rec.outdoor_price_percentage:
                    unit_vals['outdoor_price_sqm'] = rec.indoor_price_sqm * rec.outdoor_price_percentage
                if unit_vals:
                    units = self.env['real.estate.unit'].search([
                        ('building_id', '=', rec.building_id.id),
                        ('unit_type', '=', rec.unit_type),
                    ])
                    if units:
                        units.write(unit_vals)
        return res

    @api.constrains('outdoor_price_percentage')
    def _check_percentage(self):
        for rec in self:
            if rec.outdoor_price_percentage < 0 or rec.outdoor_price_percentage > 100:
                raise ValidationError(_("Outdoor Price Percentage must be between 0 and 100!"))

    @api.constrains('indoor_gross_ratio', 'terrace_gross_ratio', 'garden_gross_ratio',
                    'outdoor_gross_ratio')
    def _check_ratio(self):
        for rec in self:
            if rec.indoor_gross_ratio < 1:
                raise ValidationError("Indoor Gross Area Ratio must be greater than or equal 1")
            if rec.terrace_gross_ratio < 1:
                raise ValidationError("Terrace Gross Area Ratio must be greater than or equal 1")
            if rec.garden_gross_ratio < 1:
                raise ValidationError("Garden Gross Area Ratio must be greater than or equal 1")
            if rec.outdoor_gross_ratio < 1:
                raise ValidationError("Outdoor Gross Area Ratio must be greater than or equal 1")
