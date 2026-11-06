from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SaleProposal(models.Model):
    """Cheque half of sale.proposal, including the whole cheque-generation subsystem. Moved
    out of sales_crm in Phase 3 step 3 (supplement S1)."""
    _inherit = 'sale.proposal'

    # Add these fields to the SaleProposal class
    cheque_is_serial = fields.Selection([
        ('serial', 'Serial'),
        ('not_serial', 'Not Serial'),
    ], string='Cheque Numbering', default='serial',
        help='If Serial, cheques will be numbered sequentially from the starting number. '
             'If Not Serial, cheques will be created without cheque numbers.')
    number_of_banks = fields.Selection([
        ('1', '1'),
        ('2', '2'),
        ('3', '3'),
    ], string='Number of Banks', default='1')

    cheque_starting_number = fields.Char(string='Starting Cheque Number (Bank 1)')
    bank_id = fields.Many2one('res.bank', string='Bank 1')
    bank_1_installments_count = fields.Integer(
        string='Number of Installments (Bank 1)',
        help='Number of installments to assign to Bank 1. Leave 0 or empty to auto-distribute.')

    cheque_starting_number_2 = fields.Char(string='Starting Cheque Number (Bank 2)')
    bank_id_2 = fields.Many2one('res.bank', string='Bank 2')
    bank_2_installments_count = fields.Integer(
        string='Number of Installments (Bank 2)',
        help='Number of installments to assign to Bank 2. Leave 0 or empty to auto-distribute.')

    cheque_starting_number_3 = fields.Char(string='Starting Cheque Number (Bank 3)')
    bank_id_3 = fields.Many2one('res.bank', string='Bank 3')
    bank_3_installments_count = fields.Integer(
        string='Number of Installments (Bank 3)',
        help='Number of installments to assign to Bank 3. Leave 0 or empty to auto-distribute.')

    cheque_ids = fields.One2many('cheque.manage', 'sale_proposal_id', string='Cheques')
    # Cheques whose MAIN contract is another one but that settle installments of
    # THIS contract through allocations (multi-contract customer cheques).
    linked_cheque_ids = fields.Many2many(
        'cheque.manage',
        string='Linked Cheques',
        compute='_compute_linked_cheque_ids',
    )
    cheque_count = fields.Integer(string='Cheque Count', compute='_compute_cheque_count')
    # --- S6 compute extensions -------------------------------------------------------------

    @api.depends(
        'eoi_id',
        'eoi_id.account_payment_ids.state',
        'eoi_id.account_payment_ids.amount',
        'eoi_id.account_payment_ids.payment_type',
        'eoi_id.cheque_manage_ids.state',
        'eoi_id.cheque_manage_ids.amount',
        'eoi_id.cheque_manage_ids.cheq_type',
    )
    def _compute_eoi_amount(self):
        return super()._compute_eoi_amount()

    @api.depends(
        'installment_ids.allocation_ids.cheque_id',
        'maintenance_installment_ids.allocation_ids.cheque_id',
        'cheque_ids',
    )
    def _compute_linked_cheque_ids(self):
        for rec in self:
            allocated_cheques = (
                rec.installment_ids.mapped('allocation_ids.cheque_id')
                | rec.maintenance_installment_ids.mapped('allocation_ids.cheque_id')
            )
            rec.linked_cheque_ids = allocated_cheques - rec.cheque_ids

    @api.depends('cheque_ids', 'linked_cheque_ids')
    def _compute_cheque_count(self):
        for rec in self:
            rec.cheque_count = len(rec.cheque_ids | rec.linked_cheque_ids)
    # --- cheque hooks declared in sales_crm ------------------------------------------------

    def _eoi_cheque_amount(self):
        if not self.eoi_id:
            return 0.0
        valid_cheques = self.eoi_id.cheque_manage_ids.filtered(
            lambda c: c.cheq_type == 'incoming' and c.state not in ('cancel', 'return_to_client',
                                                                    'return', 'bounce') and c.from_eoi == True
        )
        return sum(valid_cheques.mapped('amount'))

    def _line_cheque_info(self, installment):
        EXCLUDED_CHEQUE_STATES = ('cancel', 'return', 'return_to_client', 'bounce')
        cheque = installment.allocation_ids.mapped('cheque_id').filtered(
            lambda c: c.state not in EXCLUDED_CHEQUE_STATES)[:1]
        return {
            'cheque_no': cheque.cheque_no if cheque else '',
            'bank_name': cheque.bank_id.name if cheque and cheque.bank_id else '',
            'has_cheque': bool(cheque),
        }

    def _cheque_fund_entries(self, foreign_chq_snap, line_type):
        entries = super()._cheque_fund_entries(foreign_chq_snap, line_type)

        foreign_cheques = self.env['cheque.manage'].browse(list(foreign_chq_snap.keys())).exists()
        for c in foreign_cheques:
            pool = foreign_chq_snap.get(c.id, 0.0)
            if pool <= 0.0001:
                continue
            entries.append({
                'type': 'cheque',
                'alloc_field': 'cheque_id',
                'record': c,
                'date': c.cheque_date or c.cheque_receive_date or fields.Date.today(),
                'remaining_pool': pool,
                'priority': 0,
            })

        active_cheques = self.cheque_ids.filtered(
            lambda c: c.state in ('register', 'collect', 'done', 'under_collection', 'return', 'bounce')
        )
        for c in active_cheques:
            pool = c.amount - self._payment_amount_held_outside(c, line_type)
            if pool <= 0.0001:
                continue
            entries.append({
                'type': 'cheque',
                'alloc_field': 'cheque_id',
                'record': c,
                'date': c.cheque_date or c.cheque_receive_date or fields.Date.today(),
                'remaining_pool': pool,
                'priority': 1,
            })
        return entries

    # --- the cheque-generation subsystem, moved verbatim from sales_crm --------------------

    # ----------------------------------------------------------------------------------
    # S8: the sales-linked cheque toggle (res.company.cheques_enabled).
    #
    # Gates generation of cheques *from a deal* only. Manual cheque use - registering one
    # against an installment line, a maintenance line, an EOI or a reservation - is
    # deliberately not gated.
    # ----------------------------------------------------------------------------------

    def _check_cheque_generation_enabled(self):
        """Refuse to generate cheques from a deal when the company has the toggle off."""
        self.ensure_one()
        company = self.company_id or self.env.company
        if not company.cheques_enabled:
            raise UserError(_(
                "Generating cheques from a deal is turned off for this company.\n\n"
                "Turn on 'Generate Cheques from Deals' in Settings > Real Estate Cheques > "
                "Sales Setup, or register the cheque against the installment line by hand."
            ))

    def action_create_cheques(self):
        """Step 1: Validate data, compile lines that still need coverage, and open the wizard"""
        self.ensure_one()
        self._check_cheque_generation_enabled()

        if not self.installment_ids and not self.maintenance_installment_ids:
            raise ValidationError(_("No installment or maintenance lines found. Please calculate installments first."))

        # Helper to calculate how much of the line is still uncovered
        def _get_uncovered(line):
            covered = 0.0
            for alloc in line.allocation_ids:
                if alloc.payment_id and alloc.payment_id.state not in ('canceled', 'rejected'):
                    covered += alloc.allocated_amount
                elif alloc.cheque_id and alloc.cheque_id.state not in ('cancel', 'return', 'return_to_client',
                                                                       'bounce'):
                    covered += alloc.allocated_amount

            line_total = line.total_amount if line.total_amount else line.amount
            return max(0.0, line_total - covered)

        # Filter lines that still have an uncovered amount > 0
        unpaid_insts = self.installment_ids.filtered(lambda x: _get_uncovered(x) > 0.0)
        unpaid_maints = self.maintenance_installment_ids.filtered(lambda x: _get_uncovered(x) > 0.0)

        if not unpaid_insts and not unpaid_maints:
            raise ValidationError(_("All lines are already fully covered by existing cheques or payments."))

        # Check for missing dates
        if unpaid_insts.filtered(lambda x: not x.date):
            missing_names = ', '.join(unpaid_insts.filtered(lambda x: not x.date).mapped('name') or ['Unnamed'])
            raise ValidationError(
                _("All installment lines must have a date before creating cheques.\n"
                  "The following installment(s) are missing dates: %s") % missing_names
            )

        if unpaid_maints.filtered(lambda x: not x.date):
            missing_names = ', '.join(unpaid_maints.filtered(lambda x: not x.date).mapped('name') or ['Unnamed'])
            raise ValidationError(
                _("All maintenance installment lines must have a date before creating cheques.\n"
                  "The following maintenance installment(s) are missing dates: %s") % missing_names
            )

        # Validate Bank Configurations
        is_serial = self.cheque_is_serial != 'not_serial'
        num_banks = int(self.number_of_banks or '1')

        if num_banks >= 1:
            if not self.bank_id:
                raise ValidationError(_("Please select Bank 1."))
            if is_serial and not self.cheque_starting_number:
                raise ValidationError(_("Please enter the starting cheque number for Bank 1."))
        if num_banks >= 2:
            if not self.bank_id_2:
                raise ValidationError(_("Please select Bank 2."))
            if is_serial and not self.cheque_starting_number_2:
                raise ValidationError(_("Please enter the starting cheque number for Bank 2."))
        if num_banks >= 3:
            if not self.bank_id_3:
                raise ValidationError(_("Please select Bank 3."))
            if is_serial and not self.cheque_starting_number_3:
                raise ValidationError(_("Please enter the starting cheque number for Bank 3."))

        # 1. Create the base Wizard record
        wizard = self.env['sale.proposal.cheque.wizard'].create({
            'sale_proposal_id': self.id
        })

        # 2. Combine and sort all lines that need coverage chronologically
        combined = []
        for i in unpaid_insts: combined.append(('installment', i))
        for m in unpaid_maints: combined.append(('maintenance', m))
        # Priority 0: 'installment', Priority 1: 'maintenance'
        combined.sort(key=lambda x: (
            0 if x[0] == 'installment' else 1,
            x[1].date is False,
            x[1].date or fields.Date.max
        ))
        # 3. Create Wizard Lines attached to the Wizard
        for idx, (ltype, line) in enumerate(combined):
            uncovered_amt = _get_uncovered(line)
            self.env['sale.proposal.cheque.wizard.line'].create({
                'wizard_id': wizard.id,
                'name': f"{idx + 1}. {line.date} | {line.name} | Amount: {uncovered_amt:,.2f}",
                'line_type': ltype,
                'installment_id': line.id if ltype == 'installment' else False,
                'maintenance_id': line.id if ltype == 'maintenance' else False,
            })

        # 4. Open the specific Wizard record we just built
        return {
            'name': _('Select Starting Cheque Line'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.proposal.cheque.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def action_open_combined_cheque_wizard(self):
        """Open the Combined Cheque wizard (one cheque covering installments of several
        of this customer's contracts)."""
        self.ensure_one()
        self._check_cheque_generation_enabled()
        return {
            'name': _('Combined Cheque'),
            'type': 'ir.actions.act_window',
            'res_model': 'combined.cheque.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sale_proposal_id': self.id},
        }

    def _generate_cheques(self, starting_line_key):
        """Step 2: Called by the wizard to generate cheques based on the missing balance"""
        self.ensure_one()
        self._check_cheque_generation_enabled()

        is_serial = self.cheque_is_serial != 'not_serial'
        num_banks = int(self.number_of_banks or '1')

        # Get Journal
        journal_param = self.env["ir.config_parameter"].sudo().get_param("arkzayed_18_gt_cheque_management.journal_id")
        journal = self.env['account.journal'].browse(int(journal_param))

        # Helper to calculate how much of the line is still uncovered
        def _get_uncovered(line):
            covered = 0.0
            for alloc in line.allocation_ids:
                if alloc.payment_id and alloc.payment_id.state not in ('canceled', 'rejected'):
                    covered += alloc.allocated_amount
                elif alloc.cheque_id and alloc.cheque_id.state not in ('cancel', 'return', 'return_to_client',
                                                                       'bounce'):
                    covered += alloc.allocated_amount

            line_total = line.total_amount if line.total_amount else line.amount
            return max(0.0, line_total - covered)

        # Get lines that still need coverage
        unpaid_insts = self.installment_ids.filtered(lambda x: _get_uncovered(x) > 0.01)
        unpaid_maints = self.maintenance_installment_ids.filtered(lambda x: _get_uncovered(x) > 0.01)

        # Build chronological list
        installments_list = []
        for inst in unpaid_insts.sorted(key=lambda x: x.date):
            installments_list.append({
                'type': 'installment', 'record': inst, 'date': inst.date,
                'amount': _get_uncovered(inst), 'name': inst.name, 'key': f"installment_{inst.id}"
            })

        maintenance_list = []
        for maint in unpaid_maints.sorted(key=lambda x: x.date):
            maintenance_list.append({
                'type': 'maintenance', 'record': maint, 'date': maint.date,
                'amount': _get_uncovered(maint), 'name': maint.name, 'key': f"maintenance_{maint.id}"
            })

        all_installments = installments_list + maintenance_list

        # Priority 0: 'installment', Priority 1: 'maintenance'
        all_installments.sort(key=lambda x: (
            0 if x['type'] == 'installment' else 1,
            x['date'] is False,
            x['date'] or fields.Date.max
        ))

        # Find starting index based on the user's wizard selection
        start_idx = 0
        for idx, line in enumerate(all_installments):
            if line['key'] == starting_line_key:
                start_idx = idx
                break

        # Slice the array: Only generate cheques from the start index onwards
        target_installments = all_installments[start_idx:]
        total_installments = len(target_installments)

        if total_installments == 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Nothing to Generate'),
                    'message': _('There are no remaining installments to generate cheques for.'),
                    'type': 'warning',
                    'sticky': False,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }

        # Prepare Bank Configs
        bank_configs = []
        if num_banks >= 1:
            bank_configs.append(
                {'bank_id': self.bank_id.id, 'starting_number': self.cheque_starting_number if is_serial else False,
                 'count': self.bank_1_installments_count or 0})
        if num_banks >= 2:
            bank_configs.append(
                {'bank_id': self.bank_id_2.id, 'starting_number': self.cheque_starting_number_2 if is_serial else False,
                 'count': self.bank_2_installments_count or 0})
        if num_banks >= 3:
            bank_configs.append(
                {'bank_id': self.bank_id_3.id, 'starting_number': self.cheque_starting_number_3 if is_serial else False,
                 'count': self.bank_3_installments_count or 0})

        # Validate numbers and convert to integer
        if is_serial:
            for i, config in enumerate(bank_configs):
                config['starting_int'] = int(config['starting_number'])
        else:
            for config in bank_configs:
                config['starting_int'] = 0

        # Adjust Counts Distribution
        specified_counts = [c['count'] for c in bank_configs]
        total_specified = sum(specified_counts)

        if total_specified > 0:
            if total_specified > total_installments:
                raise ValidationError(
                    _("Total installments assigned to banks (%s) exceeds the total number of remaining installments (%s).") % (
                        total_specified, total_installments))

            # If total specified is less than total, distribute remaining to last bank
            if total_specified < total_installments:
                bank_configs[-1]['count'] += (total_installments - total_specified)
        else:
            base_count = total_installments // num_banks
            remainder = total_installments % num_banks
            for i, config in enumerate(bank_configs):
                config['count'] = base_count + (1 if i < remainder else 0)

        created_cheques = self.env['cheque.manage']

        current_idx = 0
        inst_count = 0
        maint_count = 0

        # Generate Cheques
        for bank_idx, config in enumerate(bank_configs):
            cheque_counter = 0
            for _i in range(config['count']):
                if current_idx >= total_installments:
                    break

                inst_data = target_installments[current_idx]
                inst_record = inst_data['record']
                inst_type = inst_data['type']

                if is_serial:
                    current_cheque_number = str(config['starting_int'] + cheque_counter)
                else:
                    current_cheque_number = False

                cheque_vals = {
                    'name': _('%s - %s %s') % (self.name, inst_type.title(), current_idx + 1),
                    'cheque_no': current_cheque_number,
                    'payer': self.customer_id.id,
                    'bank_id': config['bank_id'],
                    'cheq_type': 'incoming',
                    'amount': inst_data['amount'],
                    'cheque_date': inst_data['date'],
                    'cheque_receive_date': fields.Date.today(),
                    'journal_id': journal.id,
                    'state': 'draft',
                    'description': inst_data['name'] or '',
                    'source_type': inst_type,
                    'unit_id': self.unit_id.id,
                    'sale_proposal_id': self.id,
                    'from_contract': True,
                }

                # Link directly to the correct One2Many line via the line ID
                if inst_type == 'installment':
                    inst_count += 1
                elif inst_type == 'maintenance':
                    maint_count += 1

                # Create the cheque
                cheque = self.env['cheque.manage'].create(cheque_vals)
                created_cheques |= cheque

                # Create the allocation bridging the cheque to the installment
                self.env['payment.allocation'].create({
                    'cheque_id': cheque.id,
                    'installment_id': inst_record.id if inst_type == 'installment' else False,
                    'maintenance_id': inst_record.id if inst_type == 'maintenance' else False,
                    'allocated_amount': inst_data['amount']
                })

                # Update line metadata
                inst_record.write({'payment_method_used': 'cheque'})

                current_idx += 1
                cheque_counter += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _(
                    '%s cheque(s) created successfully (%s installment + %s maintenance) across %s bank(s).') % (
                               len(created_cheques),
                               inst_count,
                               maint_count,
                               num_banks
                           ),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }


    def action_view_cheques(self):
        """View cheques related to this proposal (own + multi-contract linked)."""
        self.ensure_one()
        return {
            'name': _('Cheques'),
            'type': 'ir.actions.act_window',
            'res_model': 'cheque.manage',
            'view_mode': 'list,form',
            'domain': [('id', 'in', (self.cheque_ids | self.linked_cheque_ids).ids)],
            'context': {
            'default_sale_proposal_id': self.id,
            'group_by': 'source_type',
            'default_cheq_type': 'incoming',
            }
        }
