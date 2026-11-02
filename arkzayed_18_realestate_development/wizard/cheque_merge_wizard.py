from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class ChequeMergeWizard(models.TransientModel):
    _name = 'cheque.merge.wizard'
    _description = 'Cheque Merge Wizard'

    name = fields.Char(string='Name', required=True)
    payer = fields.Many2one('res.partner', string='Partner', required=True)
    bank_id = fields.Many2one('res.bank', string='Bank')
    cheque_no = fields.Char(string='Cheque Number', required=True)
    amount = fields.Float(string='Amount', required=True)
    cheque_date = fields.Date(string='Cheque Date', required=True)
    cheque_receive_date = fields.Date(string='Cheque Receive Date', default=fields.Date.today, required=True)
    journal_id = fields.Many2one('account.journal', string='Journal', required=True)
    debit_account = fields.Many2one('account.account', string='Debit Account')
    description = fields.Text(string='Description')

    source_type = fields.Selection([
        ('installment', 'Installment'),
        ('maintenance', 'Maintenance')
    ], string='Source Type')
    unit_id = fields.Many2one('real.estate.unit', string='Unit')
    sale_proposal_id = fields.Many2one('sale.proposal', string='Sale Proposal')

    cheque_ids = fields.Many2many('cheque.manage', string='Cheques to Merge')

    @api.model
    def default_get(self, fields_list):
        res = super(ChequeMergeWizard, self).default_get(fields_list)

        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            return res

        cheques = self.env['cheque.manage'].browse(active_ids)

        for cheque in cheques:
            if cheque.cheq_type != 'incoming':
                raise ValidationError(_("Only incoming cheques can be merged."))
            if cheque.state != 'draft':
                raise ValidationError(_("Only draft cheques can be merged."))

        source_types = cheques.mapped('source_type')
        unique_source_types = list(set([st for st in source_types if st]))
        if len(unique_source_types) > 1:
            raise ValidationError(_("All selected cheques must have the same source type (Installment or Maintenance)."))

        payers = cheques.mapped('payer')
        if len(payers) > 1:
            raise ValidationError(_("All selected cheques must have the same payer."))

        proposals = cheques.mapped('sale_proposal_id')
        unique_proposals = proposals.filtered(lambda p: p)
        if len(unique_proposals) > 1:
            raise ValidationError(_("All selected cheques must belong to the same sale proposal."))

        first_cheque = cheques[0]

        total_amount = sum(cheques.mapped('amount'))

        # Get unit_id from cheque first, fallback to sale proposal's unit
        unit_id = False
        if first_cheque.unit_id:
            unit_id = first_cheque.unit_id.id
        elif unique_proposals and unique_proposals[0].unit_id:
            unit_id = unique_proposals[0].unit_id.id

        res.update({
            'cheque_ids': [(6, 0, cheques.ids)],
            'payer': first_cheque.payer.id,
            'bank_id': first_cheque.bank_id.id if first_cheque.bank_id else False,
            'journal_id': first_cheque.journal_id.id,
            'debit_account': first_cheque.debit_account.id if first_cheque.debit_account else False,
            'source_type': unique_source_types[0] if unique_source_types else False,
            'unit_id': unit_id,
            'sale_proposal_id': unique_proposals[0].id if unique_proposals else False,
            'amount': total_amount,
            'cheque_date': max(cheques.mapped('cheque_date')),  # Use latest date
            'name': _('Merged Cheque - %s') % first_cheque.payer.name,
            'description': _('Merged from cheques: %s') % ', '.join([c for c in cheques.mapped('cheque_no') if c]),
        })

        return res

    def action_merge_cheques(self):
        """Create a new merged cheque and mark original cheques as merged"""
        self.ensure_one()

        if not self.cheque_ids:
            raise ValidationError(_("No cheques selected for merging."))

        cheque_vals = {
            'name': self.name,
            'cheque_no': self.cheque_no,
            'payer': self.payer.id,
            'bank_id': self.bank_id.id if self.bank_id else False,
            'cheq_type': 'incoming',
            'amount': self.amount,
            'cheque_date': self.cheque_date,
            'cheque_receive_date': self.cheque_receive_date,
            'journal_id': self.journal_id.id,
            'debit_account': self.debit_account.id if self.debit_account else False,
            'state': 'draft',
            'description': self.description,
            'source_type': self.source_type,
            'is_consolidated': True,
        }

        if self.unit_id:
            cheque_vals['unit_id'] = self.unit_id.id
        if self.sale_proposal_id:
            cheque_vals['sale_proposal_id'] = self.sale_proposal_id.id

        merged_cheque = self.env['cheque.manage'].create(cheque_vals)

        for cheque in self.cheque_ids:
            cheque.write({
                'is_merged': True,
                'merged_into_id': merged_cheque.id,
                'state': 'cancel',
            })

        return {
            'name': _('Merged Cheque'),
            'type': 'ir.actions.act_window',
            'res_model': 'cheque.manage',
            'view_mode': 'form',
            'res_id': merged_cheque.id,
            'target': 'current',
        }

