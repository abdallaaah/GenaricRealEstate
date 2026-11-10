from odoo import models

# Which crm.stage flag opens commission. The first generation fired on Confirmed
# Contract; the live gen-2 engine moved off that stage entirely and creates commission
# once collection reaches the plan's threshold, because signing a contract is not the
# same as having been paid. The broker side has no installment ledger to measure a
# collection percentage against, but it does have a Collected stage -- so the choice of
# trigger is a setting rather than a hard-coded stage.
TRIGGER_STAGE_FIELDS = {
    'confirmed_contract': 'is_confirmed_contract',
    'collected': 'is_collected',
}
DEFAULT_TRIGGER = 'confirmed_contract'


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def write(self, vals):
        result = super().write(vals)
        if result and vals.get('stage_id'):
            new_stage = self.env['crm.stage'].browse(vals['stage_id'])
            trigger = self.env['ir.config_parameter'].sudo().get_param(
                'isky_20_broker_commission.commission_trigger_stage', DEFAULT_TRIGGER)
            stage_field = TRIGGER_STAGE_FIELDS.get(trigger, TRIGGER_STAGE_FIELDS[DEFAULT_TRIGGER])
            if new_stage[stage_field]:
                Achievement = self.env['realestate.commission.achievement']
                for lead in self:
                    Achievement.create_from_lead(lead)
        return result
