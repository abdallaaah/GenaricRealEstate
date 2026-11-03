from odoo import models, fields


class BusinessUnitType(models.Model):
    _name = 'business.unit.type'
    _description = 'Business Unit Type'

    name = fields.Char(string='Type Name', required=True, unique=True)
    label = fields.Char(string='Label', help='Display label for the type')

    def _get_or_create_types(self):
        """Get or create business unit types from real.estate.unit"""
        unit_obj = self.env['real.estate.unit']
        units = unit_obj.search([
            ('unit_type', '!=', False),
            ('unit_type', '!=', 'residential')
        ])

        existing_types = set(record.name for record in self.search([]))
        unit_types = set(unit.unit_type for unit in units if unit.unit_type)

        for unit_type in unit_types:
            if unit_type not in existing_types:
                self.create({
                    'name': unit_type,
                    'label': unit_type.title()
                })