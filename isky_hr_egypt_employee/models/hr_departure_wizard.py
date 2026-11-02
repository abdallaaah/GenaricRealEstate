from odoo import models, fields

class HrDepartureWizard(models.TransientModel):
    _inherit = 'hr.departure.wizard'

    resignation_date = fields.Datetime()

    def action_register_departure(self):
        super().action_register_departure()

        employee = self.employee_id
        employee.resignation_date = self.resignation_date