from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class DiscountRequest(models.Model):
    _name = 'discount.request'
    _description = 'Discount Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: 'New'
    )
    unit_id = fields.Many2one(
        'real.estate.unit',
        string='Unit',
        required=True,
        tracking=True
    )
    down_payment = fields.Float(
        string='Down Payment',
        required=True,
        tracking=True
    )
    installment_years = fields.Integer(
        string='Installment Years',
        required=True,
        tracking=True
    )
    total_price_unit = fields.Float(
        string='Total Price',
        required=True,
        tracking=True
    )
    price_after_discount = fields.Float(
        string='Price After Discount',
        tracking=True
    )
    requested_by = fields.Many2one(
        'res.users',
        string='Requested By',
        default=lambda self: self.env.user,
        tracking=True
    )
    request_date = fields.Date(
        string='Request Date',
        default=fields.Date.today,
        tracking=True
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        tracking=True
    )
    approved_date = fields.Date(
        string='Approved Date',
        tracking=True
    )

    @api.constrains('unit_id', 'state')
    def _check_unique_active_discount_request(self):
        # Filter approved records to check
        records_to_check = self.filtered(lambda r: r.state == 'approved')
        if not records_to_check:
            return
        unit_ids = records_to_check.mapped('unit_id').ids
        existing = self.search_read(
            [
                ('unit_id', 'in', unit_ids),
                ('state', '=', 'approved'),
                ('id', 'not in', records_to_check.ids),
            ],
            ['unit_id'],
        )
        existing_unit_ids = {rec['unit_id'][0] for rec in existing}

        for record in records_to_check:
            if record.unit_id.id in existing_unit_ids:
                raise ValidationError(f'A discount request has already been approved for unit "{record.unit_id.name}".')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('discount.request') or 'New'
        return super().create(vals_list)

    def action_submit(self):
        self.write({'state': 'pending'})

    def action_approve(self):
        for record in self:
            record.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approved_date': fields.Date.today(),
            })
            record.unit_id.write({
                'total_price_unit_after_discount': record.price_after_discount,
                'installment_years_after_discount': record.installment_years,
                'down_payment_after_discount': record.down_payment,
                'has_discount': True,
            })
            # Cancel other pending/draft requests for the same unit
            other_requests = self.search([
                ('unit_id', '=', record.unit_id.id),
                ('id', '!=', record.id),
                ('state', 'in', ['draft', 'pending']),
            ])
            if other_requests:
                other_requests.write({'state': 'cancelled'})

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
