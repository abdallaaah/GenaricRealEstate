from odoo import models, fields, api
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta

class InstallmentPenalty(models.Model):
    _name = 'installment.penalty'
    _description = 'Installment Delay Penalty'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Reference',readonly=True,default='New')
    sale_proposal_id = fields.Many2one('sale.proposal',string='Contract',required=True,ondelete='cascade',tracking=True)
    installment_line_id = fields.Many2one('installment.lines',string='Installment Line',required=True,ondelete='cascade',tracking=True)
    unit_id = fields.Many2one('real.estate.unit',string='Unit',related='sale_proposal_id.unit_id',store=True)
    customer_id = fields.Many2one('res.partner',string='Customer',related='sale_proposal_id.customer_id',store=True)
    installment_due_date = fields.Date(string='Installment Due Date',required=True)
    installment_amount = fields.Float(string='Installment Amount',required=True)
    delay_penalty_rate = fields.Float(string='Penalty Rate (%)',required=True)
    number_of_periods = fields.Integer(string='Periods Overdue',tracking=True)
    penalty_amount = fields.Float(string='Penalty Amount',compute='_compute_penalty_amount',store=True,tracking=True)
    move_id = fields.Many2one('account.move',string='Journal Entry',readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('applied', 'Applied'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True, string='Status')
    last_calculation_date = fields.Date(string='Last Calculation Date')
    move_state = fields.Selection(related='move_id.state', string='Entry State')

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('installment.penalty') or 'New'
        return super().create(vals)

    @api.depends('delay_penalty_rate', 'installment_amount', 'number_of_periods')
    def _compute_penalty_amount(self):
        for rec in self:
            rec.penalty_amount = (rec.delay_penalty_rate) * rec.installment_amount * rec.number_of_periods


    def action_open_penalty_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Apply Penalty',
            'res_model': 'apply.penalty.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_penalty_id': self.id,
                'default_customer_id': self.customer_id.id,
                'default_number_of_periods': self.number_of_periods,
                'default_penalty_amount': self.penalty_amount,
            },
        }

    def action_view_journal_entry(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError('No journal entry exists for this penalty.')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entry',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.move_id.id,
            'target': 'current',
        }

    def action_cancel(self):
        self.ensure_one()
        if self.move_id and self.move_id.state == 'posted':
            raise UserError('Cannot cancel penalty with a posted journal entry.')
        if self.move_id and self.move_id.state == 'draft':
            self.move_id.unlink()
        self.write({'state': 'cancelled', 'move_id': False})

    @api.model
    def _cron_calculate_installment_penalties(self):
        today = fields.Date.today()
        contracts = self.env['sale.proposal'].search([
            ('state', 'in', ['signed_client', 'signed_ceo', 'ready_to_deliver', 'delivered'])
        ])
        
        for contract in contracts:
            if not contract.delay_payment or contract.delay_payment <= 0:
                continue
            
            for line in contract.installment_ids:
                if not line.date or line.date >= today:
                    continue
                # --- ALLOCATION LOGIC ---
                # Check the allocation table to see if there is ANY active cheque or payment attached to this line
                has_active_allocation = any(
                    (alloc.cheque_id and alloc.cheque_id.state not in ['cancel', 'return', 'return_to_client',
                                                                       'bounce']) or
                    (alloc.payment_id and alloc.payment_id.state not in ['canceled', 'draft'])
                    for alloc in line.allocation_ids
                )

                # Skip penalty if the line is already fully paid OR if there is an active payment/cheque allocated to it
                if line.paid or has_active_allocation:
                    continue
                
                delta = relativedelta(today, line.date)
                months_overdue = delta.years * 12 + delta.months
                if delta.days > 0:
                    months_overdue += 1

                existing_penalty = self.search([
                    ('installment_line_id', '=', line.id),
                    ('state', '!=', 'cancelled'),
                ], limit=1)
                
                if existing_penalty:
                    if months_overdue > existing_penalty.number_of_periods:
                        existing_penalty.write({
                            'number_of_periods': months_overdue,
                            'last_calculation_date': today,
                        })
                else:
                    self.create({
                        'sale_proposal_id': contract.id,
                        'installment_line_id': line.id,
                        'installment_due_date': line.date,
                        'installment_amount': line.amount,
                        'delay_penalty_rate': contract.delay_payment,
                        'number_of_periods': months_overdue,
                        'last_calculation_date': today,
                    })
        return True
