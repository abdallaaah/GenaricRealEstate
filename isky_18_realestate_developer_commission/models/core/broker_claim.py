from odoo import models, fields, _, api
from odoo.exceptions import UserError, ValidationError
from io import BytesIO
import base64
import xlsxwriter

class BrokerClaim(models.Model):
    """Broker commission details for unit"""
    _name = "broker.claim"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _description = 'Broker Claim'

    name = fields.Char(
        string='Contract Reference',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default='New'
    )
    broker_company = fields.Many2one(
        'res.partner',
        string='Broker Company',
        required=True,
        tracking=True
    )
    claim_type = fields.Selection([
        ('broker', 'Broker'),
        ('ambassador', 'Ambassador'),
        ('agent', 'Agent'),
        ('employee', 'Non-Sales Employee'),
    ], string='Claim Type', default='broker', tracking=True, required=True)
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        tracking=True,
        help="The employee this non-sales commission claim was generated for."
    )
    parent_claim_id = fields.Many2one(
        'broker.claim',
        string='Split From',
        readonly=True,
        copy=False,
        help="The broker/ambassador claim this agent's extra commission is linked to."
    )
    agent_claim_ids = fields.One2many('broker.claim', 'parent_claim_id', string='Agent Claims')
    parent_broker_id = fields.Many2one(
        'res.partner',
        string='Broker',
        related='parent_claim_id.broker_company',
        store=True,
        help="The broker/ambassador this agent's commission was from."
    )
    unit_id = fields.Many2one(
        'real.estate.unit',
        string='Unit',
        required=True,
        tracking=True
    )
    available_unit_ids = fields.Many2many(
        'real.estate.unit',
        compute='_compute_available_unit_ids',
        help='Units that have a contract referred by the selected broker/ambassador. '
             'Used to restrict the Unit field on the form.'
    )
    sale_proposal_id = fields.Many2one(
        'sale.proposal',
        string='Contract',
        tracking=True
    )
    unit_sold_price = fields.Float(
        'Unit Sold Price',
        required=True,
        tracking=True
    )
    commission = fields.Float(
        'Commission %',
        required=True,
        tracking=True
    )
    commission_amount = fields.Float(
        'Commission Amount',
        compute='_compute_commission_amount',
        store=True,
        tracking=True
    )
    collection_percentage = fields.Float(
        'Collection %',
        help='Percentage of unit price collected when claim was created',
        tracking=True
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ], default='draft', string='Status', tracking=True)

    payment_date = fields.Date('Payment Date', tracking=True)
    payment_id = fields.Many2one(
        'account.payment',
        string='Payment',
        readonly=True,
        tracking=True,
        copy=False
    )
    journal_entry_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        readonly=True,
        tracking=True,
        copy=False
    )
    notes = fields.Text('Notes')

    paid_outside_system = fields.Boolean(
        string='Paid Outside System',
        copy=False,
        tracking=True,
        help='Commission for an old contract that was already paid before this system was in use. '
             'Marking this sets the claim to Paid without creating a payment record.'
    )
    paid_outside_system_note = fields.Char(
        string='Paid Outside System Reference',
        copy=False,
        help='Optional reference/note on how the old commission was paid outside the system.'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.user.company_id
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    payment_count = fields.Integer(compute='_compute_payment_count', string='Payment Count')
    commission_amount_with_vat = fields.Monetary(
        string='Commission Amount (With VAT)',
        compute='_compute_commission_amounts',
        store=True,
        currency_field='currency_id'
    )

    commission_amount_without_vat = fields.Monetary(
        string='Commission Amount (Without VAT)',
        compute='_compute_commission_amounts',
        store=True,
        currency_field='currency_id'
    )

    paid_commission = fields.Monetary(
        string='Paid Commission',
        compute='_compute_commission_amounts',
        store=True,
        currency_field='currency_id'
    )

    withholding_tax = fields.Monetary(
        string='Paid Commission',
        compute='_compute_commission_amounts',
        store=True,
        currency_field='currency_id'
    )
    claim_date = fields.Date(
        string='Claim Date',
        required=False,
        tracking=True
    )
    with_withholding_tax = fields.Boolean(string='Apply Withholding Tax', default=True)

    @api.depends('broker_company', 'claim_type')
    def _compute_available_unit_ids(self):
        """Units that have a contract referred by the selected broker/ambassador.
        Left empty for agent/employee claims, which aren't tied to referred_by_partner_id
        (the view only applies this as a domain for claim_type in broker/ambassador)."""
        for rec in self:
            if rec.broker_company and rec.claim_type in ('broker', 'ambassador'):
                proposals = self.env['sale.proposal'].search([
                    ('referred_by_partner_id', '=', rec.broker_company.id),
                    ('state', 'not in', ['cancelled', 'terminated']),
                ])
                rec.available_unit_ids = proposals.mapped('unit_id')
            else:
                rec.available_unit_ids = False

    @api.onchange('broker_company')
    def _onchange_broker_company_clear_unit(self):
        """Clear Unit if it no longer has a contract with the newly selected broker/ambassador."""
        if self.broker_company and self.unit_id and self.unit_id not in self.available_unit_ids:
            self.unit_id = False

    @api.onchange('unit_id')
    def _onchange_unit_id_populate_contract(self):
        """Default Contract, Unit Sold Price and Collection % from the unit's contract."""
        if not self.unit_id:
            return
        base_domain = [('unit_id', '=', self.unit_id.id), ('state', 'not in', ['cancelled', 'terminated'])]
        if self.broker_company:
            base_domain.append(('referred_by_partner_id', '=', self.broker_company.id))

        SaleProposal = self.env['sale.proposal']
        preferred_states = ['signed_client', 'signed_ceo', 'ready_to_deliver', 'delivered']
        proposal = SaleProposal.search(
            base_domain + [('state', 'in', preferred_states)], order='create_date desc', limit=1
        )
        if not proposal:
            proposal = SaleProposal.search(base_domain, order='create_date desc', limit=1)

        if proposal:
            self.sale_proposal_id = proposal
            self.unit_sold_price = proposal.price_after_discount
            self.collection_percentage = proposal.collection_percentage

    @api.constrains('broker_company', 'unit_id', 'claim_type')
    def _check_unit_has_broker_contract(self):
        """Block saving a broker/ambassador claim for a unit that has no contract with this broker."""
        for rec in self:
            if rec.claim_type not in ('broker', 'ambassador') or not rec.broker_company or not rec.unit_id:
                continue
            has_contract = self.env['sale.proposal'].search_count([
                ('unit_id', '=', rec.unit_id.id),
                ('referred_by_partner_id', '=', rec.broker_company.id),
                ('state', 'not in', ['cancelled', 'terminated']),
            ])
            if not has_contract:
                raise ValidationError(_(
                    'Unit %(unit)s has no contract referred by %(broker)s. '
                    'Please select a unit that has a contract with this broker/ambassador.',
                    unit=rec.unit_id.display_name,
                    broker=rec.broker_company.name,
                ))

    @api.depends('unit_sold_price', 'commission', 'with_withholding_tax')
    def _compute_commission_amounts(self):
        for rec in self:
            unit_price = rec.unit_sold_price or 0.0
            commission_percent = rec.commission or 0.0

            commission_with_vat = unit_price * commission_percent / 100

            commission_without_vat = commission_with_vat / 1.14 if commission_with_vat else 0.0

            withholding_tax = commission_without_vat * 0.05

            if rec.with_withholding_tax:
                net_commission = commission_with_vat - withholding_tax
            else:
                net_commission = commission_with_vat

            rec.withholding_tax = withholding_tax
            rec.commission_amount_with_vat = commission_with_vat
            rec.commission_amount_without_vat = commission_without_vat
            rec.paid_commission = net_commission

    @api.depends('payment_id')
    def _compute_payment_count(self):
        for rec in self:
            rec.payment_count = 1 if rec.payment_id else 0

    @api.depends('unit_sold_price', 'commission')
    def _compute_commission_amount(self):
        for record in self:
            record.commission_amount = (record.commission / 100) * record.unit_sold_price

    def _get_claim_type_label(self):
        self.ensure_one()
        return dict(self._fields['claim_type'].selection).get(self.claim_type, _('Broker'))

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('broker.claim') or _('New')
        return super().create(vals)

    def action_confirm(self):
        """Confirm the broker claim and create journal entry"""
        for record in self:
            # Get configuration using ICP (ir.config_parameter)
            ICP = self.env['ir.config_parameter'].sudo()
            debit_account_id = int(ICP.get_param('arkzayed_18_realestate_development.commission_debit_account_id', 0))
            credit_account_id = int(ICP.get_param('arkzayed_18_realestate_development.commission_credit_account_id', 0))
            journal_id = int(ICP.get_param('arkzayed_18_realestate_development.commission_journal_id', 0))

            withholding_account = self.env['account.account'].search([('for_withholding_tax', '=', True)], limit=1)
            withholding_account_id = withholding_account.id if withholding_account else False

            if not debit_account_id or not credit_account_id:
                raise UserError(_(
                    'Please configure Broker Commission accounts in Settings > Configuration > Broker Claims'
                ))

            if not journal_id:
                raise UserError(_(
                    'Please configure Broker Commission journal in Settings > Configuration > Broker Claims'
                ))
            if not withholding_account_id and record.with_withholding_tax:
                raise UserError(_(
                    'Withholding tax account not found. Please create an account with "For Withholding Tax" enabled.'
                ))
            entry_label = _('%s Commission - %s - %s') % (
                record._get_claim_type_label(), record.broker_company.name, record.name)
            account_lines = [
                    # Debit line
                    (0, 0, {
                        'name': entry_label,
                        'account_id': debit_account_id,
                        'debit': record.commission_amount_with_vat,
                        'credit': 0.0,
                        'partner_id': record.broker_company.id,
                        'currency_id': record.currency_id.id,
                    }),
                    # Credit line
                    (0, 0, {
                        'name': entry_label,
                        'account_id': credit_account_id,
                        'debit': 0.0,
                        'credit': record.paid_commission,
                        'partner_id': record.broker_company.id,
                        'currency_id': record.currency_id.id,
                    }),
                ]
            if record.with_withholding_tax:
                account_lines.append(
                    # withholding_line
                    (0, 0, {
                        'name': entry_label,
                        'account_id': withholding_account_id,
                        'debit': 0.0,
                        'credit': record.withholding_tax,
                        'partner_id': record.broker_company.id,
                        'currency_id': record.currency_id.id,
                    })
                )
            # Create journal entry
            move_vals = {
                'move_type': 'entry',
                'journal_id': journal_id,
                'date': fields.Date.today(),
                'ref': entry_label,
                'company_id': record.company_id.id,
                'line_ids': account_lines
            }

            journal_entry = self.env['account.move'].create(move_vals)

            # Update the claim
            record.write({
                'state': 'confirmed',
                'journal_entry_id': journal_entry.id
            })

        return True

    def action_view_agent_claims(self):
        """View the agent claims split out from this broker/ambassador claim"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Agent Claims'),
            'res_model': 'broker.claim',
            'view_mode': 'list,form',
            'domain': [('parent_claim_id', '=', self.id)],
        }

    def action_view_journal_entry(self):
        """View the related journal entry"""
        self.ensure_one()
        if not self.journal_entry_id:
            raise UserError(_('No journal entry exists for this claim.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Journal Entry'),
            'res_model': 'account.move',
            'res_id': self.journal_entry_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_payment(self):
        """Create vendor payment for the broker commission"""
        self.ensure_one()

        if self.state != 'confirmed':
            raise UserError(_('Only confirmed claims can be paid.'))

        if self.payment_id:
            raise UserError(_('Payment already exists for this claim.'))

        # Verify broker is a vendor
        if not self.broker_company:
            raise UserError(_('Broker company is not set.'))

        # Create the payment
        payment_vals = {
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.broker_company.id,
            'amount': self.paid_commission,
            'currency_id': self.currency_id.id,
            'date': fields.Date.today(),
            'memo': _('%s Commission - %s') % (self._get_claim_type_label(), self.name),
            'company_id': self.company_id.id,
            'is_commission_payment': True,
        }

        payment = self.env['account.payment'].create(payment_vals)

        # Update the claim
        self.write({
            'payment_id': payment.id,
        })

        # Return action to open the payment
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Payment'),
            'res_model': 'account.payment',
            'res_id': payment.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_mark_paid_outside_system(self):
        """Mark an old-contract claim as paid, without creating a payment record,
        since its commission was already paid before this system was in use."""
        for record in self:
            if record.state != 'confirmed':
                raise UserError(_('Only confirmed claims can be marked as paid outside the system.'))
            if record.payment_id:
                raise UserError(_('This claim already has a payment recorded in the system.'))
            record.write({
                'state': 'paid',
                'paid_outside_system': True,
                'payment_date': fields.Date.today(),
            })

    def action_view_payment(self):
        """View the related payment"""
        self.ensure_one()
        if not self.payment_id:
            raise UserError(_('No payment exists for this claim.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Payment'),
            'res_model': 'account.payment',
            'res_id': self.payment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_cancel(self):
        """Cancel the broker claim"""
        if self.payment_id and self.payment_id.state == 'posted':
            raise UserError(_('Cannot cancel a claim with a posted payment. Please cancel the payment first.'))

        if self.journal_entry_id and self.journal_entry_id.state == 'posted':
            raise UserError(
                _('Cannot cancel a claim with a posted journal entry. Please cancel the journal entry first.'))

        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        """Reset to draft"""
        if self.payment_id:
            raise UserError(_('Cannot reset to draft when payment exists. Please delete the payment first.'))

        if self.journal_entry_id:
            raise UserError(
                _('Cannot reset to draft when journal entry exists. Please delete the journal entry first.'))

        self.write({
            'state': 'draft',
            'paid_outside_system': False,
            'paid_outside_system_note': False,
        })

    def action_export_excel(self):
        self.ensure_one()
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('مطالبة')

        FONT = 'Arial'

        # ================= FORMATS =================
        title_fmt = workbook.add_format({
            'font_name': FONT,
            'bold': True,
            'font_size': 11,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'bg_color': '#D9D9D9',
            'pattern': 1
        })

        label_fmt = workbook.add_format({
            'font_name': FONT,
            'bold': True,
            'font_size': 10,
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'indent': 2
        })

        value_fmt = workbook.add_format({
            'font_name': FONT,
            'font_size': 10,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })

        header_fmt = workbook.add_format({
            'font_name': FONT,
            'bold': True,
            'font_size': 10,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'text_wrap': True,
            'bg_color': '#D9E1F2'
        })

        amount_fmt = workbook.add_format({
            'font_name': FONT,
            'font_size': 10,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'num_format': '#,##0.00'
        })

        total_fmt = workbook.add_format({
            'font_name': FONT,
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'bg_color': '#D9D9D9'
        })

        total_amount_fmt = workbook.add_format({
            'font_name': FONT,
            'font_size': 10,
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'num_format': '#,##0.00',
            'bg_color': '#D9D9D9'
        })

        sign_fmt = workbook.add_format({
            'font_name': FONT,
            'bold': True,
            'align': 'center',
            'valign': 'top',
            'border': 1,
            'text_wrap': True
        })

        dots_fmt = workbook.add_format({
            'font_name': FONT,
            'font_size': 10,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })

        # ================= RTL + COLUMNS =================
        sheet.right_to_left()

        sheet.set_landscape()
        sheet.set_paper(9)
        sheet.fit_to_pages(1, 1)
        sheet.set_margins(left=0.5, right=0.5, top=0.75, bottom=0.75)
        sheet.center_horizontally()
        sheet.center_vertically()

        sheet.set_column('A:A', 3)
        sheet.set_column('B:B', 40)
        sheet.set_column('C:C', 15)
        sheet.set_column('D:D', 15)
        sheet.set_column('E:E', 13)
        sheet.set_column('F:F', 15)
        sheet.set_column('G:G', 8)
        sheet.set_column('H:H', 17)
        sheet.set_column('I:I', 13)
        sheet.set_column('J:J', 13)

        # ================= TITLE =================
        sheet.merge_range('B2:J2', 'مطالبة', title_fmt)

        # ================= HEADER TEXT =================
        row = 2
        formatted_date = self.claim_date.strftime('%d/%m/%Y') if self.claim_date else ''

        sheet.write(row, 1, 'تحريراً في :', label_fmt)
        sheet.merge_range(row, 2, row, 9, formatted_date, value_fmt)
        row += 1

        sheet.write(row, 1, 'السادة شركة : ذا ارك جروب للتطوير العقاري', label_fmt)
        sheet.merge_range(row, 2, row, 9, '', value_fmt)
        row += 1

        sheet.write(row, 1, 'تحية طيبة وبعد،', label_fmt)
        sheet.merge_range(row, 2, row, 9, '', value_fmt)
        row += 1

        sheet.write(row, 1, 'برجاء صرف العمولة الخاصة بشركة/', label_fmt)
        sheet.merge_range(row, 2, row, 9, self.broker_company.name or '', value_fmt)
        row += 1

        sheet.write(row, 1, 'سجل تجاري رقم', label_fmt)
        sheet.merge_range(row, 2, row, 9, self.broker_company.cr or '', value_fmt)
        row += 1

        sheet.write(row, 1, 'بطاقة ضريبية رقم', label_fmt)
        sheet.merge_range(row, 2, row, 9, self.broker_company.vat or '', value_fmt)
        row += 1

        sheet.write(row, 1, 'عن الوحدات الآتي بيانها:', label_fmt)
        sheet.merge_range(row, 2, row, 9, '', value_fmt)
        row += 2

        # ================= CALCULATIONS =================
        unit_price = self.unit_sold_price or 0.0
        commission_percent = self.commission or 0.0
        commission_with_vat = unit_price * commission_percent / 100
        commission_before_tax = commission_with_vat / 1.14
        withholding_tax = 0.0

        if self.with_withholding_tax:
            withholding_tax = commission_before_tax * 5 / 100
            net_commission = commission_with_vat - withholding_tax
        else:
            net_commission = commission_with_vat

        # ================= TABLE HEADER =================
        headers = [
            'رقم الوحدة المباعة',
            'اسم المشتري',
            'مشروع',
            'قيمة الوحدة المباعة',
            'قيمة العمولة شامل ضريبة القيمة المضافة',
            'ضريبة قيمة مضافة',
            'قيمة العمولة غير شامل ضريبة القيمة المضافة',
        ]

        if self.with_withholding_tax:
            headers.append('ضرائب الخصم 5%')

        headers.append('صافي العمولة المستحقة')

        for i, title in enumerate(headers):
            sheet.write(row, 1 + i, title, header_fmt)

        sheet.set_row(row - 1, 20)
        sheet.set_row(row, 40)

        # ================= DATA =================
        row += 1

        values = [
            self.unit_id.display_name or '',
            self.sale_proposal_id.customer_id.name or '',
            self.unit_id.project_id.name or '',
            unit_price,
            commission_with_vat,
            '14%',
            commission_before_tax,
        ]

        if self.with_withholding_tax:
            values.append(withholding_tax)

        values.append(net_commission)

        for i, val in enumerate(values):
            fmt = amount_fmt if isinstance(val, (int, float)) else value_fmt
            sheet.write(row, 1 + i, val, fmt)

        # ================= EMPTY ROW =================
        row += 1
        num_cols = len(headers)
        for c in range(1, 1 + num_cols):
            sheet.write(row, c, '', value_fmt)

        # ================= TOTAL ================
        row += 1

        sheet.merge_range(row, 1, row, 3, 'Total', total_fmt)

        col_idx = 4
        sheet.write(row, col_idx, unit_price, total_amount_fmt)
        col_idx += 1
        sheet.write(row, col_idx, commission_with_vat, total_amount_fmt)
        col_idx += 1
        sheet.write(row, col_idx, '', total_fmt)  # Empty for 14%
        col_idx += 1
        sheet.write(row, col_idx, commission_before_tax, total_amount_fmt)
        col_idx += 1

        if self.with_withholding_tax:
            sheet.write(row, col_idx, withholding_tax, total_amount_fmt)
            col_idx += 1

        sheet.write(row, col_idx, net_commission, total_amount_fmt)

        # ================= EMPTY ROWS =================
        for _ in range(2):
            row += 1
            for c in range(1, 1 + num_cols):
                sheet.write(row, c, '', value_fmt)

        # ================= FOOTER =================
        row += 1

        sheet.merge_range(row, 1, row, 3, 'المراجعة\n............................', sign_fmt)

        sheet.merge_range(row, 4, row, 6, 'يعتمد\n............................', sign_fmt)

        sheet.set_row(row, 30)

        # ================= FINAL EMPTY ROWS =================
        for _ in range(4):
            row += 1
            for c in range(1, 1 + num_cols):
                sheet.write(row, c, '', value_fmt)

        workbook.close()
        output.seek(0)

        attachment = self.env['ir.attachment'].create({
            'name': f'مطالبة_عمولة_{self.name}.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new'
        }

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref('arkzayed_18_realestate_development.broker_claim_report_action').report_action(self)
