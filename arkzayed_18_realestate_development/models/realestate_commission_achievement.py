from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError


class RealEstateCommissionAchievement(models.Model):
    _name = "realestate.commission.achievement"
    _description = "Real Estate Commission Achievement"
    _rec_name = 'sale_proposal_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    opportunity_id = fields.Many2one('crm.lead', string='Opportunity')
    job_level_id = fields.Many2one('job.level', string='Job Level')
    user_id = fields.Many2one('res.users', string='User', required=True)
    job_position_id = fields.Many2one(comodel_name='hr.job', string='Job Position')
    sales_volume = fields.Integer(string='Sales Volume', group_operator=False)
    commission_percentage = fields.Float(string='Commission Percentage', group_operator=False)
    commission_amount = fields.Float(string='Commission Amount')
    total_commission_amount = fields.Float(string='Total Commission Amount', compute='calc_total_commission', store=True)
    commission_plan_id = fields.Many2one('sale.commission.plan', string='Commission Plan')
    commission_target_id = fields.Many2one('sale.commission.plan.target')
    target_commission_rate_id = fields.Many2one('sale.commission.plan.target.commission', tracking=True)
    is_tcr_sales_person = fields.Boolean(string="Is Sales Person")
    sale_proposal_id = fields.Many2one('sale.proposal', string='Sale Proposal', tracking=True, ondelete='cascade')
    unit_id = fields.Many2one(
        'real.estate.unit',
        string='Unit',
        related='sale_proposal_id.unit_id',
        store=True,
        readonly=True,
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
    paid_outside_system = fields.Boolean(
        string='Paid Outside System',
        copy=False,
        tracking=True,
        help='Commission for an old contract that was already paid before this system was in use. '
             'Marking this sets the record to Paid without creating a payment record.'
    )
    paid_outside_system_note = fields.Char(
        string='Paid Outside System Reference',
        copy=False,
        help='Optional reference/note on how the old commission was paid outside the system.'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    journal_entry_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        readonly=True,
        tracking=True,
        copy=False
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.user.company_id
    )
    partner_id = fields.Many2one(
        'res.partner',
        compute="_get_partner"
    )

    @api.depends('user_id')
    def _get_partner(self):
        for rec in self:
            rec.partner_id = False
            if rec.user_id:
                rec.partner_id = rec.user_id.partner_id

    @api.depends('commission_amount')
    def calc_total_commission(self):
        for rec in self:
            rec.total_commission_amount = rec.commission_amount

    def action_confirm(self):
        """Confirm the Sale commission and create journal entry"""
        for record in self:
            # Get configuration using ICP (ir.config_parameter)
            ICP = self.env['ir.config_parameter'].sudo()
            debit_account_id = int(ICP.get_param('arkzayed_18_realestate_development.sale_commission_debit_account_id', 0))
            credit_account_id = int(ICP.get_param('arkzayed_18_realestate_development.sale_commission_credit_account_id', 0))
            journal_id = int(ICP.get_param('arkzayed_18_realestate_development.sale_commission_journal_id', 0))

            if not debit_account_id or not credit_account_id:
                raise UserError(_(
                    'Please configure Sales Team Commission accounts in Settings > Configuration > Broker Claims'
                ))

            if not journal_id:
                raise UserError(_(
                    'Please configure Sales Team Commission journal in Settings > Configuration > Broker Claims'
                ))


            # Create journal entry
            move_vals = {
                'move_type': 'entry',
                'journal_id': journal_id,
                'date': fields.Date.today(),
                'ref': _('Sales Team Commission - %s') % record.sale_proposal_id.name,
                'company_id': record.company_id.id,
                'line_ids': [
                    # Debit line
                    (0, 0, {
                        'name': _('Sales Team Commission - %s - %s') % (record.partner_id.name, record.sale_proposal_id.name),
                        'account_id': debit_account_id,
                        'debit': record.commission_amount,
                        'credit': 0.0,
                        'partner_id': record.partner_id.id,
                        'currency_id': record.currency_id.id,
                    }),
                    # Credit line
                    (0, 0, {
                    'name': _('Sales Team Commission - %s - %s') % (record.partner_id.name, record.sale_proposal_id.name),
                        'account_id': credit_account_id,
                        'debit': 0.0,
                        'credit': record.commission_amount,
                        'partner_id': record.partner_id.id,
                        'currency_id': record.currency_id.id,
                    }),
                ],
            }

            journal_entry = self.env['account.move'].create(move_vals)

            # Update the sale commission
            record.write({
                'state': 'confirmed',
                'journal_entry_id': journal_entry.id
            })

        return True

    def action_view_journal_entry(self):
        """View the related journal entry"""
        self.ensure_one()
        if not self.journal_entry_id:
            raise UserError(_('No journal entry exists for this sale commission.'))

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
            raise UserError(_('Only confirmed sale commissions can be paid.'))

        if self.payment_id:
            raise UserError(_('Payment already exists for this sale commission.'))


        # Create the payment
        payment_vals = {
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.partner_id.id,
            'amount': self.commission_amount,
            'currency_id': self.currency_id.id,
            'date': fields.Date.today(),
            'memo': _('Sales Team Commission - %s') % self.sale_proposal_id.name,
            'company_id': self.company_id.id,
            'is_commission_payment': True,
        }

        payment = self.env['account.payment'].create(payment_vals)

        # Update the sale commission
        self.write({
            'payment_id': payment.id,
            'payment_date': fields.Date.today(),
            'state': 'paid'
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
        """Mark an old-contract sale commission as paid, without creating a payment record,
        since its commission was already paid before this system was in use."""
        for record in self:
            if record.state != 'confirmed':
                raise UserError(_('Only confirmed sale commissions can be marked as paid outside the system.'))
            if record.payment_id:
                raise UserError(_('This sale commission already has a payment recorded in the system.'))
            record.write({
                'state': 'paid',
                'paid_outside_system': True,
                'payment_date': fields.Date.today(),
            })

    def action_view_payment(self):
        """View the related payment"""
        self.ensure_one()
        if not self.payment_id:
            raise UserError(_('No payment exists for this sale commission.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Payment'),
            'res_model': 'account.payment',
            'res_id': self.payment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


    def action_cancel(self):
        """Cancel the sale commission"""
        if self.payment_id and self.payment_id.state == 'posted':
            raise UserError(_('Cannot cancel a sale commission with a posted payment. Please cancel the payment first.'))

        if self.journal_entry_id and self.journal_entry_id.state == 'posted':
            raise UserError(
                _('Cannot cancel a sale commission with a posted journal entry. Please cancel the journal entry first.'))

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
