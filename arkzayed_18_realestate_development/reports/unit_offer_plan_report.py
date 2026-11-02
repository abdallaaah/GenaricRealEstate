from odoo import api, models


class ReportUnitOfferPlan(models.AbstractModel):
    _name = 'report.arkzayed_18_realestate_development.unit_offer_tmpl'
    _description = 'Unit Offer Plan'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        ids = docids or data.get('doc_ids') or self.env.context.get('active_ids') or []
        return {'doc_ids': ids, 'doc_model': 'real.estate.unit',
                'docs': self.env['real.estate.unit'].browse(ids), 'template_ids': data.get('template_ids')}
