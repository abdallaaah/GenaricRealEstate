from odoo import fields, models, api
from odoo.exceptions import ValidationError


class UnqualifiedLeadWizard(models.TransientModel):
    _name = 'crm.lead.unqualified.wizard'
    _description = 'Unqualified Lead Wizard'

    lead_id = fields.Many2one('crm.lead', string='Lead')

    lost_reason_id = fields.Many2one('crm.lost.reason', string='Unqualified Reason', required=True)

    def action_confirm(self):
        self.ensure_one()
        if not self.lost_reason_id:
            raise ValidationError("Cancel Reason Is Required")

        if self.lead_id:
            self.lead_id.write({
                'lost_reason_id': self.lost_reason_id,
                'lead_stage_id': self.env.ref('arkzayed_18_realestate_developer_crm.stage_unqualified').id
            })
        return {'type': 'ir.actions.act_window_close'}
