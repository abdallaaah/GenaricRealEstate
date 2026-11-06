from odoo import models, api, fields

class SalesProposal(models.Model):
    _inherit = 'sale.proposal'

    opportunity_id = fields.Many2one('crm.lead', string='Opportunity')

    @api.model
    def create(self, vals):
        proposal = super().create(vals)

        if proposal.user_id or proposal.sales_ids or proposal.split_deal:
            proposal._build_commission_hierarchy()

        return proposal

    def write(self, vals):
        commission_fields = {'user_id', 'sales_ids', 'split_deal'}
        needs_rebuild = commission_fields.intersection(vals.keys())

        result = super().write(vals)
        if needs_rebuild:
            for rec in self:
                rec._build_commission_hierarchy()

        return result

    # _build_commission_hierarchy itself (and the commission_ids field it populates) moved to
    # isky_18_realestate_developer_commission/models/core/sale_proposal_crm_ext.py - it's
    # called by name above, which still resolves fine once that module is installed.
