from odoo import api, fields, models


class AccountReconcileWizard(models.TransientModel):
    _inherit = 'account.reconcile.wizard'

    # --- from arkzayed_18_vendor_bill/wizard/account_reconcile_wizard.py ---
    reconciliation_mode = fields.Selection([
        ('original', 'Original'),
        ('construction', 'Construction')
    ], string='Reconciliation Mode', default='original', required=True,
        help='Original: Standard reconciliation. Construction: Apply percentage-based reconciliation.')

    reconciliation_percentage = fields.Float(
        string='Reconciliation Percentage',
        default=0.0,
        help='Percentage to apply when reconciling payments for this partner'
    )

    original_payment_amount = fields.Monetary(
        string='Original Payment Amount',
        currency_field='reco_currency_id',
        readonly=True,
        help='Stores the total of non-insurance bill lines before applying percentage'
    )

    @api.depends('company_id')
    def _compute_journal_id(self):
        """Force the write-off move of a vendor-bill reconciliation into the
        journal flagged with ``is_reconcile_journal`` so the move's ``name``
        continues that journal's sequence (e.g. PBNK/2026/00007)."""
        super()._compute_journal_id()
        for wizard in self:
            if any(line.move_id.move_type == 'in_invoice' for line in wizard.move_line_ids):
                reconcile_journal = self.env['account.journal']._get_reconcile_journal(wizard.company_id)
                if reconcile_journal:
                    wizard.journal_id = reconcile_journal

    @api.model
    def default_get(self, fields_list):
        """Override to set reconciliation_percentage from partner and store original bill amount"""
        res = super().default_get(fields_list)

        # Get move_line_ids to determine the partner and original amount
        move_line_ids = self.env['account.move.line']

        if 'move_line_ids' in res:
            # Extract IDs from Command.set format: [(6, 0, [ids])]
            for cmd in res.get('move_line_ids', []):
                if cmd[0] == 6:  # Command.set
                    move_line_ids = self.env['account.move.line'].browse(cmd[2])
                    break

        if move_line_ids:
            # Set reconciliation percentage from partner based on building
            if 'reconciliation_percentage' in fields_list:
                partners = move_line_ids.mapped('partner_id')
                # Only set default if all lines have the same partner
                if len(partners) == 1:
                    # Get the building from the bill
                    bill_lines = move_line_ids.filtered(
                        lambda l: l.move_id.move_type in ('out_invoice', 'in_invoice', 'out_refund', 'in_refund')
                    )

                    if bill_lines:
                        move = bill_lines[0].move_id
                        building_id = move.building_id.id if move.building_id else False

                        # Get percentage based on building
                        percentage = partners.get_reconciliation_percentage(building_id)
                        if percentage:
                            res['reconciliation_percentage'] = percentage

            # Store the original bill amount (sum of non-insurance lines with taxes)
            if 'original_payment_amount' in fields_list:
                # Find the bill/invoice lines (from moves with invoice origin)
                bill_lines = move_line_ids.filtered(
                    lambda l: l.move_id.move_type in ('out_invoice', 'in_invoice', 'out_refund', 'in_refund')
                )

                # If no lines with explicit move_type, filter out bank/cash journal lines
                if not bill_lines:
                    bill_lines = move_line_ids.filtered(
                        lambda l: l.journal_id.type not in ('bank', 'cash')
                    )

                if bill_lines:
                    # Get the move (invoice/bill) from the lines
                    moves = bill_lines.mapped('move_id')

                    if moves:
                        # Take the first move (they should all be from the same reconciliation)
                        move = moves[0]

                        # Calculate total of non-insurance invoice lines (with taxes)
                        total_amount = 0.0
                        for invoice_line in move.invoice_line_ids:
                            # Only sum lines that are NOT insurance products
                            if not invoice_line.is_insurance_product and not invoice_line.product_id.deduction:
                                # Use price_total to include taxes
                                total_amount += invoice_line.price_total

                        res['original_payment_amount'] = abs(total_amount)

        return res

    @api.depends('move_line_ids', 'original_payment_amount', 'reconciliation_percentage', 'reconciliation_mode')
    def _compute_reco_wizard_data(self):
        """Override to apply reconciliation percentage to payment amount"""
        # Call the parent method first
        res = super()._compute_reco_wizard_data()

        for wizard in self:
            # Only apply percentage if mode is 'construction' and we have the required data
            if (wizard.reconciliation_mode == 'construction' and
                    wizard.original_payment_amount and
                    wizard.reconciliation_percentage and
                    not wizard.edit_mode):

                # Calculate the percentage of the payment amount (always positive)
                percentage_amount = (wizard.reconciliation_percentage / 100.0) * wizard.original_payment_amount

                # Update the amount_currency (always positive)
                wizard.amount_currency = percentage_amount

                # Also update the company currency amount proportionally
                if wizard.amount and wizard.reco_currency_id:
                    # Calculate the exchange rate from the original amounts
                    original_amount_currency = wizard.amount_currency + (
                            (wizard.reconciliation_percentage / 100.0 - 1.0) * wizard.original_payment_amount
                    )
                    if original_amount_currency:
                        rate = wizard.amount / original_amount_currency
                        wizard.amount = wizard.amount_currency * rate

        return res

    @api.depends('original_payment_amount', 'reconciliation_percentage', 'reconciliation_mode')
    def _compute_edit_mode_amount_currency(self):
        """Override to apply reconciliation percentage in edit mode (single line)"""
        res = super()._compute_edit_mode_amount_currency()

        for wizard in self:
            # Only apply percentage if mode is 'construction' and we're in edit mode
            if (wizard.reconciliation_mode == 'construction' and
                    wizard.edit_mode and
                    wizard.original_payment_amount and
                    wizard.reconciliation_percentage):
                # Apply percentage to the ORIGINAL payment amount (always positive)
                percentage_amount = (wizard.reconciliation_percentage / 100.0) * wizard.original_payment_amount
                wizard.edit_mode_amount_currency = percentage_amount

        return res

    @api.onchange('reconciliation_percentage', 'reconciliation_mode')
    def _onchange_reconciliation_percentage(self):
        """Recalculate amounts when percentage or mode changes"""
        # Trigger recomputation of the relevant fields
        if self.edit_mode:
            self._compute_edit_mode_amount_currency()
        else:
            self._compute_reco_wizard_data()
