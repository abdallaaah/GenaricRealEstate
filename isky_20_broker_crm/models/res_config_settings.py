from odoo import api, fields, models

from .crm_feature_codes import CRM_FEATURE_FINANCE_STAGE_GATE


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    broker_sequence_prefix = fields.Char(related='company_id.broker_sequence_prefix', readonly=False)
    broker_unassigned_leads_visible_to_all = fields.Boolean(
        related='company_id.broker_unassigned_leads_visible_to_all', readonly=False)

    # Surface for the broker.feature.flag record, same pattern as the commission flags.
    crm_finance_stage_gate_enabled = fields.Boolean(
        string="Finance Stage Gates", compute='_compute_crm_feature_flags',
        inverse='_inverse_crm_finance_stage_gate',
        help="On (default): only Deal Finance can move a deal to Collected or Confirmed "
             "Contract, and only Finance or an Operations Manager can reopen a cancelled "
             "deal. Off: anyone who can edit the deal may do so -- the required dates, "
             "attachments, and reasons still apply.")

    @api.depends_context('company')
    def _compute_crm_feature_flags(self):
        FeatureFlag = self.env['broker.feature.flag']
        for settings in self:
            settings.crm_finance_stage_gate_enabled = FeatureFlag.is_feature_enabled(
                CRM_FEATURE_FINANCE_STAGE_GATE)

    def _inverse_crm_finance_stage_gate(self):
        self.env['broker.feature.flag']._set_flag(
            CRM_FEATURE_FINANCE_STAGE_GATE, "CRM: Finance Stage Gates",
            self.crm_finance_stage_gate_enabled, category='crm')
