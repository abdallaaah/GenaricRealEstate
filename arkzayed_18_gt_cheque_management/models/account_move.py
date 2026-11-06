from num2words import num2words

from odoo import models, fields


class AccountMove(models.Model):
    """Cash in/out statement feature.

    Phase 2b: moved here from isky_18_realestate_developer_accounting (the L1 accounting
    bridge). It belongs in this module because `action_cash_in_out_statement` resolves
    `arkzayed_18_gt_cheque_management.account_cash_in_out_report`, whose report action and
    QWeb template live here - while the bridge did not (and per S1 must not) depend on this
    module. The four helper methods below are called only by that report's template.
    """
    _inherit = 'account.move'

    journal_type = fields.Selection(
        related='journal_id.type',
        string='Journal Type',
        store=True,
        readonly=True
    )

    def action_cash_in_out_statement(self):
        return self.env.ref('arkzayed_18_gt_cheque_management.account_cash_in_out_report').report_action(self)

    def is_receipt(self):
        """
        Check if the move is a receipt based on the journal type.

        :return: True if the journal type is 'bank_receipt', otherwise False.
        """
        for line in self.line_ids:
            if line.account_id.account_type == 'asset_cash':
                return line.amount_currency >= 0

    def _get_arabic_amount(self, amount, lang):
        return num2words(float(abs(amount)), lang=lang)

    def calculate_total_amount(self):
        """
        Calculate the total amount_currency for lines with account_type 'asset_cash'.

        :return: The total amount_currency for 'asset_cash' account type.
        """
        total_amount = 0
        for line in self.line_ids:
            if line.account_id.account_type == 'asset_cash':
                total_amount += abs(line.amount_currency)
        return total_amount

    def get_currency_name(self):
        """
        Retrieve the currency name for lines with account_type 'asset_cash'.

        :return: The currency name if found, otherwise None.
        """
        if self.line_ids:
            for line in self.line_ids:
                if line.account_id.account_type == 'asset_cash' and line.currency_id:
                    return line.currency_id.name
        return None
