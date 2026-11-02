from odoo import models, _
from odoo.exceptions import UserError


class OutgoingChequeReport(models.AbstractModel):
    _name = 'report.arkzayed_18_gt_cheque_management.outgoing_check_report'

    def _get_report_values(self, docids, data=None):
        docs = self.env['cheque.manage'].browse(docids)
        for doc in docs:
            if doc.state == 'draft':
                raise UserError(_('You cann\'t print draft cheques'))
            if doc.cheq_type != 'outgoing':
                raise UserError(_('You can only print vouchers for outgoing cheques.'))

        return {
            'doc_ids': docids,
            'doc_model': 'cheque.manage',
            'docs': docs,
        }