# -*- coding: utf-8 -*-
from odoo import models, fields, api, _, Command
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    """Mode A coupling between the sales pipeline and the accounting layer.

    Phase 3 step 2b-a: moved here out of isky_18_realestate_developer_sales_crm so that
    sales_crm no longer hard-depends on the optional L1 accounting bridge. Everything here
    touches a bridge-owned field (custom_exchange_rate, converted_amount, is_overseas,
    overseas_payment_type, is_revenue_split_entry) or creates account.move records - i.e. it is
    all Mode A. With this module absent, sales_crm runs in Mode B and none of it exists.
    """
    # _name is required alongside a list _inherit when extending an existing model:
    # without it Odoo treats the class as a new anonymous model and the inherited
    # Many2many relations collide on their table names (the same lesson crm_lead.py
    # records; this run re-learned it from
    # "TypeError: Many2many fields ... use the same table and columns").
    _name = 'account.payment'
    _inherit = ['account.payment', 'realestate.revenue.split.mixin']

    # --- S6 guard pattern -------------------------------------------------------------
    # The base compute in sales_crm depends only on always-present paths. This redeclaration
    # adds this module's own paths and calls super(), so the field recomputes when the
    # user-edited exchange rate changes. Required by claude/scripts/lint_guard_pattern.py.
    @api.depends('amount', 'currency_id', 'date', 'company_id', 'allocation_ids.allocated_amount',
                 'custom_exchange_rate', 'converted_amount')
    def _compute_unallocated(self):
        return super()._compute_unallocated()

    def _get_amount_company_currency(self):
        """Mode A: honour a user-edited exchange rate when one is set, instead of the
        automatic currency rate used by the base implementation in sales_crm."""
        self.ensure_one()
        if self.currency_id != self.company_id.currency_id and self.custom_exchange_rate:
            return self.converted_amount
        return super()._get_amount_company_currency()

    # --- Mode A: revenue-split collection journal entry --------------------------------
    def _create_collection_journal_entry(self):
        """Create draft collection journal entry for returned cheque payments and overseas installment payments"""
        self.ensure_one()

        # Skip if collection entry already exists
        if len(self.collection_move_ids) >= 2:
            return None

        # Returned cheque payments: ONLY if selected cheques are Installment
        is_returned_cheque_installment = (
                self.is_returned_cheque
                and self.returned_cheque_ids
                and self.returned_source_type == 'installment'
        )

        # CONDITION 2: Overseas INSTALLMENT payment only (not maintenance)
        is_overseas_installment = (
                self.is_overseas and
                self.overseas_payment_type == 'installment' and
                self.installment_line_id and
                not self.maintenance_installment_line_id
        )

        # Only proceed if one of the conditions is met
        if not (is_returned_cheque_installment or is_overseas_installment):
            return None

        # Get sale proposal from multiple sources
        sale_proposal = None
        if self.installment_line_id and self.installment_line_id.sale_proposal_id:
            sale_proposal = self.installment_line_id.sale_proposal_id
        elif self.sale_proposal_id:
            sale_proposal = self.sale_proposal_id
        elif self.returned_cheque_ids:
            proposals = self.returned_cheque_ids.mapped('sale_proposal_id').filtered(lambda x: x)
            if len(proposals) > 1:
                raise ValidationError(
                    _("Selected cheques belong to different Sale Proposals. Please select cheques from the same contract."))
            sale_proposal = proposals[0] if proposals else None

        # If no sale proposal found, log warning and return
        if not sale_proposal:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning("Cannot create collection entry for payment %s: No sale proposal found" % self.name)
            return None

        # Phase 7 (D2/D3): business lines are rows, math shared through
        # realestate.revenue.split.mixin. This path keeps posting ONE move per business line and
        # keeps logging a warning when configuration is missing - only the source of the
        # accounts, percentages and analytic accounts changed.
        debit_account_id, journal_id, missing = self._revenue_split_posting_config()
        if missing:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning("Collection entry configuration incomplete: %s", ', '.join(missing))
            return None

        total_amount = self.amount
        split = self._revenue_split_amounts(total_amount)
        if not split:
            return None

        moves_to_link = []
        move_vals = {
            'journal_id': journal_id,
            'date': self.date or fields.Date.today(),
            'ref': _('Collection - %s - %s') % (sale_proposal.name, self.name),
            'is_revenue_split_entry': True,
        }

        for line, amount in split:
            analytic = ({str(line.analytic_account_id.id): 100.0}
                        if line.analytic_account_id else False)
            move = self.env['account.move'].create(move_vals)
            move.write({'line_ids': [
                (0, 0, self._revenue_split_debit_line(
                    debit_account_id, amount, self.name, self.partner_id.id, analytic)),
                (0, 0, self._revenue_split_credit_line(
                    line, amount, self.name, self.partner_id.id)),
            ]})
            moves_to_link.append(move.id)


        if moves_to_link:
            self.write({
                'collection_move_ids': [Command.link(m_id) for m_id in moves_to_link]
            })

        import logging
        _logger = logging.getLogger(__name__)
        _logger.info("Collection entry created successfully for payment %s: Moves ID %s and %s" % (self.name, moves_to_link[0], moves_to_link[1]))

        return moves_to_link
