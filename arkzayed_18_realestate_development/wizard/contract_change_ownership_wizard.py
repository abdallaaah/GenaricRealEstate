from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ContractChangeOwnershipWizard(models.TransientModel):
    _name = "contract.change.ownership.wizard"

    contract_id = fields.Many2one('sale.proposal')
    current_customer_id = fields.Many2one('res.partner')
    new_customer_id = fields.Many2one('res.partner')

    number_of_banks = fields.Selection([
        ('1', '1'), ('2', '2'), ('3', '3'),
    ], string='Number of Banks', default='1', required=True)

    cheque_is_serial = fields.Selection([
        ('serial', 'Serial'),
        ('not_serial', 'Not Serial'),
    ], string='Cheque Numbering', default='serial', required=True)

    # ---- Bank 1 ----
    bank_id = fields.Many2one('res.bank', string='Bank 1')
    cheque_starting_number = fields.Char(string='Starting Cheque Number (Bank 1)')
    bank_1_installments_count = fields.Integer(
        string='Number of Installments (Bank 1)',
        help="Leave 0 or empty to auto-distribute the remaining cheques evenly across the selected banks."
    )

    # ---- Bank 2 ----
    bank_id_2 = fields.Many2one('res.bank', string='Bank 2')
    cheque_starting_number_2 = fields.Char(string='Starting Cheque Number (Bank 2)')
    bank_2_installments_count = fields.Integer(string='Number of Installments (Bank 2)')

    # ---- Bank 3 ----
    bank_id_3 = fields.Many2one('res.bank', string='Bank 3')
    cheque_starting_number_3 = fields.Char(string='Starting Cheque Number (Bank 3)')
    bank_3_installments_count = fields.Integer(string='Number of Installments (Bank 3)')

    def _get_bank_configs(self):
        self.ensure_one()
        is_serial = self.cheque_is_serial != 'not_serial'
        num_banks = int(self.number_of_banks or '1')

        bank_configs = []

        if num_banks >= 1:
            if not self.bank_id:
                raise ValidationError(_("Please select Bank 1."))
            if is_serial and not self.cheque_starting_number:
                raise ValidationError(_("Please enter the starting cheque number for Bank 1."))
            bank_configs.append({
                'bank_id': self.bank_id.id,
                'starting_number': self.cheque_starting_number if is_serial else False,
                'count': self.bank_1_installments_count or 0,
            })
        if num_banks >= 2:
            if not self.bank_id_2:
                raise ValidationError(_("Please select Bank 2."))
            if is_serial and not self.cheque_starting_number_2:
                raise ValidationError(_("Please enter the starting cheque number for Bank 2."))
            bank_configs.append({
                'bank_id': self.bank_id_2.id,
                'starting_number': self.cheque_starting_number_2 if is_serial else False,
                'count': self.bank_2_installments_count or 0,
            })
        if num_banks >= 3:
            if not self.bank_id_3:
                raise ValidationError(_("Please select Bank 3."))
            if is_serial and not self.cheque_starting_number_3:
                raise ValidationError(_("Please enter the starting cheque number for Bank 3."))
            bank_configs.append({
                'bank_id': self.bank_id_3.id,
                'starting_number': self.cheque_starting_number_3 if is_serial else False,
                'count': self.bank_3_installments_count or 0,
            })

        if is_serial:
            for i, config in enumerate(bank_configs):
                try:
                    config['starting_int'] = int(config['starting_number'])
                except ValueError:
                    raise ValidationError(
                        _("Starting cheque number for Bank %s must be a valid number.") % (i + 1))
        else:
            for config in bank_configs:
                config['starting_int'] = 0

        return bank_configs, is_serial

    @staticmethod
    def _distribute_counts(bank_configs, total_lines):
        specified_counts = [c['count'] for c in bank_configs]
        total_specified = sum(specified_counts)

        if total_specified > 0:
            if total_specified != total_lines:
                raise ValidationError(
                    _("Total cheques assigned to banks (%s) does not match the total number "
                      "of unpaid lines to re-issue (%s). Either make the counts add up exactly, "
                      "or leave all of them at 0 to auto-distribute evenly.")
                    % (total_specified, total_lines))
        else:
            num_banks = len(bank_configs)
            base_count = total_lines // num_banks
            remainder = total_lines % num_banks
            for i, config in enumerate(bank_configs):
                config['count'] = base_count + (1 if i < remainder else 0)

        return bank_configs

    def action_confirm(self):
        self.ensure_one()

        if not self.new_customer_id:
            raise ValidationError(_("Please select the new customer."))

        if self.new_customer_id.id == self.current_customer_id.id:
            raise ValidationError(_("You cannot change the ownership to the same customer."))

        # Validate that all change_ownership_type values are configured
        required_types = ['deferred_revenue', 'maintenance_fund', 'account_receivables']
        type_labels = {
            'deferred_revenue': 'Deferred Revenue',
            'maintenance_fund': 'Maintenance Fund',
            'account_receivables': 'Account Receivables',
        }

        configured_types = self.env['account.account'].search([
            ('change_ownership_type', 'in', required_types)
        ]).mapped('change_ownership_type')

        missing_types = [t for t in required_types if t not in configured_types]
        if missing_types:
            missing_labels = ', '.join([type_labels[t] for t in missing_types])
            raise ValidationError(
                _('The following change ownership types are not configured:\n%s\n\n'
                  'Please configure them in the Chart of Accounts before proceeding with ownership change.') % missing_labels
            )

        contract = self.contract_id

        unpaid_installment_lines = contract.installment_ids.filtered(lambda l: not l.paid)
        unpaid_maintenance_lines = contract.maintenance_installment_ids.filtered(lambda l: not l.paid)

        all_unpaid_lines = []
        for line in unpaid_installment_lines.sorted(key=lambda l: l.date or fields.Date.today()):
            all_unpaid_lines.append({'type': 'installment', 'record': line})
        for line in unpaid_maintenance_lines.sorted(key=lambda l: l.date or fields.Date.today()):
            all_unpaid_lines.append({'type': 'maintenance', 'record': line})

        contract_vals = {
            'customer_id': self.new_customer_id.id,
            'old_customer_id': self.current_customer_id.id,
            'ownership_changed': True,
            'number_of_banks': self.number_of_banks,
            'cheque_is_serial': self.cheque_is_serial,
            'bank_id': self.bank_id.id,
            'cheque_starting_number': self.cheque_starting_number,
            'bank_1_installments_count': self.bank_1_installments_count,
            'bank_id_2': self.bank_id_2.id if self.bank_id_2 else False,
            'cheque_starting_number_2': self.cheque_starting_number_2,
            'bank_2_installments_count': self.bank_2_installments_count,
            'bank_id_3': self.bank_id_3.id if self.bank_id_3 else False,
            'cheque_starting_number_3': self.cheque_starting_number_3,
            'bank_3_installments_count': self.bank_3_installments_count,
        }

        if not all_unpaid_lines:
            contract.write(contract_vals)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _(
                        "Contract ownership changed from %s to %s",
                        self.current_customer_id.name, self.new_customer_id.name
                    ),
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }

        journal_param = self.env["ir.config_parameter"].sudo().get_param(
            "arkzayed_18_gt_cheque_management.journal_id")
        if not journal_param:
            raise ValidationError(_("Please configure the cheque journal in settings."))
        journal = self.env['account.journal'].browse(int(journal_param))
        if not journal.exists():
            raise ValidationError(_("The configured cheque journal does not exist."))

        self.create_ownership_journals()

        bank_configs, is_serial = self._get_bank_configs()
        total_lines = len(all_unpaid_lines)
        bank_configs = self._distribute_counts(bank_configs, total_lines)

        new_cheques = self.env['cheque.manage']

        current_idx = 0
        for config in bank_configs:
            cheque_counter = 0
            for _i in range(config['count']):
                if current_idx >= total_lines:
                    break

                data = all_unpaid_lines[current_idx]
                ch_type = data['type']
                line = data['record']

                pending_allocations = line.allocation_ids.filtered(
                    lambda a: (a.cheque_id and a.cheque_id.state != 'done')
                    or (a.payment_id and a.payment_id.state != 'paid')
                )
                old_cheques = pending_allocations.mapped('cheque_id')
                old_payments = pending_allocations.mapped('payment_id')

                for payment in old_payments:
                    self._reverse_payment(payment)

                for cheque in old_cheques:
                    self._reverse_cheque(cheque)

                pending_allocations.unlink()

                if old_cheques:
                    current_cheque_number = (
                        str(config['starting_int'] + cheque_counter) if is_serial else False
                    )
                    new_cheque = self.env['cheque.manage'].create({
                        'name': _('%s - %s %s') % (contract.name, ch_type.title(), current_idx + 1),
                        'cheque_no': current_cheque_number,
                        'payer': self.new_customer_id.id,
                        'bank_id': config['bank_id'],
                        'cheq_type': 'incoming',
                        'amount': line.remaining_amount,
                        'cheque_date': line.date,
                        'cheque_receive_date': fields.Date.today(),
                        'journal_id': journal.id,
                        'state': 'draft',
                        'description': line.name or '',
                        'source_type': ch_type,
                        'unit_id': contract.unit_id.id,
                        'sale_proposal_id': contract.id,
                    })
                    new_cheques |= new_cheque
                    self.env['payment.allocation'].create({
                        'cheque_id': new_cheque.id,
                        'installment_id': line.id if ch_type == 'installment' else False,
                        'maintenance_id': line.id if ch_type == 'maintenance' else False,
                        'allocated_amount': line.remaining_amount,
                    })

                current_idx += 1
                cheque_counter += 1

        contract.write(contract_vals)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _(
                    "Contract ownership changed from %s to %s. %s cheque(s) reversed and re-issued across %s bank(s).",
                    self.current_customer_id.name, self.new_customer_id.name, len(new_cheques), self.number_of_banks
                ),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def create_ownership_journals(self):
        """Create journal entry for ownership change: Deferred Revenue and Accounts Receivable."""
        self.ensure_one()

        ownership_accounts = self.env['account.account'].search([
            ('change_ownership_type', '!=', False),
        ])

        deferred_revenue_account = ownership_accounts.filtered(lambda a: a.change_ownership_type == 'deferred_revenue')
        maintenance_fund_account = ownership_accounts.filtered(lambda a: a.change_ownership_type == 'maintenance_fund')
        account_receivables_account = ownership_accounts.filtered(
            lambda a: a.change_ownership_type == 'account_receivables')

        contract = self.contract_id
        move_lines = []

        # Get the journal for creating the move
        journal = self.env['account.journal'].search([('type', '=', 'general')], limit=1)
        if not journal:
            raise ValidationError(_("No general journal found to create entries."))

        # Deferred Revenue entries (using the unit's total price)
        if deferred_revenue_account and contract.unit_price:
            # Debit: Deferred Revenue (old partner)
            move_lines.append((0, 0, {
                'account_id': deferred_revenue_account.id,
                'debit': contract.unit_price,
                'credit': 0,
                'partner_id': self.current_customer_id.id,
                'name': _('Deferred Revenue - Old Partner - %s') % contract.name,
            }))

            # Credit: Deferred Revenue (new partner)
            move_lines.append((0, 0, {
                'account_id': deferred_revenue_account.id,
                'debit': 0,
                'credit': contract.unit_price,
                'partner_id': self.new_customer_id.id,
                'name': _('Deferred Revenue - New Partner - %s') % contract.name,
            }))

        # Maintenance Fund entries (using the maintenance amount)
        if maintenance_fund_account and contract.maintenance_price:
            # Debit: Maintenance Fund (old partner)
            move_lines.append((0, 0, {
                'account_id': maintenance_fund_account.id,
                'debit': contract.maintenance_price,
                'credit': 0,
                'partner_id': self.current_customer_id.id,
                'name': _('Maintenance Fund - Old Partner - %s') % contract.name,
            }))

            # Credit: Maintenance Fund (new partner)
            move_lines.append((0, 0, {
                'account_id': maintenance_fund_account.id,
                'debit': 0,
                'credit': contract.maintenance_price,
                'partner_id': self.new_customer_id.id,
                'name': _('Maintenance Fund - New Partner - %s') % contract.name,
            }))

        # Account Receivable entries (using the remaining unpaid installments amount,
        # including maintenance installments)
        remaining_installments_amount = sum(contract.installment_ids.mapped('remaining_amount')) + \
            sum(contract.maintenance_installment_ids.mapped('remaining_amount'))

        if account_receivables_account and remaining_installments_amount:
            # Debit: Account Receivable (new partner)
            move_lines.append((0, 0, {
                'account_id': account_receivables_account.id,
                'debit': remaining_installments_amount,
                'credit': 0,
                'partner_id': self.new_customer_id.id,
                'name': _('Account Receivable - New Partner - %s') % contract.name,
            }))

            # Credit: Account Receivable (old partner)
            move_lines.append((0, 0, {
                'account_id': account_receivables_account.id,
                'debit': 0,
                'credit': remaining_installments_amount,
                'partner_id': self.current_customer_id.id,
                'name': _('Account Receivable - Old Partner - %s') % contract.name,
            }))

        # Create the journal entry if there are lines
        if move_lines:
            move_ref = _('Ownership Change - %s') % contract.name
            move_vals = {
                'journal_id': journal.id,
                'date': fields.Date.today(),
                'name': move_ref,
                'ref': move_ref,
                'line_ids': move_lines,
            }
            move = self.env['account.move'].create(move_vals)
            move.action_post()

            # Save the journal move to the contract
            contract.write({'ownership_change_journal_id': move.id})

            return move

    def _reverse_cheque(self, cheque):
        if cheque.move_line_ids:
            moves = cheque.move_line_ids.mapped('move_id').filtered(lambda m: m.state == 'posted')
            if moves:
                default_values_list = [{
                    'date': fields.Date.today(),
                    'ref': _('Reversal - Ownership Change - %s') % cheque.seq_no,
                } for _move in moves]

                moves._reverse_moves(default_values_list, cancel=True)

        cheque.write({'state': 'cancel'})

    def _reverse_payment(self, payment):
        if payment.state != 'canceled':
            payment.action_cancel()