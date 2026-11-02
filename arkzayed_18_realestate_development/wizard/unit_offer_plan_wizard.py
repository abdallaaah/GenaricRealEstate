from odoo import _, fields, models
from odoo.exceptions import UserError


class UnitOfferPlanWizard(models.TransientModel):
    _name = 'unit.offer.plan.wizard'
    _description = 'Print Unit Offer Plan'

    unit_id = fields.Many2one('real.estate.unit', string='Unit', required=True, readonly=True)
    project_id = fields.Many2one(related='unit_id.project_id')
    template_ids = fields.Many2many(
        'installment.template', 'unit_offer_plan_wizard_template_rel', 'wizard_id', 'template_id',
        string='Payment Plans', required=True,
        domain="['|', ('project_ids', '=', False), ('project_ids', 'in', project_id)]",
        help='Only the plans you pick here are printed, one page each, after the unit page.')

    def action_print(self):
        self.ensure_one()
        if not self.template_ids:
            raise UserError(_('Pick at least one payment plan to print.'))
        return self.env.ref('arkzayed_18_realestate_development.action_unit_offer_plan').report_action(
            self.unit_id, data={'template_ids': self.template_ids.ids, 'doc_ids': self.unit_id.ids})
