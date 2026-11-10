from odoo import fields, models


class CrmLeadUnqualifiedWizard(models.TransientModel):
    _name = 'crm.lead.unqualified.wizard'
    _description = "Unqualify Lead Wizard"

    lead_id = fields.Many2one('crm.lead', required=True)
    lost_reason_id = fields.Many2one('crm.lost.reason', required=True)

    def action_confirm(self):
        self.ensure_one()
        self.lead_id.write({
            'lost_reason_id': self.lost_reason_id.id,
            'lead_stage_id': self.env.ref('isky_20_broker_crm.lead_stage_unqualified').id,
        })
        return {'type': 'ir.actions.act_window_close'}
