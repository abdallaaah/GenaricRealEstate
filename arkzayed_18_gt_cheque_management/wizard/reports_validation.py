from odoo import api, fields, models, _
from odoo.exceptions import ValidationError



class CustomerPaymentReportModel(models.AbstractModel):
    _name = 'report.arkzayed_18_gt_cheque_management.customer_payment_report'

    @api.model
    def _get_report_values(self, docids, data=None):
        records = self.env['account.payment'].browse(docids)

        # Check if any record is outbound payment (vendor payment)
        outbound_records = records.filtered(lambda r: r.payment_type == 'outbound')
        if outbound_records:
            raise ValidationError(
                _("Cannot print Customer Payment report for Vendor Payment records. Please use the Vendor Payment report instead."))

        return {
            'doc_ids': docids,
            'doc_model': 'account.payment',
            'docs': records,
            'data': data,
        }


class VendorPaymentReportModel(models.AbstractModel):
    _name = 'report.arkzayed_18_realestate_development.voucher_payment_report'

    @api.model
    def _get_report_values(self, docids, data=None):
        records = self.env['account.payment'].browse(docids)

        # Check if any record is inbound payment (customer payment)
        inbound_records = records.filtered(lambda r: r.payment_type == 'inbound')
        if inbound_records:
            raise ValidationError(
                _("Cannot print Voucher Payment report for Customer Payment records. Please use the Customer Payment report instead."))

        return {
            'doc_ids': docids,
            'doc_model': 'account.payment',
            'docs': records,
            'data': data,
        }


class IncomingCheckReportModel(models.AbstractModel):
    _name = 'report.arkzayed_18_gt_cheque_management.incoming_check_report'

    @api.model
    def _get_report_values(self, docids, data=None):
        records = self.env['cheque.manage'].browse(docids)

        # Check if any record is outgoing check
        outgoing_records = records.filtered(lambda r: r.cheq_type == 'outgoing')
        if outgoing_records:
            raise ValidationError(
                _("Cannot print Incoming Check report for Outgoing Check records. Please use the Outgoing Check report instead."))

        return {
            'doc_ids': docids,
            'doc_model': 'cheque.manage',
            'docs': records,
            'data': data,
        }


class OutgoingCheckReportModel(models.AbstractModel):
    _name = 'report.arkzayed_18_gt_cheque_management.outgoing_check_report'

    @api.model
    def _get_report_values(self, docids, data=None):
        records = self.env['cheque.manage'].browse(docids)

        # Check if any record is incoming check
        incoming_records = records.filtered(lambda r: r.cheq_type == 'incoming')
        if incoming_records:
            raise ValidationError(
                _("Cannot print Outgoing Check report for Incoming Check records. Please use the Incoming Check report instead."))

        return {
            'doc_ids': docids,
            'doc_model': 'cheque.manage',
            'docs': records,
            'data': data,
        }
