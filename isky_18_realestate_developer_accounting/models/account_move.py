from num2words import num2words

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    # --- from arkzayed_18_realestate_development/models/account_move.py ---
    is_contract = fields.Boolean(string='Is Contract', default=False,
                                 help='Check if this invoice is related to a real estate contract')
    sale_proposal_id = fields.Many2one('sale.proposal', string='Sale Proposal', readonly=True)
    penalty_id = fields.Many2one('installment.penalty', string='Penalty', readonly=True)
    sale_reservation_id = fields.Many2one('real.estate.sale.reservation', string='Sale Reservation', readonly=True)
    is_collection = fields.Boolean(string="Is Collection", default=False)
    is_maintenance_collection = fields.Boolean(string="Is Maintenance Collection", default=False)
    is_gis_quia = fields.Boolean(string="Is GIS/OAYA", default=False)
    under_collection_date = fields.Date(string="Under Collection Date", copy=False)

    # --- from arkzayed_18_gt_cheque_management/models/account_move.py (not actually cheque-specific;
    # this file was not even imported by that module's __init__.py, so it was dead code there) ---
    journal_type = fields.Selection(
        related='journal_id.type',
        string='Journal Type',
        store=True,
        readonly=True
    )

    # --- from arkzayed_18_realestate_development/models/account_invoice.py ---
    real_estate_ref = fields.Char("Real Estate Ref.")
    line_id = fields.Many2one("loan.line", "Contract Line")
    installment_line_id = fields.Many2one("installment.lines", "Contract Line")
    installment_lines_line_id = fields.Many2one("maintenance.installment.lines", "Contract Line")
    revenue_share_id = fields.Many2one('revenue.share2', string="Revenue Share")
    revenue_share_type = fields.Selection([('rev1', 'Rev1'), ('rev2', 'Rev2')])
    entry_sequence = fields.Char(readonly=True, copy=False)
    is_checked = fields.Selection([
        ('checked', 'Checked'),
        ('not_checked', 'Not Checked')
    ], string="Checked", default='not_checked', compute='_compute_is_checked', store=True)
    checked_bool = fields.Boolean(string="Checked", default=False)

    # --- from arkzayed_18_vendor_bill/models/account_move.py ---
    building_id = fields.Many2one(
        'real.estate.building',
        string='Building',
        tracking=True
    )

    purchase_type = fields.Selection([
        ('original', 'Original'),
        ('construction', 'Construction')
    ], string='Type', default='original',
        help="Original: Normal calculation (qty × price = subtotal)\n"
             "Construction: Subtotal is editable, quantity is calculated")

    engineering_approved = fields.Boolean(
        string='Engineering Approved',
        copy=False,
        tracking=True,
        help="Set to True once the Engineering team has approved a Construction vendor bill. "
             "Construction bills can only be confirmed after this approval."
    )

    history_line_ids = fields.One2many(
        'account.move.history.line',
        'move_id',
        string='History Lines',
        compute='_compute_history_lines',
        store=True
    )
    history_report_line_ids = fields.One2many(
        'account.move.history.line.report',
        'move_id',
        string='History Report'
    )
    ipc_previous_work_done = fields.Float(
        string='Previous Work Done',
        compute='_compute_ipc_values',
        store=True
    )
    ipc_current_work_done = fields.Float(
        string='Current Work Done',
        compute='_compute_ipc_values',
        store=True
    )
    ipc_total_work_done = fields.Float(
        string='Total Work Done',
        compute='_compute_ipc_values',
        store=True
    )
    ipc_previous_materials = fields.Float(
        string='Previous Materials',
        compute='_compute_ipc_values',
        store=True
    )
    ipc_current_materials = fields.Float(
        string='Current Materials',
        compute='_compute_ipc_values',
        store=True
    )
    ipc_materials_on_site = fields.Float(
        string='Materials on Site',
        compute='_compute_ipc_values',
        store=True
    )

    ipc_previous_social_insurance = fields.Float(
        string='Previous Social Insurance',
        compute='_compute_ipc_values',
        store=True
    )
    ipc_current_social_insurance = fields.Float(
        string='Current Social Insurance',
        compute='_compute_ipc_values',
        store=True
    )
    ipc_total_social_insurance = fields.Float(
        string='Total Social Insurance',
        compute='_compute_ipc_values',
        store=True
    )

    ipc_previous_engineering_fee = fields.Float(
        string='Previous Engineering Fee',
        compute='_compute_ipc_values',
        store=True
    )
    ipc_current_engineering_fee = fields.Float(
        string='Current Engineering Fee',
        compute='_compute_ipc_values',
        store=True
    )
    ipc_total_engineering_fee = fields.Float(
        string='Total Engineering Fee',
        compute='_compute_ipc_values',
        store=True
    )

    ipc_gross_value = fields.Float(
        string='Gross Value',
        compute='_compute_ipc_values',
        store=True
    )
    ipc_withholding_tax = fields.Float(
        string='Withholding Tax',
        compute='_compute_ipc_withholding_tax',
        store=True
    )

    @api.depends('checked_bool')
    def _compute_is_checked(self):
        for record in self:
            record.is_checked = 'checked' if record.checked_bool else 'not_checked'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('company_id'):
                vals['company_id'] = self.env.company.id
        res = super(AccountMove, self).create(vals_list)
        res.entry_sequence = self.env['ir.sequence'].next_by_code('entry.sequence')
        return res

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

    def action_register_penalty_payment(self):
        self.ensure_one()
        if self.state != 'posted':
            raise UserError('Please post the journal entry before registering payment.')
        return {
            'name': 'Register Payment',
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment.register',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'account.move',
                'active_ids': [self.id],
            },
        }

    def action_read_history_report_lines(self):
        for move in self:
            move.history_report_line_ids.unlink()

            report_lines = []
            for history_line in move.history_line_ids:
                report_lines.append((0, 0, {
                    'product_id': history_line.product_id.id,
                    'previous_work': history_line.previous_work,
                    'current_work': history_line.current_work,
                    'total_work': history_line.total_work,
                }))

            move.history_report_line_ids = report_lines

        return True

    @api.depends('invoice_line_ids', 'invoice_line_ids.purchase_line_id',
                 'invoice_line_ids.purchase_line_id.order_id.requisition_id')
    def _compute_history_lines(self):
        for move in self:
            if move.move_type != 'in_invoice':
                move.history_line_ids = False
                continue

            # Get the purchase agreement from current bill's purchase orders
            requisition_ids = move.invoice_line_ids.mapped(
                'purchase_line_id.order_id.requisition_id'
            )

            if not requisition_ids:
                move.history_line_ids = False
                continue

            # Get all purchase orders linked to these agreements
            all_purchase_orders = self.env['purchase.order'].search([
                ('requisition_id', 'in', requisition_ids.ids),
                ('state', 'in', ['purchase', 'done'])
            ])

            # Calculate history per product
            history_data = {}

            for po in all_purchase_orders:
                for line in po.order_line:
                    product = line.product_id
                    if not product:
                        continue

                    if product.id not in history_data:
                        history_data[product.id] = {
                            'product_id': product.id,
                            'previous_work': 0.0,
                            'current_work': 0.0,
                        }

                    # Get all posted invoice lines for this PO line (excluding current bill)
                    previous_invoice_lines = line.invoice_lines.filtered(
                        lambda l: l.move_id.state == 'posted' and l.move_id.id != move.id
                    )
                    previous_subtotal = sum(previous_invoice_lines.mapped('price_subtotal'))

                    # Get invoice lines from current bill for this PO line
                    current_invoice_lines = line.invoice_lines.filtered(
                        lambda l: l.move_id.id == move.id
                    )
                    current_subtotal = sum(current_invoice_lines.mapped('price_subtotal'))

                    # Add to product totals
                    history_data[product.id]['previous_work'] += previous_subtotal
                    history_data[product.id]['current_work'] += current_subtotal

            # Create history lines
            history_lines = []
            for product_id, data in history_data.items():
                history_lines.append((0, 0, {
                    'product_id': data['product_id'],
                    'previous_work': data['previous_work'],
                    'current_work': data['current_work'],
                    'total_work': data['previous_work'] + data['current_work'],
                }))

            move.history_line_ids = history_lines

    @api.depends('history_report_line_ids',
                 'history_report_line_ids.product_id',
                 'history_report_line_ids.product_id.ipc_type',
                 'history_report_line_ids.product_id.is_social_insurance',
                 'history_report_line_ids.product_id.is_engineering_fee',
                 'history_report_line_ids.previous_work',
                 'history_report_line_ids.current_work',
                 'history_report_line_ids.total_work')
    def _compute_ipc_values(self):
        for move in self:
            if move.move_type != 'in_invoice':
                move.ipc_previous_work_done = 0.0
                move.ipc_current_work_done = 0.0
                move.ipc_total_work_done = 0.0
                move.ipc_previous_materials = 0.0
                move.ipc_current_materials = 0.0
                move.ipc_materials_on_site = 0.0
                move.ipc_previous_social_insurance = 0.0
                move.ipc_current_social_insurance = 0.0
                move.ipc_total_social_insurance = 0.0
                move.ipc_previous_engineering_fee = 0.0
                move.ipc_current_engineering_fee = 0.0
                move.ipc_total_engineering_fee = 0.0
                move.ipc_gross_value = 0.0
                continue

            previous_work_done = 0.0
            current_work_done = 0.0
            previous_materials = 0.0
            current_materials = 0.0
            previous_social_insurance = 0.0
            current_social_insurance = 0.0
            previous_engineering_fee = 0.0
            current_engineering_fee = 0.0

            # Read from history_report_line_ids instead of history_line_ids
            for report_line in move.history_report_line_ids:
                product = report_line.product_id
                if not product:
                    continue

                # Check flags - order matters, check specific flags first
                if product.is_social_insurance:
                    previous_social_insurance += abs(report_line.previous_work)
                    current_social_insurance += abs(report_line.current_work)

                elif product.is_engineering_fee:
                    previous_engineering_fee += abs(report_line.previous_work)
                    current_engineering_fee += abs(report_line.current_work)

                elif product.ipc_type == 'work_done':
                    previous_work_done += report_line.previous_work
                    current_work_done += report_line.current_work

                elif product.ipc_type == 'material':
                    previous_materials += report_line.previous_work
                    current_materials += report_line.current_work

            move.ipc_previous_work_done = previous_work_done
            move.ipc_current_work_done = current_work_done
            move.ipc_total_work_done = previous_work_done + current_work_done

            move.ipc_previous_materials = previous_materials
            move.ipc_current_materials = current_materials
            move.ipc_materials_on_site = previous_materials + current_materials

            move.ipc_previous_social_insurance = previous_social_insurance
            move.ipc_current_social_insurance = current_social_insurance
            move.ipc_total_social_insurance = previous_social_insurance + current_social_insurance

            move.ipc_previous_engineering_fee = previous_engineering_fee
            move.ipc_current_engineering_fee = current_engineering_fee
            move.ipc_total_engineering_fee = previous_engineering_fee + current_engineering_fee

            move.ipc_gross_value = move.ipc_total_work_done + move.ipc_materials_on_site

    @api.depends('invoice_line_ids', 'invoice_line_ids.tax_ids', 'invoice_line_ids.price_subtotal')
    def _compute_ipc_withholding_tax(self):
        for move in self:
            withholding_total = 0.0

            for line in move.invoice_line_ids:
                for tax in line.tax_ids:
                    if tax.amount < 0:
                        withholding_total += (line.price_subtotal * abs(tax.amount) / 100)

            move.ipc_withholding_tax = withholding_total

    def action_engineering_approval(self):
        """Mark Construction vendor bills as approved by the Engineering team.

        Only members of the 'Engineering Approval' group may run this action;
        once approved, the standard Confirm button becomes available.
        """
        if not self.env.user.has_group('arkzayed_18_vendor_bill.group_engineering_approval'):
            raise UserError(_("Only users in the Engineering Approval group can perform this action."))
        for move in self:
            if move.move_type != 'in_invoice' or move.purchase_type != 'construction':
                raise UserError(_("Engineering Approval only applies to Construction vendor bills."))
            move.engineering_approved = True

    def action_post(self):
        for move in self:
            if (move.move_type == 'in_invoice'
                    and move.purchase_type == 'construction'
                    and not move.engineering_approved):
                raise UserError(_(
                    "Construction vendor bills must be approved by the Engineering team "
                    "before they can be confirmed."
                ))
        return super().action_post()

    def button_draft(self):
        if not self.env.user.has_group('arkzayed_18_vendor_bill.group_reset_to_draft'):
            raise UserError(
                _("You do not have the rights to reset this record to draft. Please contact your administrator."))
        res = super(AccountMove, self).button_draft()
        # Re-require Engineering Approval every time a Construction bill goes back to draft.
        construction_bills = self.filtered(
            lambda m: m.move_type == 'in_invoice' and m.purchase_type == 'construction'
        )
        if construction_bills:
            construction_bills.engineering_approved = False
        return res


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # --- from arkzayed_18_vendor_bill/models/account_move.py ---
    is_insurance_product = fields.Boolean(
        string='Is Insurance Product',
        default=False
    )
    insurance_percentage = fields.Float(
        string='Insurance (%)',
        default=0.0
    )

    # --- from arkzayed_cost_distribution/models/account_move_line.py ---
    distribution_state = fields.Selection([
        ('pending', 'Not Distributed'),
        ('partial', 'Partially Distributed'),
        ('done', 'Fully Distributed'),
    ], string='Unit Distribution', default='pending')

    allocation_ids = fields.One2many('arkzayed.cost.allocation', 'move_line_id', string='Cost Allocations')

    distributed_amount = fields.Monetary(compute='_compute_distributed_amount', string='Distributed Amount')

    remaining_amount = fields.Monetary(compute='_compute_distributed_amount', string='Remaining to Distribute')

    @api.constrains('account_id', 'display_type')
    def _check_payable_receivable(self):
        """Override to skip validation for contract invoices"""
        for line in self:
            # Skip validation for contract invoices
            if line.move_id.is_contract:
                continue

            # Original validation for non-contract moves
            account_type = line.account_id.account_type
            if line.move_id.is_sale_document(include_receipts=True):
                if account_type == 'liability_payable':
                    raise UserError(
                        _("Account %s is of payable type, but is used in a sale operation.", line.account_id.code))
                if (line.display_type == 'payment_term') ^ (account_type == 'asset_receivable'):
                    raise UserError(_("Any journal item on a receivable account must have a due date and vice versa."))
            if line.move_id.is_purchase_document(include_receipts=True):
                if account_type == 'asset_receivable':
                    raise UserError(_("Account %s is of receivable type, but is used in a purchase operation.",
                                      line.account_id.code))
                if (line.display_type == 'payment_term') ^ (account_type == 'liability_payable'):
                    raise UserError(_("Any journal item on a payable account must have a due date and vice versa."))

    @api.onchange('is_insurance_product', 'insurance_percentage')
    def _onchange_is_insurance_product(self):
        """Calculate the price of insurance based on the percentage"""
        for line in self:
            if line.is_insurance_product and line.insurance_percentage > 0:
                # Get all invoice lines (including unsaved changes)
                all_lines = line.move_id.invoice_line_ids

                # Filter non-insurance lines
                non_insurance_lines = all_lines.filtered(
                    lambda l: not l.is_insurance_product and l.id != line.id
                )

                # Calculate total with taxes
                product_total = self._product_with_tax_amount(non_insurance_lines)

                # Calculate insurance amount
                line.price_unit = (product_total * line.insurance_percentage / 100)

    @api.onchange('price_unit', 'tax_ids', 'quantity')
    def _onchange_recalculate_insurance_lines(self):
        """Recalculate all insurance lines when any line changes"""
        if not self.is_insurance_product:
            # Only recalculate if this is NOT an insurance line (to avoid recursion)
            insurance_lines = self.move_id.invoice_line_ids.filtered(lambda l: l.is_insurance_product)
            for ins_line in insurance_lines:
                ins_line._onchange_is_insurance_product()

    def _product_with_tax_amount(self, lines):
        """Calculate the total amount of lines including taxes"""
        total_sum = 0
        for line in lines:
            product_price = line.price_unit * line.quantity
            # Calculate tax amount
            tax_amount = 0
            for tax in line.tax_ids:
                tax_amount += product_price * tax.amount / 100
            total_sum += product_price + tax_amount
        return total_sum

    @api.depends('allocation_ids.amount', 'price_total')
    def _compute_distributed_amount(self):
        for line in self:
            distributed = sum(line.allocation_ids.mapped('amount'))
            line.distributed_amount = distributed
            # The distributable amount is the line total including taxes.
            line.remaining_amount = line.price_total - distributed

    def action_open_cost_distribution_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Distribute Cost to Units',
            'res_model': 'arkzayed.cost.distribution.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_move_line_id': self.id},
        }
