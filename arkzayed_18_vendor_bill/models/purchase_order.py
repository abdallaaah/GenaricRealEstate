# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    purchase_type = fields.Selection([
        ('original', 'Original'),
        ('construction', 'Construction')
    ], string='Purchase Type', default='original', required=True,
        help="Original: Normal calculation (qty × price = subtotal)\n"
             "Construction: Subtotal is editable, quantity is calculated")

    @api.model
    def default_get(self, fields_list):
        """Set purchase_type to construction if there's a requisition in context"""
        res = super().default_get(fields_list)
        # Check for requisition in context or explicit purchase_type
        if self.env.context.get('default_requisition_id') or self.env.context.get(
                'default_purchase_type') == 'construction':
            res['purchase_type'] = 'construction'
        return res

    def _prepare_invoice(self):
        """Override to pass purchase_type to the invoice"""
        invoice_vals = super()._prepare_invoice()
        invoice_vals['purchase_type'] = self.purchase_type
        return invoice_vals


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    is_insurance_product = fields.Boolean(
        string='Is Insurance',
        default=False
    )
    insurance_percentage = fields.Float(
        string='Insurance (%)',
        default=0.0
    )
    quantity_percentage = fields.Float(
        string='Quantity (%)',
        default=0.0,
    )

    # Make price_subtotal computed and stored, but read-only
    price_subtotal = fields.Monetary(
        compute='_compute_amount',
        string='Subtotal',
        store=True,
        readonly=True
    )

    purchase_type = fields.Selection(
        related='order_id.purchase_type',
        string='Purchase Type',
        store=True
    )

    @api.depends('product_qty', 'price_unit', 'taxes_id', 'discount', 'purchase_type')
    def _compute_amount(self):
        """Override to handle construction type calculation"""

        for line in self:
            # Custom calculation for construction type
            if line.purchase_type == 'construction':
                # Calculate subtotal from qty and price
                line.price_subtotal = line.product_qty * line.price_unit

                # Use the base line computation to get taxes on the subtotal
                base_line = line._prepare_base_line_for_taxes_computation()
                self.env['account.tax']._add_tax_details_in_base_line(base_line, line.company_id)

                line.price_total = base_line['tax_details']['raw_total_included_currency']
                line.price_tax = line.price_total - line.price_subtotal
            else:
                # Use standard calculation for everything else
                super(PurchaseOrderLine, line)._compute_amount()

    @api.onchange('quantity_percentage')
    def _onchange_quantity(self):
        for line in self:
            line.product_qty = line.quantity_percentage / 100

    @api.onchange('product_qty', 'price_unit')
    def _onchange_qty_price_update_subtotal(self):
        """Update subtotal when quantity or price changes"""
        for line in self:
            if not line.is_insurance_product:
                # Trigger recomputation
                line._compute_amount()

    @api.model_create_multi
    def create(self, vals_list):
        """Set quantity to 1 and recalculate price for insurance product lines"""
        for vals in vals_list:
            if vals.get('is_insurance_product'):
                vals['product_qty'] = 1
                vals['price_unit'] = 0.0

        lines = super().create(vals_list)

        # Recalculate insurance lines
        orders_to_recalc = lines.mapped('order_id')
        for order in orders_to_recalc:
            self._recalculate_insurance_lines_for_order(order)

        return lines

    def write(self, vals):
        """Handle updates for construction type and insurance lines"""
        # Prevent changing quantity on insurance lines
        if 'product_qty' in vals:
            for line in self:
                if line.is_insurance_product and vals.get('product_qty') != 1:
                    vals['product_qty'] = 1

        res = super().write(vals)

        # Recalculate insurance lines if needed
        if any(field in vals for field in ['price_unit', 'product_qty', 'taxes_id']):
            orders_to_recalc = self.filtered(lambda l: not l.is_insurance_product).mapped('order_id')
            for order in orders_to_recalc:
                self._recalculate_insurance_lines_for_order(order)

        return res

    def _get_lines_above(self, target_line):
        """Get all lines that appear before the target line in the order"""
        if not target_line.order_id:
            return self.env['purchase.order.line']

        all_lines = target_line.order_id.order_line.sorted(key=lambda l: l.sequence)
        lines_above = self.env['purchase.order.line']

        for line in all_lines:
            if line.id == target_line.id:
                break
            lines_above |= line

        return lines_above

    @api.model
    def _recalculate_insurance_lines_for_order(self, order):
        """Recalculate all insurance lines for a given order"""
        if not order:
            return

        insurance_lines = order.order_line.filtered(
            lambda l: l.is_insurance_product and l.insurance_percentage > 0
        )

        if not insurance_lines:
            return

        for ins_line in insurance_lines:
            # Get only non-insurance lines ABOVE this insurance line
            lines_above = self._get_lines_above(ins_line)
            non_insurance_lines_above = lines_above.filtered(lambda l: not l.is_insurance_product)

            # Check if insurance should exclude tax
            exclude_tax = ins_line.product_id.insurance_exclude_tax if ins_line.product_id else False

            if exclude_tax:
                # Calculate without tax
                product_total = self._product_amount_without_tax(non_insurance_lines_above)
            else:
                # Calculate with tax (original behavior)
                product_total = self._product_with_tax_amount(non_insurance_lines_above)

            new_price = -(product_total * ins_line.insurance_percentage / 100)
            super(PurchaseOrderLine, ins_line).write({
                'price_unit': new_price
            })

    @api.onchange('is_insurance_product', 'insurance_percentage', 'product_id')
    def _onchange_is_insurance_product(self):
        """Calculate the price of insurance based on the percentage"""
        for line in self:
            if line.is_insurance_product:
                line.product_qty = 1
                line.price_unit = 0

                if line.insurance_percentage > 0 and line.order_id:
                    # Get only non-insurance lines ABOVE this insurance line
                    lines_above = self._get_lines_above(line)
                    non_insurance_lines_above = lines_above.filtered(lambda l: not l.is_insurance_product)

                    # Check if insurance should exclude tax
                    exclude_tax = line.product_id.insurance_exclude_tax if line.product_id else False

                    if exclude_tax:
                        # Calculate without tax
                        product_total = self._product_amount_without_tax(non_insurance_lines_above)
                    else:
                        # Calculate with tax (original behavior)
                        product_total = self._product_with_tax_amount(non_insurance_lines_above)

                    line.price_unit = -(product_total * line.insurance_percentage / 100)

    @api.onchange('price_unit', 'taxes_id', 'product_qty')
    def _onchange_recalculate_insurance_lines(self):
        """Recalculate all insurance lines BELOW this line when it changes"""
        if self.is_insurance_product:
            self.product_qty = 1
            return

        if not self.order_id:
            return

        # Get all lines in the order sorted by sequence
        all_lines = self.order_id.order_line.sorted(key=lambda l: l.sequence)

        # Find insurance lines that come AFTER this line
        found_current = False
        insurance_lines_below = self.env['purchase.order.line']

        for line in all_lines:
            if line.id == self.id:
                found_current = True
                continue
            if found_current and line.is_insurance_product and line.insurance_percentage > 0:
                insurance_lines_below |= line

        if not insurance_lines_below:
            return

        for ins_line in insurance_lines_below:
            # Get only non-insurance lines ABOVE the insurance line
            lines_above = self._get_lines_above(ins_line)
            non_insurance_lines_above = lines_above.filtered(lambda l: not l.is_insurance_product)

            # Check if insurance should exclude tax
            exclude_tax = ins_line.product_id.insurance_exclude_tax if ins_line.product_id else False

            if exclude_tax:
                # Calculate without tax
                product_total = self._product_amount_without_tax(non_insurance_lines_above)
            else:
                # Calculate with tax (original behavior)
                product_total = self._product_with_tax_amount(non_insurance_lines_above)

            ins_line.price_unit = -(product_total * ins_line.insurance_percentage / 100)

    @api.onchange('product_qty')
    def _onchange_product_qty_insurance(self):
        """Prevent changing quantity for insurance products"""
        if self.is_insurance_product and self.product_qty != 1:
            self.product_qty = 1

    def _product_amount_without_tax(self, lines):
        """Calculate the total amount of lines WITHOUT taxes"""
        total_sum = 0
        for line in lines:
            total_sum += line.price_unit * line.product_qty
        return total_sum

    def _product_with_tax_amount(self, lines):
        """Calculate the total amount of lines including taxes (only taxes marked for insurance)"""
        total_sum = 0
        for line in lines:
            product_price = line.price_unit * line.product_qty
            tax_amount = 0
            for tax in line.taxes_id:
                # Only include tax if its tax group is marked to be included in insurance
                if tax.tax_group_id and tax.tax_group_id.include_in_insurance:
                    tax_amount += product_price * tax.amount / 100
            total_sum += product_price + tax_amount
        return total_sum

    def _prepare_account_move_line(self, move=False):
        """Copy insurance fields to invoice line"""
        res = super()._prepare_account_move_line(move=move)
        res.update({
            'is_insurance_product': self.is_insurance_product,
            'insurance_percentage': self.insurance_percentage,
        })
        return res
