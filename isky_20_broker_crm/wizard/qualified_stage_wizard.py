from odoo import fields, models
from odoo.addons.isky_20_broker_crm.models.crm_lead import UNIT_TYPE_SELECTION


class QualifiedStageWizard(models.TransientModel):
    _name = 'qualified.stage.wizard'
    _description = "Qualify Lead Wizard"

    lead_id = fields.Many2one('crm.lead', required=True)
    limited_budget = fields.Boolean()
    priority = fields.Selection(related='lead_id.priority', readonly=False)
    unit_type = fields.Selection(UNIT_TYPE_SELECTION, default=lambda self: self.lead_id.unit_type)
    finish_type = fields.Selection([
        ('finished', "Finished"), ('semi_finished', "Semi-Finished"), ('core_shell', "Core and Shell"),
    ])
    min_area = fields.Float()
    max_area = fields.Float()
    currency_id = fields.Many2one(related='lead_id.company_currency')
    min_price = fields.Monetary(currency_field='currency_id')
    max_price = fields.Monetary(currency_field='currency_id')
    qualified_comment = fields.Text(required=True)

    def action_confirm(self):
        self.ensure_one()
        target_stage = 'isky_20_broker_crm.lead_stage_qualified_limited_budget' if self.limited_budget \
            else 'isky_20_broker_crm.lead_stage_qualified'
        self.lead_id.write({
            'priority': self.priority,
            'unit_type': self.unit_type,
            'finish_type': self.finish_type,
            'min_area': self.min_area,
            'max_area': self.max_area,
            'min_price': self.min_price,
            'max_price': self.max_price,
            'qualified_comment': self.qualified_comment,
            'lead_stage_id': self.env.ref(target_stage).id,
        })
        return {'type': 'ir.actions.act_window_close'}
