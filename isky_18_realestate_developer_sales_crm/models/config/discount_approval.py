from odoo import models, fields, api, _


class DiscountApproval(models.Model):
    _name = 'discount.approval'
    _description = 'Discount Approval'
    _order = 'sequence'

    name = fields.Char(
        string='Name',
        required=True
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    discount_percentage_from = fields.Float(
        string='Discount % From',
        help='Discount percentage range start (inclusive)'
    )
    discount_percentage_to = fields.Float(
        string='Discount % To',
        help='Discount percentage range end (inclusive)'
    )
    discount_amount_from = fields.Float(
        string='Discount Amount From',
        help='Discount amount range start (inclusive)'
    )
    discount_amount_to = fields.Float(
        string='Discount Amount To',
        help='Discount amount range end (inclusive)'
    )
    approver_id = fields.Many2one(
        'res.users',
        string='Approver',
        required=True,
        help='User who will approve discounts matching these criteria'
    )
    approver_ids = fields.Many2many(
        'res.users',
        'discount_approval_users_rel',
        'approval_id',
        'user_id',
        string='Alternative Approvers',
        help='Additional users who can also approve discounts matching these criteria'
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )
    notes = fields.Text(
        string='Notes'
    )

    def _get_approver_for_discount(self, discount_percentage=None, discount_amount=None):
        """
        Get the appropriate approver(s) for a discount based on percentage and/or amount.
        """
        domain = [('active', '=', True)]

        if discount_percentage is not None:
            domain += [
                '|',
                ('discount_percentage_from', '=', 0),
                ('discount_percentage_from', '<=', discount_percentage),
            ]
            domain += [
                '|',
                ('discount_percentage_to', '=', 0),
                ('discount_percentage_to', '>=', discount_percentage),
            ]

        if discount_amount is not None:
            domain += [
                '|',
                ('discount_amount_from', '=', 0),
                ('discount_amount_from', '<=', discount_amount),
            ]
            domain += [
                '|',
                ('discount_amount_to', '=', 0),
                ('discount_amount_to', '>=', discount_amount),
            ]

        approvals = self.search(domain, limit=1)
        if approvals:
            return approvals[0].approver_id
        return None