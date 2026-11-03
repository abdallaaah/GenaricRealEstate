from odoo import models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def write(self, vals):
        result = super().write(vals)
        if result and vals.get('stage_id'):
            new_stage = self.env['crm.stage'].browse(vals['stage_id'])
            if new_stage.is_confirmed_contract:
                Achievement = self.env['realestate.commission.achievement']
                for lead in self:
                    Achievement.create_from_lead(lead)
        return result
