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
    _inherit = 'account.payment'

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

        Parameters = self.env['ir.config_parameter'].sudo()

        debit_account_id = Parameters.get_param('arkzayed_18_realestate_development.collection_debit_account_id')
        credit_gis_account_id = Parameters.get_param('arkzayed_18_realestate_development.collection_credit_gis_account_id')
        credit_oaya_account_id = Parameters.get_param('arkzayed_18_realestate_development.collection_credit_oaya_account_id')
        gis_percentage = float(Parameters.get_param('arkzayed_18_realestate_development.collection_gis_percentage') or 0)
        oaya_percentage = float(Parameters.get_param('arkzayed_18_realestate_development.collection_oaya_percentage') or 0)
        journal_id = Parameters.get_param('arkzayed_18_realestate_development.collection_journal_id')

        # get analytic accounts
        analytic_accounts = self.env['account.analytic.account']
        # get gis analytic account
        gis_analytic_accounts = analytic_accounts.search([('is_gis_account', '=', True)], limit=1)
        # get oaya analytic account
        oaya_analytic_account = analytic_accounts.search([('is_oaya_account', '=', True)], limit=1)

        if not all([debit_account_id, credit_gis_account_id, credit_oaya_account_id, journal_id]):
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning("Collection entry configuration incomplete in settings")
            return None

        total_amount = self.amount

        # Calculate amounts based on configured percentages
        gis_amount = round((total_amount * gis_percentage) / 100, 2)
        oaya_amount = round((total_amount * oaya_percentage) / 100, 2)

        # Total credit is sum of GIS + OAYA
        total_credit = gis_amount + oaya_amount

        # Debit amount matches the total credit to balance the entry
        debit_amount = total_credit

        moves_to_link = []


        move_vals = {
            'journal_id': int(journal_id),
            'date': self.date or fields.Date.today(),
            'ref': _('Collection - %s - %s') % (sale_proposal.name, self.name),
            'is_revenue_split_entry': True,
        }

        # Credit line 1 - GIS
        if gis_amount > 0:
            gis_move = self.env['account.move'].create(move_vals)
            gis_move.write({
                'line_ids':[
                    (0, 0, {
                        'name': _('Collection Expense - %s') % self.name,
                        'account_id': int(debit_account_id),
                        'partner_id': self.partner_id.id,
                        'debit': gis_amount,
                        'credit': 0.0,
                        'analytic_distribution':{
                            str(gis_analytic_accounts.id): 100.0,
                        }
                    })
                    ,(0, 0, {
                    'name': _('GIS Collection (%.2f%%) - %s') % (gis_percentage, self.name),
                    'account_id': int(credit_gis_account_id),
                    'partner_id': self.partner_id.id,
                    'debit': 0.0,
                    'credit': gis_amount,
                })
                ]})

            moves_to_link.append(gis_move.id)


        # Credit line 2 - OAYA
        if oaya_amount > 0:
            oaya_move = self.env['account.move'].create(move_vals)
            oaya_move.write({
                'line_ids':[
                    (0, 0, {
                        'name': _('Collection Expense - %s') % self.name,
                        'account_id': int(debit_account_id),
                        'partner_id': self.partner_id.id,
                        'debit': oaya_amount,
                        'credit': 0.0,
                        'analytic_distribution':{
                            str(oaya_analytic_account.id): 100.0,
                        }
                    })
                    ,(0, 0, {
                    'name': _('OAYA Collection (%.2f%%) - %s') % (oaya_percentage, self.name),
                    'account_id': int(credit_oaya_account_id),
                    'partner_id': self.partner_id.id,
                    'debit': 0.0,
                    'credit': oaya_amount,
                })]
            })

            moves_to_link.append(oaya_move.id)


        if moves_to_link:
            self.write({
                'collection_move_ids': [Command.link(m_id) for m_id in moves_to_link]
            })

        import logging
        _logger = logging.getLogger(__name__)
        _logger.info("Collection entry created successfully for payment %s: Moves ID %s and %s" % (self.name, moves_to_link[0], moves_to_link[1]))

        return moves_to_link
