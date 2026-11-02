from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

# Cheque states that still "cover" an installment line (mirror action_create_cheques).
_COVERING_CHEQUE_STATES_EXCLUDED = ('cancel', 'return', 'return_to_client', 'bounce')
_COVERING_PAYMENT_STATES_EXCLUDED = ('canceled', 'rejected')
_INVALID_CONTRACT_STATES = ('cancelled', 'terminated')


class CombinedChequeWizard(models.TransientModel):
    _name = 'combined.cheque.wizard'
    _description = 'Combined Cheque (one cheque, several contracts)'

    sale_proposal_id = fields.Many2one(
        'sale.proposal', string='Main Contract', required=True, readonly=True)
    customer_id = fields.Many2one(
        'res.partner', string='Customer', related='sale_proposal_id.customer_id', readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company)
    company_currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    contract_ids = fields.Many2many(
        'sale.proposal', 'combined_cheque_wizard_contract_rel', 'wizard_id', 'contract_id',
        string='Contracts',
        domain="[('customer_id', '=', customer_id), ('state', 'not in', ['cancelled', 'terminated'])]")
    unit_ids = fields.Many2many(
        'real.estate.unit', 'combined_cheque_wizard_unit_rel', 'wizard_id', 'unit_id',
        string='Units', compute='_compute_unit_ids', inverse='_inverse_unit_ids', store=True)

    bank_id = fields.Many2one('res.bank', string='Bank', required=True)
    cheque_no = fields.Char(string='Cheque Number')
    cheque_date = fields.Date(
        string='Cheque Date', compute='_compute_cheque_date', store=True, readonly=False,
        default=fields.Date.context_today)
    journal_id = fields.Many2one(
        'account.journal', string='Journal', required=True, default=lambda self: self._default_journal())
    replace_draft_cheques = fields.Boolean(string='Replace Existing Draft Cheques', default=True)

    line_ids = fields.One2many('combined.cheque.wizard.line', 'wizard_id', string='Installments')
    total_amount = fields.Monetary(
        string='Total', compute='_compute_totals', currency_field='company_currency_id')
    selected_count = fields.Integer(string='Selected', compute='_compute_totals')

    # ------------------------------------------------------------------ defaults
    @api.model
    def _default_journal(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'arkzayed_18_gt_cheque_management.journal_id')
        return int(param) if param else False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        main = self.env['sale.proposal'].browse(self.env.context.get('default_sale_proposal_id'))
        if not main:
            return res
        contracts = self.env['sale.proposal'].search([
            ('customer_id', '=', main.customer_id.id),
            ('state', 'not in', list(_INVALID_CONTRACT_STATES)),
        ])
        contracts |= main  # make sure the origin is always present
        res['sale_proposal_id'] = main.id
        res['contract_ids'] = [(6, 0, contracts.ids)]
        res['line_ids'] = self._build_line_commands(contracts, {})
        return res

    # ------------------------------------------------------------------ coverage
    def _line_coverage(self, line):
        """Return (amount_still_to_cover, replaceable_draft_cheque).
        A lone single-allocation DRAFT cheque does not count as covering the line and
        is returned so it can be replaced."""
        covered = 0.0
        replaceable_draft = self.env['cheque.manage']
        for alloc in line.allocation_ids:
            if alloc.payment_id and alloc.payment_id.state not in _COVERING_PAYMENT_STATES_EXCLUDED:
                covered += alloc.allocated_amount
            elif alloc.cheque_id and alloc.cheque_id.state not in _COVERING_CHEQUE_STATES_EXCLUDED:
                chq = alloc.cheque_id
                if chq.state == 'draft' and len(chq.allocation_ids) == 1:
                    replaceable_draft |= chq
                else:
                    covered += alloc.allocated_amount
        line_total = line.total_amount if line.total_amount else line.amount
        return max(0.0, line_total - covered), replaceable_draft[:1]

    def _build_line_commands(self, contracts, preserve):
        """Build One2many commands for every offerable installment/maintenance line of
        ``contracts``. ``preserve`` maps (line_type, line_id) -> (cover, amount)."""
        candidates = []
        for contract in contracts:
            for ltype, lines in (
                ('installment', contract.installment_ids),
                ('maintenance', contract.maintenance_installment_ids),
            ):
                for line in lines:
                    to_cover, draft = self._line_coverage(line)
                    if to_cover <= 0.01:
                        continue
                    candidates.append((ltype, line, to_cover, draft))
        # order by type then date then contract
        candidates.sort(key=lambda c: (
            0 if c[0] == 'installment' else 1,
            c[1].date is False,
            c[1].date or fields.Date.max,
            c[1].sale_proposal_id.id,
        ))
        commands = []
        for ltype, line, to_cover, draft in candidates:
            key = (ltype, line.id)
            kept_cover, kept_amount = preserve.get(key, (False, False))
            commands.append((0, 0, {
                'line_type': ltype,
                'installment_id': line.id if ltype == 'installment' else False,
                'maintenance_id': line.id if ltype == 'maintenance' else False,
                'sale_proposal_id': line.sale_proposal_id.id,
                'unit_id': line.unit_id.id if line.unit_id else False,
                'name': line.name,
                'due_date': line.date,
                'amount_to_cover': to_cover,
                'cover': kept_cover,
                'amount': kept_amount if kept_cover else to_cover,
                'existing_draft_cheque_id': draft.id if draft else False,
            }))
        return commands

    # ------------------------------------------------------------------ computes
    @api.depends('contract_ids', 'contract_ids.unit_id')
    def _compute_unit_ids(self):
        for wiz in self:
            wiz.unit_ids = wiz.contract_ids.mapped('unit_id')

    def _inverse_unit_ids(self):
        for wiz in self:
            contracts = wiz.sale_proposal_id
            for unit in wiz.unit_ids:
                if unit.sale_contract_id:
                    contracts |= unit.sale_contract_id
            wiz.contract_ids = contracts

    @api.onchange('unit_ids')
    def _onchange_unit_ids(self):
        contracts = self.sale_proposal_id
        for unit in self.unit_ids:
            real_unit = unit._origin or unit
            if not real_unit.sale_contract_id:
                raise ValidationError(
                    _("The unit '%s' is not linked to any contract.") % real_unit.display_name)
            contracts |= real_unit.sale_contract_id
        self.contract_ids = contracts

    @api.onchange('contract_ids')
    def _onchange_contract_ids(self):
        # the origin contract can never be removed
        if self.sale_proposal_id and self.sale_proposal_id not in self.contract_ids:
            self.contract_ids |= self.sale_proposal_id
        preserve = {
            ((l.line_type, (l.installment_id or l.maintenance_id).id)): (l.cover, l.amount)
            for l in self.line_ids if (l.installment_id or l.maintenance_id)
        }
        self.line_ids = [(5, 0, 0)] + self._build_line_commands(self.contract_ids, preserve)

    @api.depends('line_ids.cover', 'line_ids.due_date')
    def _compute_cheque_date(self):
        for wiz in self:
            dates = wiz.line_ids.filtered(lambda l: l.cover and l.due_date).mapped('due_date')
            if dates:
                wiz.cheque_date = min(dates)
            elif not wiz.cheque_date:
                wiz.cheque_date = fields.Date.context_today(wiz)

    @api.depends('line_ids.cover', 'line_ids.amount')
    def _compute_totals(self):
        for wiz in self:
            ticked = wiz.line_ids.filtered('cover')
            wiz.total_amount = sum(ticked.mapped('amount'))
            wiz.selected_count = len(ticked)

    # ------------------------------------------------------------------ confirm
    def action_confirm(self):
        self.ensure_one()
        ticked = self.line_ids.filtered('cover')
        if not ticked:
            raise UserError(_("Please tick at least one installment to cover."))

        types = set(ticked.mapped('line_type'))
        if len(types) > 1:
            raise UserError(_(
                "A single cheque can cover either installments OR maintenance lines, "
                "not both. Please tick one type only."))
        source_type = types.pop()

        for line in ticked:
            if line.amount <= 0.0:
                raise UserError(_("The amount for '%s' must be greater than zero.") % line.name)
            if round(line.amount, 2) > round(line.amount_to_cover, 2):
                raise UserError(_(
                    "The amount for '%(line)s' (%(amt).2f) exceeds the amount still to cover "
                    "(%(max).2f).", line=line.name, amt=line.amount, max=line.amount_to_cover))

        drafts_to_cancel = ticked.mapped('existing_draft_cheque_id')
        if drafts_to_cancel and not self.replace_draft_cheques:
            raise UserError(_(
                "Some ticked lines are already covered by a draft cheque. Enable "
                "'Replace Existing Draft Cheques' to replace them."))

        if not self.bank_id:
            raise UserError(_("Please select a bank for the cheque."))

        # Cancel the draft cheques we are replacing
        for chq in drafts_to_cancel:
            chq.message_post(body=_(
                "Cancelled and replaced by a combined cheque created from contract %s.")
                % self.sale_proposal_id.name)
            chq.write({'state': 'cancel'})

        additional = (ticked.mapped('sale_proposal_id') - self.sale_proposal_id)

        cheque = self.env['cheque.manage'].create({
            'cheq_type': 'incoming',
            'payer': self.customer_id.id,
            'sale_proposal_id': self.sale_proposal_id.id,
            'additional_proposal_ids': [(6, 0, additional.ids)],
            'from_contract': True,
            'source_type': source_type,
            'amount': sum(ticked.mapped('amount')),
            'bank_id': self.bank_id.id,
            'cheque_no': self.cheque_no or False,
            'cheque_date': self.cheque_date,
            'cheque_receive_date': fields.Date.today(),
            'journal_id': self.journal_id.id,
            'company_id': self.company_id.id,
            'state': 'draft',
        })

        Alloc = self.env['payment.allocation']
        for line in ticked:
            vals = {'cheque_id': cheque.id, 'allocated_amount': line.amount}
            if line.line_type == 'installment':
                vals['installment_id'] = line.installment_id.id
            else:
                vals['maintenance_id'] = line.maintenance_id.id
            Alloc.create(vals)

        return {
            'name': _('Combined Cheque'),
            'type': 'ir.actions.act_window',
            'res_model': 'cheque.manage',
            'view_mode': 'form',
            'res_id': cheque.id,
            'target': 'current',
        }


class CombinedChequeWizardLine(models.TransientModel):
    _name = 'combined.cheque.wizard.line'
    _description = 'Combined Cheque Wizard Line'
    _order = 'line_type, due_date, id'

    wizard_id = fields.Many2one('combined.cheque.wizard', ondelete='cascade')
    currency_id = fields.Many2one(related='wizard_id.company_currency_id', readonly=True)

    cover = fields.Boolean(string='Cover')
    sale_proposal_id = fields.Many2one('sale.proposal', string='Contract')
    unit_id = fields.Many2one('real.estate.unit', string='Unit')
    line_type = fields.Selection(
        [('installment', 'Installment'), ('maintenance', 'Maintenance')], string='Type')
    installment_id = fields.Many2one('installment.lines')
    maintenance_id = fields.Many2one('maintenance.installment.lines')
    name = fields.Char(string='Installment')
    due_date = fields.Date(string='Due Date')
    amount_to_cover = fields.Monetary(string='Still to Cover', currency_field='currency_id')
    amount = fields.Monetary(string='Amount', currency_field='currency_id')
    existing_draft_cheque_id = fields.Many2one('cheque.manage', string='Existing Draft Cheque')
