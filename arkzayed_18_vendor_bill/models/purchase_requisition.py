# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class PurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'

    total_agreement = fields.Monetary(
        string='Total Agreement',
        currency_field='currency_id',
        help="Total value of the purchase agreement"
    )
    down_payment_agreement = fields.Monetary(
        string='Down Payment Agreement',
        currency_field='currency_id',
        help="Down payment amount for this agreement"
    )
    payment_ids = fields.One2many(
        'account.payment',
        'requisition_id',
        string='Payments',
        readonly=True
    )
    cheque_ids = fields.One2many(
        'cheque.manage',
        'requisition_id',
        string='Cheques',
        readonly=True
    )
    payment_count = fields.Integer(
        string='Payment Count',
        compute='_compute_payment_count'
    )
    cheque_count = fields.Integer(
        string='Cheque Count',
        compute='_compute_cheque_count'
    )
    progress_cutoff_date = fields.Date(string='Progress Cut-off Date')
    submission_date = fields.Date(string='Submission Date')

    @api.depends('payment_ids', 'payment_ids.state')
    def _compute_payment_count(self):
        for requisition in self:
            requisition.payment_count = len(requisition.payment_ids)

    @api.depends('cheque_ids')
    def _compute_cheque_count(self):
        for requisition in self:
            requisition.cheque_count = len(requisition.cheque_ids)

    def action_create_down_payment(self):
        """Open wizard to create payment or cheque for down payment"""
        self.ensure_one()

        if not self.down_payment_agreement:
            raise UserError(_('Please set a down payment amount first.'))

        return {
            'name': _('Create Down Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.requisition.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_requisition_id': self.id,
                'default_amount': self.down_payment_agreement,
                'default_partner_id': self.vendor_id.id if self.vendor_id else False,
                'default_is_pre_payment': True,
            }
        }

    def action_view_payments(self):
        """View payments related to this requisition"""
        self.ensure_one()
        return {
            'name': _('Payments'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('requisition_id', '=', self.id)],
            'context': {'default_requisition_id': self.id}
        }

    def action_view_cheques(self):
        """View cheques related to this requisition"""
        self.ensure_one()
        return {
            'name': _('Cheques'),
            'type': 'ir.actions.act_window',
            'res_model': 'cheque.manage',
            'view_mode': 'list,form',
            'domain': [('requisition_id', '=', self.id)],
            'context': {'default_requisition_id': self.id}
        }


class PurchaseRequisitionLine(models.Model):
    _inherit = 'purchase.requisition.line'

    is_insurance_product = fields.Boolean(
        string='Is Insurance Product',
        default=False
    )
    insurance_percentage = fields.Float(
        string='Insurance (%)',
        default=0.0
    )

    @api.onchange('is_insurance_product', 'insurance_percentage')
    def _onchange_is_insurance_product(self):
        """Calculate the price of insurance based on the percentage"""
        for line in self:
            if line.is_insurance_product:
                # Initialize price_unit to 0 for insurance products
                line.price_unit = 0

                if line.insurance_percentage > 0:
                    # Get all requisition lines (including unsaved changes)
                    all_lines = line.requisition_id.line_ids

                    # Filter non-insurance lines
                    non_insurance_lines = all_lines.filtered(
                        lambda l: not l.is_insurance_product and l.id != line.id
                    )

                    # Calculate total (requisition lines don't have taxes, so this is always without tax)
                    product_total = self._product_amount(non_insurance_lines)

                    # Calculate insurance amount
                    line.price_unit = (product_total * line.insurance_percentage / 100)

    def _product_amount(self, lines):
        """Calculate the total amount of lines (requisition lines don't have taxes)"""
        total_sum = 0
        for line in lines:
            total_sum += line.price_unit * line.product_qty
        return total_sum

    def _prepare_purchase_order_line(self, **kwargs):
        """Override to pass insurance fields to purchase order line and reset price_unit for insurance products"""
        # Remove 'order' parameter if it exists to avoid signature issues
        kwargs.pop('order', None)
        res = super()._prepare_purchase_order_line(**kwargs)

        # Add insurance fields to the purchase order line
        res.update({
            'is_insurance_product': self.is_insurance_product,
            'insurance_percentage': self.insurance_percentage,
        })

        # For insurance products, force price_unit to 0 to trigger recalculation in PO
        if self.is_insurance_product:
            res['price_unit'] = 0.0

        return res
