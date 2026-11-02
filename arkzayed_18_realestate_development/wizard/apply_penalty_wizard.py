from odoo import models, fields
from odoo.exceptions import UserError


class ApplyPenaltyWizard(models.TransientModel):
    _name = 'apply.penalty.wizard'
    _description = 'Apply Penalty Wizard'

    penalty_id = fields.Many2one('installment.penalty',string='Penalty',required=True,readonly=True)
    customer_id = fields.Many2one('res.partner',string='Customer',readonly=True)
    number_of_periods = fields.Integer(string='Number of Periods',readonly=True)
    penalty_amount = fields.Float(string='Penalty Amount',required=True)

    def action_create_draft_entry(self):
        self.ensure_one()
        if self.penalty_amount <= 0:
            raise UserError('Penalty amount must be greater than zero.')
        if self.penalty_id.move_id:
            raise UserError('Journal entry already exists for this penalty.')
        params = self.env['ir.config_parameter'].sudo()
        debit_account_id = params.get_param('arkzayed_18_realestate_development.penalty_debit_account_id')
        credit_account_id = params.get_param('arkzayed_18_realestate_development.penalty_credit_account_id')
        journal_id = params.get_param('arkzayed_18_realestate_development.penalty_journal_id')
        
        if not debit_account_id or not credit_account_id:
            raise UserError('Please configure Penalty Debit and Credit Accounts in Accounting Settings.')
        
        if not journal_id:
            raise UserError('Please configure Penalty Journal in Accounting Settings.')
        
        journal = self.env['account.journal'].browse(int(journal_id))
        if not journal.exists():
            raise UserError('Configured Penalty Journal not found.')
        
        move_lines = [
            (0, 0, {
                'name': f'Delay Penalty - {self.penalty_id.name}',
                'account_id': int(debit_account_id),
                'partner_id': self.customer_id.id,
                'debit': self.penalty_amount,
                'credit': 0.0,
            }),
            (0, 0, {
                'name': f'Delay Penalty - {self.penalty_id.name}',
                'account_id': int(credit_account_id),
                'partner_id': self.customer_id.id,
                'debit': 0.0,
                'credit': self.penalty_amount,
            }),
        ]
        
        move_vals = {
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': f'Penalty: {self.penalty_id.sale_proposal_id.name} - {self.penalty_id.installment_line_id.name or ""}',
            'partner_id': self.customer_id.id,
            'penalty_id': self.penalty_id.id,
            'line_ids': move_lines,
        }
        move = self.env['account.move'].create(move_vals)
        self.penalty_id.write({
            'move_id': move.id,
            'state': 'applied',
            'penalty_amount': self.penalty_amount,
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entry',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
            'target': 'current',
        }

