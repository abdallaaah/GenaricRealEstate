from odoo import api, models


class ReportDiscount(models.AbstractModel):
    _name = 'report.arkzayed_18_realestate_development.report_discount'
    _description = 'Discount Review Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['discount.report.wizard'].browse(docids)[:1]
        return {
            'doc_ids': docids,
            'doc_model': 'discount.report.wizard',
            'docs': wizard,
            'd': wizard._collect(),
            'money': lambda v: '{:,.0f}'.format(v or 0.0),
            'mil': lambda v: '{:,.1f}M'.format((v or 0.0) / 1e6),
        }
