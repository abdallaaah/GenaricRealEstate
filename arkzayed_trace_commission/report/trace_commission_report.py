from odoo import api, models


class ReportTraceCommission(models.AbstractModel):
    _name = 'report.arkzayed_trace_commission.tc_report'
    _description = 'Trace Commission report'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['trace.commission'].browse(docids)[:1]
        return {'doc_ids': docids, 'doc_model': 'trace.commission', 'docs': wizard, 'd': wizard._report_data()}
