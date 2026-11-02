import re

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


def _next_cheque_number(base, offset):
    """Increment the trailing number of ``base`` by ``offset`` keeping zero padding.
    '000123' -> '000124'; 'A-0009' -> 'A-0010'; no trailing digits -> appended."""
    if not base:
        return base
    m = re.match(r'^(.*?)(\d+)$', base)
    if not m:
        return base if offset == 0 else '%s%s' % (base, offset)
    prefix, digits = m.group(1), m.group(2)
    return '%s%s' % (prefix, str(int(digits) + offset).zfill(len(digits)))


class ChequeSplitWizard(models.TransientModel):
    _name = 'cheque.split.wizard'
    _description = 'Replace a Combined Cheque With Individual Cheques'

    cheque_id = fields.Many2one('cheque.manage', string='Original Cheque', required=True, readonly=True)
    cheque_state = fields.Selection(related='cheque_id.state', string='Original State', readonly=True)
    bank_id = fields.Many2one('res.bank', string='Bank')
    starting_number = fields.Char(string='Starting Cheque Number')
    return_reason_id = fields.Many2one('return.reason', string='Return Reason')
    line_ids = fields.One2many('cheque.split.wizard.line', 'wizard_id', string='Individual Cheques')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        cheque = self.env['cheque.manage'].browse(
            self.env.context.get('default_cheque_id') or self.env.context.get('active_id'))
        if not cheque:
            return res
        cheque._check_can_split()
        res['cheque_id'] = cheque.id
        res['bank_id'] = cheque.bank_id.id
        lines = []
        for alloc in cheque.allocation_ids:
            line = alloc.installment_id or alloc.maintenance_id
            lines.append((0, 0, {
                'installment_id': alloc.installment_id.id,
                'maintenance_id': alloc.maintenance_id.id,
                'sale_proposal_id': line.sale_proposal_id.id if line else False,
                'unit_id': line.unit_id.id if line and line.unit_id else False,
                'amount': alloc.allocated_amount,
                'cheque_date': line.date if line else cheque.cheque_date,
                'bank_id': cheque.bank_id.id,
            }))
        res['line_ids'] = lines
        return res

    @api.onchange('starting_number')
    def _onchange_starting_number(self):
        if not self.starting_number:
            return
        for idx, line in enumerate(self.line_ids):
            line.cheque_no = _next_cheque_number(self.starting_number, idx)

    def action_confirm(self):
        self.ensure_one()
        orig = self.cheque_id
        orig._check_can_split()

        if self.cheque_state == 'collect' and not self.return_reason_id:
            raise UserError(_("Please select a return reason to return the received cheque."))

        numbers = [l.cheque_no for l in self.line_ids if l.cheque_no]
        if len(numbers) != len(set(numbers)):
            raise UserError(_("Duplicate cheque numbers are not allowed."))

        # 1. Dispose of the original cheque
        if orig.state == 'draft':
            orig.write({'state': 'cancel'})
        elif orig.state == 'collect':
            orig.return_reason_id = self.return_reason_id
            orig.action_return()

        # 2. Create one individual draft cheque per line
        new_cheques = self.env['cheque.manage']
        Alloc = self.env['payment.allocation']
        for line in self.line_ids:
            source_type = 'installment' if line.installment_id else 'maintenance'
            nc = self.env['cheque.manage'].create({
                'cheq_type': 'incoming',
                'payer': orig.payer.id,
                'sale_proposal_id': line.sale_proposal_id.id,
                'from_contract': True,
                'source_type': source_type,
                'amount': line.amount,
                'bank_id': (line.bank_id or self.bank_id or orig.bank_id).id,
                'cheque_no': line.cheque_no or False,
                'cheque_date': line.cheque_date,
                'cheque_receive_date': fields.Date.today(),
                'journal_id': orig.journal_id.id,
                'company_id': orig.company_id.id,
                'state': 'draft',
            })
            alloc_vals = {'cheque_id': nc.id, 'allocated_amount': line.amount}
            if line.installment_id:
                alloc_vals['installment_id'] = line.installment_id.id
            else:
                alloc_vals['maintenance_id'] = line.maintenance_id.id
            Alloc.create(alloc_vals)
            new_cheques |= nc

        orig.message_post(body=_("Replaced by individual cheques: %s") % (
            ', '.join(new_cheques.mapped('seq_no')) or '-'))

        return {
            'name': _('Individual Cheques'),
            'type': 'ir.actions.act_window',
            'res_model': 'cheque.manage',
            'view_mode': 'list,form',
            'domain': [('id', 'in', new_cheques.ids)],
            'target': 'current',
        }


class ChequeSplitWizardLine(models.TransientModel):
    _name = 'cheque.split.wizard.line'
    _description = 'Cheque Split Wizard Line'

    wizard_id = fields.Many2one('cheque.split.wizard', ondelete='cascade')
    sale_proposal_id = fields.Many2one('sale.proposal', string='Contract')
    unit_id = fields.Many2one('real.estate.unit', string='Unit')
    installment_id = fields.Many2one('installment.lines')
    maintenance_id = fields.Many2one('maintenance.installment.lines')
    amount = fields.Float(string='Amount')
    cheque_date = fields.Date(string='Cheque Date')
    cheque_no = fields.Char(string='Cheque Number')
    bank_id = fields.Many2one('res.bank', string='Bank')
