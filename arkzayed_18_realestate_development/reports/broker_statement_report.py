from odoo import api, models


class ReportBrokerStatement(models.AbstractModel):
    _name = 'report.arkzayed_18_realestate_development.broker_statement'
    _description = 'Broker / Ambassador Commission Statement'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['broker.claim.statement.wizard'].browse(docids)[:1]
        return {
            'doc_ids': docids,
            'doc_model': 'broker.claim.statement.wizard',
            'docs': wizard,
            'd': wizard._collect(),
            'fmt': lambda v: '{:,.2f}'.format(v or 0.0),
        }
