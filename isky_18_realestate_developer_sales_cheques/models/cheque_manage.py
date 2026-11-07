from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)


class ChequeManage(models.Model):
    # _name is required alongside a list _inherit when extending an existing model:
    # without it Odoo treats the class as a new anonymous model and the inherited
    # Many2many relations collide on their table names (the same lesson crm_lead.py
    # records; this run re-learned it from
    # "TypeError: Many2many fields ... use the same table and columns").
    _name = 'cheque.manage'
    _inherit = ['cheque.manage', 'realestate.revenue.split.mixin']

    eoi_id = fields.Many2one('eoi.eoi', string='EOI')
    installment_line_id = fields.Many2one('installment.lines', string='Installment Line')
    maintenance_installment_line_id = fields.Many2one('maintenance.installment.lines', string='Maintenance Installment Line')
    sale_proposal_id = fields.Many2one('sale.proposal', string='Sale Proposal')
    sale_reservation_id = fields.Many2one('real.estate.sale.reservation', string='Sale Reservation')
    from_down_payment = fields.Boolean()
    source_type = fields.Selection([
        ('installment', 'Installment'),
        ('maintenance', 'Maintenance')
    ], string='Source Type', readonly=True)

    collection_move_id = fields.Many2one(
        'account.move',
        string='Collection Journal Entry',
        readonly=True,
        copy=False
    )
    collection_entry_count = fields.Integer(
        string='Collection Entries',
        compute='_compute_collection_entry_count'
    )

    unit_id = fields.Many2one(
        'real.estate.unit',
        string='Unit',
        copy=False,
        tracking=True,
        compute='_compute_unit_id',
        store=True,
    )
    returned_payment_id = fields.Many2one(
        'account.payment',
        string='Returned Payment',
        copy=False
    )
    is_returned_paid = fields.Boolean(
        string='Returned Paid',
        default=False,
        copy=False
    )
    reservation_payment_id = fields.Many2one('reservation.payment')
    eoi_payment_id = fields.Many2one('eoi.payment')
    from_eoi = fields.Boolean(string='Related To EOI', default=False, help='Indicates if the cheque is created from an EOI', copy=False)
    from_reservation = fields.Boolean(string='Related To Reservation', default=False, copy=False)
    from_contract = fields.Boolean(string='Related To Contract', default=False, copy=False)

    allocation_ids = fields.One2many('payment.allocation', 'cheque_id', string='Allocations')
    unallocated_amount = fields.Float(string='Unallocated Balance', compute='_compute_unallocated', store=True)

    available_installment_ids = fields.Many2many(
        'installment.lines',
        compute='_compute_available_allocations',
        string='Available Installments'
    )
    available_maintenance_ids = fields.Many2many(
        'maintenance.installment.lines',
        compute='_compute_available_allocations',
        string='Available Maintenance'
    )
    realestate_related_seq = fields.Char(string='Realestate Related Sequence', copy=False)

    # A single customer cheque may settle installments of several of the payer's
    # contracts. sale_proposal_id stays the MAIN contract; these are the extra ones.
    additional_proposal_ids = fields.Many2many(
        'sale.proposal',
        'cheque_manage_additional_proposal_rel',
        'cheque_id', 'proposal_id',
        string='Additional Contracts',
        copy=False,
    )
    additional_unit_ids = fields.Many2many(
        'real.estate.unit',
        'cheque_manage_additional_unit_rel',
        'cheque_id', 'unit_id',
        string='Additional Units',
        compute='_compute_additional_unit_ids',
        inverse='_inverse_additional_unit_ids',
        store=True,
    )

    @api.depends('additional_proposal_ids', 'additional_proposal_ids.unit_id')
    def _compute_additional_unit_ids(self):
        for rec in self:
            rec.additional_unit_ids = rec.additional_proposal_ids.mapped('unit_id')

    def _inverse_additional_unit_ids(self):
        """Keep additional_proposal_ids in sync when units are set directly.
        A unit belongs to exactly one contract (unit.sale_contract_id)."""
        for rec in self:
            proposals = rec.env['sale.proposal']
            for unit in rec.additional_unit_ids:
                contract = unit.sale_contract_id
                if not contract:
                    raise ValidationError(
                        _("The unit '%s' is not linked to any contract.") % unit.display_name)
                proposals |= contract
            rec.additional_proposal_ids = proposals

    @api.onchange('additional_unit_ids')
    def _onchange_additional_unit_ids(self):
        """Picking an additional unit fills the matching contract.
        In onchange the units are NewId records, so resolve the real record first."""
        proposals = self.env['sale.proposal']
        for unit in self.additional_unit_ids:
            real_unit = unit._origin or unit
            contract = real_unit.sale_contract_id
            if not contract:
                raise ValidationError(
                    _("The unit '%s' is not linked to any contract.") % real_unit.display_name)
            proposals |= contract
        self.additional_proposal_ids = proposals

    @api.constrains('additional_proposal_ids', 'sale_proposal_id', 'payer')
    def _check_additional_proposals(self):
        for rec in self:
            if not rec.additional_proposal_ids:
                continue
            if not rec.sale_proposal_id:
                raise ValidationError(
                    _("Please set the main Sale Proposal before adding additional contracts."))
            if rec.sale_proposal_id in rec.additional_proposal_ids:
                raise ValidationError(
                    _("The main contract (%s) cannot also be listed as an additional contract.")
                    % rec.sale_proposal_id.name)
            wrong = rec.additional_proposal_ids.filtered(lambda p: p.customer_id != rec.payer)
            if wrong:
                raise ValidationError(_(
                    "These additional contracts do not belong to the payer (%(payer)s): %(contracts)s",
                    payer=rec.payer.display_name or '',
                    contracts=', '.join(wrong.mapped('name')),
                ))

    @api.depends(
        'sale_proposal_id', 'additional_proposal_ids', 'sale_reservation_id',
        'allocation_ids.installment_id', 'allocation_ids.maintenance_id'
    )
    def _compute_available_allocations(self):
        for rec in self:
            proposals = rec.sale_proposal_id | rec.additional_proposal_ids
            reservation = rec.sale_reservation_id

            all_inst = proposals.mapped('installment_ids') | \
                       (reservation.installment_ids if reservation else self.env['installment.lines'])
            all_maint = proposals.mapped('maintenance_installment_ids') | \
                        (reservation.maintenance_installment_ids if reservation else self.env[
                            'maintenance.installment.lines'])

            # Unpaid lines
            unpaid_inst = all_inst.filtered(lambda l: l.remaining_amount > 0)
            unpaid_maint = all_maint.filtered(lambda l: l.remaining_amount > 0)

            # Lines already selected in allocation table
            selected_inst = rec.allocation_ids.mapped('installment_id')
            selected_maint = rec.allocation_ids.mapped('maintenance_id')

            # Filter out selected lines from dropdown options
            rec.available_installment_ids = unpaid_inst - selected_inst
            rec.available_maintenance_ids = unpaid_maint - selected_maint

    @api.depends('amount', 'allocation_ids.allocated_amount')
    def _compute_unallocated(self):
        for rec in self:
            total_allocated = sum(rec.allocation_ids.mapped('allocated_amount'))
            rec.unallocated_amount = max(0.0, rec.amount - total_allocated)

    def unlink(self):
        for rec in self:
            if rec.sale_reservation_id:
                sale_contracts = self.env['sale.proposal'].search([('sale_contract_reservation_id', '=', rec.sale_reservation_id.id)])
                if (sale_contracts or rec.sale_reservation_id.sale_reservation_proposal_id) and not self.env.user.has_group('arkzayed_18_realestate_development.delete_payment_with_reservation_contract_group'):
                    raise ValidationError("You are not allowed to delete check with reservation proposal.")
                else:
                    rec.sale_reservation_id.state = 'reserved'

                if rec.reservation_payment_id:
                    rec.reservation_payment_id.is_payment_created = False

                if rec.eoi_payment_id:
                    rec.eoi_payment_id.is_payment_created = False
        return super().unlink()

    @api.depends('collection_move_id')
    def _compute_collection_entry_count(self):
        for rec in self:
            rec.collection_entry_count = 1 if rec.collection_move_id else 0

    def action_view_collection_entry(self):
        """Smart button to view collection journal entry"""
        self.ensure_one()
        if not self.collection_move_id:
            raise UserError(_("No collection journal entry has been created yet."))

        return {
            'name': _('Collection Journal Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.collection_move_id.id,
            'target': 'current',
        }

    def _get_partner_account(self, account_type='receivable'):
        """
        Get the appropriate partner account based on whether this is an EOI cheque
        or a regular cheque.

        :param account_type: 'receivable' or 'payable'
        :return: account.account recordset
        """
        self.ensure_one()

        # Check if this is an EOI cheque
        if not self.sale_proposal_id and (self.eoi_id or self.sale_reservation_id):
            # Use down payment accounts for EOI/Sale Reservation
            if account_type == 'receivable':
                if not self.payer.property_account_down_payment_receivable_id:
                    raise ValidationError(
                        "Please set 'Account Down Payment Receivable' for partner %s" % self.payer.name
                    )
                return self.payer.property_account_down_payment_receivable_id
            else:  # payable
                if not self.payer.property_account_down_payment_payable_id:
                    raise ValidationError(
                        "Please set 'Account Down Payment Payable' for partner %s" % self.payer.name
                    )
                return self.payer.property_account_down_payment_payable_id
        else:
            # Use regular accounts for non-EOIcheques
            if account_type == 'receivable':
                return self.payer.property_account_receivable_id
            else:  # payable
                return self.payer.property_account_payable_id

    def cheque_collect(self):
        """Override to use down payment accounts for EOI cheques"""
        Move = self.env['account.move']

        if not self.company_id.received_checks:
            raise UserError(
                "Journal and company received checks cannot be empty for cheque with sequence %s" % self.seq_no
            )

        if self.cheq_type == 'incoming':
            # Use the helper method to get the correct account
            partner_account = self._get_partner_account('receivable')

            credit_line = {
                'account_id': partner_account.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line = {
                'account_id': self.company_id.received_checks.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            self.write({'state': 'collect'})
        else:  # outgoing
            partner_account = self._get_partner_account('payable')

            credit_line = {
                'account_id': self.credit_account.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line = {
                'account_id': partner_account.id if not self.is_owner else self.equity_account_id.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            self.write({'state': 'collect'})

        move_vals = {
            'date': self.cheque_receive_date or fields.Date.today(),
            'journal_id': self.journal_id.id,
            'ref': self.seq_no,
            'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
        }
        move_id = Move.create(move_vals)
        self.move_id = move_id.id
        move_id.action_post()

    def action_return(self, date=None):
        """Override to use down payment accounts for EOIcheques"""
        # Check if return reason is provided
        if not self.return_reason_id:
            raise ValidationError(_("Please select a return reason before returning the cheque."))

        state = 'return' if self.state == 'collect' else 'return_to_client'

        if self.bounced:
            for rec in self:
                for move in rec.move_line_ids.mapped('move_id'):
                    move.button_cancel()
                result = rec.write({'state': state, 'return_date': fields.Date.today()})
                # Update EOI status if cheque is returned
                if rec.eoi_id and state == 'return':
                    rec.eoi_id.write({'status': 'refunded'})
                return result
        else:
            Move = self.env['account.move']

            if self.state == 'collect':
                if self.cheq_type == 'incoming':
                    # Use the helper method to get the correct account
                    partner_account = self._get_partner_account('receivable')

                    credit_line = {
                        'account_id': self.company_id.received_checks.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': 0,
                        'credit': self.amount,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                    debit_line = {
                        'account_id': partner_account.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': self.amount,
                        'credit': 0,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                else:  # outgoing
                    partner_account = self._get_partner_account('payable')

                    credit_line = {
                        'account_id': partner_account.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': 0,
                        'credit': self.amount,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                    debit_line = {
                        'account_id': self.credit_account.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': self.amount,
                        'credit': 0,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }

                move_vals = {
                    'date': date or fields.Date.today(),
                    'journal_id': self.journal_id.id,
                    'ref': self.seq_no,
                    'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
                }
                move_id = Move.create(move_vals)
                move_id.action_post()

            elif self.state == 'register':
                if not self.company_id.return_account:
                    raise ValidationError(_("Please set the Return Account in company settings"))
                if self.cheq_type == 'incoming':
                    credit_line1 = {
                        'account_id': self.debit_account.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': 0,
                        'credit': self.amount,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                    debit_line1 = {
                        'account_id': self.company_id.return_account.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': self.amount,
                        'credit': 0,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                else:  # outgoing
                    credit_line1 = {
                        'account_id': self.company_id.return_account.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': 0,
                        'credit': self.amount,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                    debit_line1 = {
                        'account_id': self.credit_account.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': self.amount,
                        'credit': 0,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }

                move_vals1 = {
                    'date': date or fields.Date.today(),
                    'journal_id': self.journal_id.id,
                    'ref': self.seq_no,
                    'line_ids': [(0, 0, credit_line1), (0, 0, debit_line1)]
                }
                move_id1 = Move.create(move_vals1)
                move_id1.action_post()

            result = self.write({'state': state, 'return_date': fields.Date.today()})

            # Update EOI status if cheque is returned
            if self.eoi_id and state == 'return':
                self.eoi_id.write({'status': 'refunded'})

            return result

    def action_return_to_client(self):
        """Override to use down payment accounts for EOI cheques"""
        # Check if return reason is provided
        if not self.return_reason_id:
            raise ValidationError(_("Please select a return reason before returning the cheque to client."))

        if self.bounced:
            for rec in self:
                for move in rec.move_line_ids.mapped('move_id'):
                    move.button_cancel()
                result = rec.write({'state': 'return', 'return_date': fields.Date.today()})
                # Update EOI status if cheque is returned
                if rec.eoi_id:
                    rec.eoi_id.write({'status': 'refunded'})
                return result
        else:
            Move = self.env['account.move']

            if self.state == 'return_to_client':
                if self.cheq_type == 'incoming':
                    # Use the helper method to get the correct account
                    partner_account = self._get_partner_account('receivable')

                    credit_line = {
                        'account_id': self.company_id.received_checks.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': 0,
                        'credit': self.amount,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                    debit_line = {
                        'account_id': partner_account.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': self.amount,
                        'credit': 0,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                else:  # outgoing
                    partner_account = self._get_partner_account('payable')

                    credit_line = {
                        'account_id': partner_account.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': 0,
                        'credit': self.amount,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }
                    debit_line = {
                        'account_id': self.company_id.outgoing_checks.id,
                        'partner_id': self.payer.id,
                        'name': self.name,
                        'debit': self.amount,
                        'credit': 0,
                        'date_maturity': self.cheque_date,
                        'cheque_id': self.id,
                    }

                move_vals = {
                    'date': fields.Date.today(),
                    'journal_id': self.journal_id.id,
                    'ref': self.seq_no,
                    'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
                }
                move_id = Move.create(move_vals)
                move_id.action_post()

            result = self.write({'state': 'return', 'return_date': fields.Date.today()})

            # Update EOI status if cheque is returned
            if self.eoi_id:
                self.eoi_id.write({'status': 'refunded'})

            return result

    def action_bounce(self, journal_id=None, date=None):
        """Override to use down payment accounts for EOI cheques"""
        Move = self.env['account.move']

        if self.cheq_type == 'incoming':
            partner_account = self._get_partner_account('receivable')

            credit_line = {
                'account_id': self.under_collection_account_id.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line = {
                'account_id': journal_id.default_account_id.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            credit_line_1 = {
                'account_id': partner_account.id if not self.is_owner else self.equity_account_id.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line_1 = {
                'account_id': self.company_id.received_checks.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
        else:  # outgoing
            partner_account = self._get_partner_account('payable')

            credit_line = {
                'account_id': journal_id.default_account_id.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line = {
                'account_id': self.credit_account.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            credit_line_1 = {
                'account_id': self.company_id.outgoing_checks.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line_1 = {
                'account_id': partner_account.id if not self.is_owner else self.equity_account_id.id,
                'partner_id': self.payer.id,
                'name': self.name,
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }

        move_vals = {
            'date': date,
            'journal_id': self.journal_id.id,
            'ref': self.seq_no,
            'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
        }
        move_vals_two = {
            'date': date,
            'journal_id': self.journal_id.id,
            'ref': self.seq_no,
            'line_ids': [(0, 0, credit_line_1), (0, 0, debit_line_1)]
        }
        move_id = Move.create(move_vals)
        move_id_two = Move.create(move_vals_two)
        move_id.action_post()
        move_id_two.action_post()
        return self.write({'state': 'bounce', 'bounced': True})

    def _validate_allocations_on_confirm(self):
        """Validate allocations before confirming cheque"""
        for cheque in self:
            # Force validation if linked to contract/reservation OR if allocation lines exist
            if cheque.sale_proposal_id or cheque.sale_reservation_id or cheque.allocation_ids:
                total_allocated = sum(cheque.allocation_ids.mapped('allocated_amount'))
                if round(total_allocated, 2) != round(cheque.amount, 2):
                    raise ValidationError(_(
                        "Cannot confirm cheque: The total allocated amount (%(alloc).2f) must be equal to the cheque amount (%(amt).2f).\n"
                        "Unallocated Balance: %(unalloc).2f",
                        alloc=total_allocated,
                        amt=cheque.amount,
                        unalloc=cheque.unallocated_amount
                    ))

                for alloc in cheque.allocation_ids:
                    line = alloc.installment_id or alloc.maintenance_id
                    if line and round(alloc.allocated_amount, 2) > round(line.remaining_amount, 2):
                        # Name the contract/reservation the line itself belongs to, which
                        # may be an additional contract rather than the cheque's main one.
                        line_ref = line.sale_proposal_id or line.reservation_id
                        ref_name = line_ref.name if line_ref else ""
                        raise ValidationError(_(
                            "Cannot confirm cheque: For line '%(line)s' in %(ref)s, "
                            "the allocated amount (%(alloc).2f) is greater than the line remaining amount (%(rem).2f).",
                            line=line.name,
                            ref=ref_name,
                            alloc=alloc.allocated_amount,
                            rem=line.remaining_amount
                        ))

    def _check_can_split(self):
        """Guard for the Replace-With-Individual-Cheques wizard."""
        self.ensure_one()
        if self.cheq_type != 'incoming':
            raise UserError(_("Only incoming cheques can be replaced with individual cheques."))
        if self.state not in ('draft', 'collect'):
            raise UserError(_("Only cheques in Draft or Received state can be replaced."))
        if len(self.allocation_ids) < 2:
            raise UserError(_("This cheque must have at least two allocations to be split."))
        total = sum(self.allocation_ids.mapped('allocated_amount'))
        if round(total, 2) != round(self.amount, 2):
            raise UserError(_(
                "The cheque's allocations (%(alloc).2f) must equal its amount (%(amt).2f) "
                "before splitting.", alloc=total, amt=self.amount))

    def action_open_split_wizard(self):
        """Open the wizard that replaces this combined cheque with one cheque per line."""
        self.ensure_one()
        self._check_can_split()
        return {
            'name': _('Replace With Individual Cheques'),
            'type': 'ir.actions.act_window',
            'res_model': 'cheque.split.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_cheque_id': self.id},
        }

    def write(self, vals):
        """Override write to trigger collection entry and broker claim checks when cheque state changes to done"""
        old_states = {record.id: record.state for record in self}
        result = super(ChequeManage, self).write(vals)

        if 'state' in vals:
            for record in self:
                if vals.get('state') == 'done' and old_states.get(record.id) != 'done':

                    if record.source_type == 'installment':
                        moves = record.move_line_ids.mapped('move_id')
                        last_move = moves.sorted('id')[-1:]
                        if last_move:
                            last_move.write({'is_collection': True})

                    elif record.source_type == 'maintenance':
                        moves = record.move_line_ids.mapped('move_id')
                        last_move = moves.sorted('id')[-1:]
                        if last_move:
                            last_move.write({'is_maintenance_collection': True})

                    if record.sale_proposal_id and not record.collection_move_id and record.source_type == 'installment':
                        try:
                            record._create_collection_journal_entry()
                        except Exception as e:
                            pass

                    if record.additional_proposal_ids:
                        # Multi-contract cheque: refresh every contract this cheque
                        # settles (collection amounts for all; claims for the ones
                        # settled through installment lines).
                        alloc_insts = record.allocation_ids.mapped('installment_id')
                        alloc_maints = record.allocation_ids.mapped('maintenance_id')
                        proposals = (
                            alloc_insts.mapped('sale_proposal_id')
                            | alloc_maints.mapped('sale_proposal_id')
                        ).filtered(lambda p: p)
                        for sale_proposal in proposals:
                            has_inst = bool(alloc_insts.filtered(lambda l: l.sale_proposal_id == sale_proposal))
                            sale_proposal._compute_collection_amounts()
                            if has_inst and sale_proposal._is_commission_eligible():
                                if sale_proposal.referred_by == 'broker':
                                    sale_proposal._check_and_create_broker_claim()
                                sale_proposal._check_and_create_non_sales_claims()
                    elif record.installment_line_id and record.installment_line_id.sale_proposal_id:
                        sale_proposal = record.installment_line_id.sale_proposal_id
                        if sale_proposal._is_commission_eligible():
                            sale_proposal._compute_collection_amounts()
                            if sale_proposal.referred_by == 'broker':
                                sale_proposal._check_and_create_broker_claim()
                            sale_proposal._check_and_create_non_sales_claims()

        return result

    def _create_collection_journal_entry(self):
        """Create draft collection journal entry for cheques from sale proposals"""
        self.ensure_one()

        if not self.sale_proposal_id or self.collection_move_id:
            return None

        # Phase 7 (D2/D3): business lines are rows, math shared through
        # realestate.revenue.split.mixin. This path returns quietly when configuration is
        # missing, as it did before.
        debit_account_id, journal_id, missing = self._revenue_split_posting_config()
        if missing:
            return None

        total_amount = self.amount
        split = self._revenue_split_amounts(total_amount)
        if not split:
            return None
        total_credit = sum(amount for _line, amount in split)

        line_ids = [(0, 0, self._revenue_split_debit_line(
            debit_account_id, total_credit, self.name, self.payer.id))]
        for line, amount in split:
            line_ids.append((0, 0, self._revenue_split_credit_line(
                line, amount, self.name, self.payer.id)))

        move_vals = {
            'journal_id': journal_id,
            'date': self.cashed_date or self.cheque_date or fields.Date.today(),
            'ref': _('Collection - %s - %s') % (self.sale_proposal_id.name, self.seq_no),
            'line_ids': line_ids,
            'is_revenue_split_entry': True,
        }

        move = self.env['account.move'].create(move_vals)
        self.collection_move_id = move.id

        return move

    def under_collection_action(self):
        # Validate allocations BEFORE state collect
        self._validate_allocations_on_confirm()
        return super().under_collection_action()


    # ----------------------------------------------------------------------------------
    # S8 / backlog #34: the incoming credit account.
    #
    # cheque.manage.credit_account is required=True and NOT NULL on a fresh database, and no
    # cheque-creating call site anywhere supplies it. The legacy default_get() resolves
    # debit_inc_account for incoming cheques and credit_out_account for outgoing ones, then
    # writes BOTH keys unconditionally - so for an incoming cheque it forces credit_account
    # back to None, overwriting whatever the caller asked for.
    #
    # Rather than patch each of the 11 create() call sites (4 of which are in the legacy
    # monolith's wizards and off limits per CLAUDE.md), both fixes land on this model: the
    # create() override below is the single choke point every caller passes through.
    # ----------------------------------------------------------------------------------

    SETTING_LABEL = "Settings > Real Estate Cheques > Financials > Incoming Cheque Credit Account"

    @api.model
    def default_get(self, fields_list):
        """Stop the legacy override from discarding a caller's credit account, and fall back
        to the company setting. Only ever fills a blank - never replaces a real value."""
        res = super().default_get(fields_list)
        if res.get('credit_account'):
            return res
        # the legacy default_get sets 'credit_account': None unconditionally when the journal
        # parameter is set, which wipes a default_credit_account context key. Put it back.
        ctx_val = self.env.context.get('default_credit_account')
        if ctx_val:
            res['credit_account'] = ctx_val
        elif (res.get('cheq_type') or self.env.context.get('default_cheq_type')) != 'outgoing':
            account = self.env.company.cheque_incoming_credit_account_id
            if account:
                res['credit_account'] = account.id
        return res

    @api.model
    def _resolve_incoming_credit_account(self, values):
        """Fill credit_account for an incoming cheque from the company setting, or refuse with
        a UserError naming the setting. Guarantees the NOT NULL constraint is never the first
        thing to fail.

        A value the caller supplied always wins. Outgoing cheques are left exactly as they
        were: their credit account comes from the legacy credit_out_account parameter, and S8
        changes no behaviour outside the incoming path.
        """
        if values.get('credit_account'):
            return values

        cheq_type = values.get('cheq_type') or self.env.context.get('default_cheq_type')
        if cheq_type == 'outgoing':
            return values

        account_id = self.env.context.get('default_credit_account')
        if not account_id:
            account_id = self.env.company.cheque_incoming_credit_account_id.id
        if not account_id:
            raise UserError(_(
                "No incoming cheque credit account is configured for company '%(company)s', "
                "so this cheque cannot be created.\n\n"
                "Set it in %(setting)s "
                "(field cheque_incoming_credit_account_id).",
                company=self.env.company.name,
                setting=self.SETTING_LABEL,
            ))
        values['credit_account'] = account_id
        return values

    @api.model
    def create(self, values):
        values = self._resolve_incoming_credit_account(dict(values))
        proposal_id = values.get('sale_proposal_id')
        reservation_id = values.get('sale_reservation_id')
        eoi_id = values.get('eoi_id')
        unit_id = values.get('unit_id')

        # 1. Resolve from Sale Proposal
        if proposal_id:
            proposal = self.env['sale.proposal'].browse(proposal_id)
            if not reservation_id and proposal.sale_contract_reservation_id:
                reservation_id = proposal.sale_contract_reservation_id.id
                values['sale_reservation_id'] = reservation_id
            if not eoi_id:
                eoi = proposal.eoi_id or (
                    proposal.sale_contract_reservation_id.eoi_id
                    if proposal.sale_contract_reservation_id else False
                )
                if eoi:
                    eoi_id = eoi.id
                    values['eoi_id'] = eoi_id
            if not unit_id and proposal.unit_id:
                unit_id = proposal.unit_id.id
                values['unit_id'] = unit_id

        # 2. Resolve from Sale Reservation
        if reservation_id:
            reservation = self.env['real.estate.sale.reservation'].browse(reservation_id)
            if not eoi_id and reservation.eoi_id:
                eoi_id = reservation.eoi_id.id
                values['eoi_id'] = eoi_id
            if not unit_id and reservation.unit_id:
                unit_id = reservation.unit_id.id
                values['unit_id'] = unit_id
            if not proposal_id:
                proposal = self.env['sale.proposal'].search([
                    ('sale_contract_reservation_id', '=', reservation_id),
                    ('state', '!=', 'cancelled')
                ], limit=1)
                if proposal:
                    proposal_id = proposal.id
                    values['sale_proposal_id'] = proposal_id

        # 3. Resolve from EOI
        if eoi_id and not (reservation_id or proposal_id):
            reservation = self.env['real.estate.sale.reservation'].search([
                ('eoi_id', '=', eoi_id),
                ('state', 'not in', ['cancelled', 'expired'])
            ], limit=1)
            proposal = self.env['sale.proposal'].search([
                ('eoi_id', '=', eoi_id),
                ('state', '!=', 'cancelled')
            ], limit=1)
            if proposal:
                values['sale_proposal_id'] = proposal.id
                if proposal.unit_id and not unit_id:
                    values['unit_id'] = proposal.unit_id.id
                if proposal.sale_contract_reservation_id and not reservation_id:
                    values['sale_reservation_id'] = proposal.sale_contract_reservation_id.id
            elif reservation:
                values['sale_reservation_id'] = reservation.id
                if reservation.unit_id and not unit_id:
                    values['unit_id'] = reservation.unit_id.id

        # 4. Resolve from Unit
        if unit_id and not (proposal_id or reservation_id):
            proposal = self.env['sale.proposal'].search([
                ('unit_id', '=', unit_id),
                ('state', '!=', 'cancelled')
            ], limit=1, order='create_date desc')
            reservation = self.env['real.estate.sale.reservation'].search([
                ('unit_id', '=', unit_id),
                ('state', 'not in', ['cancelled', 'expired'])
            ], limit=1, order='create_date desc')

            if proposal:
                values['sale_proposal_id'] = proposal.id
                if proposal.sale_contract_reservation_id and not reservation_id:
                    values['sale_reservation_id'] = proposal.sale_contract_reservation_id.id
                if proposal.eoi_id and not eoi_id:
                    values['eoi_id'] = proposal.eoi_id.id
            elif reservation:
                values['sale_reservation_id'] = reservation.id
                if reservation.eoi_id and not eoi_id:
                    values['eoi_id'] = reservation.eoi_id.id

        # 5. Resolve Payer ID from Proposal, Reservation, or EOI
        if not values.get('payer'):
            payer_id = False
            if proposal_id:
                proposal = self.env['sale.proposal'].browse(proposal_id)
                payer_id = proposal.customer_id.id
            elif reservation_id:
                reservation = self.env['real.estate.sale.reservation'].browse(reservation_id)
                payer_id = reservation.customer_id.id
            elif eoi_id:
                eoi = self.env['eoi.eoi'].browse(eoi_id)
                payer_id = eoi.customer_id.id

            if payer_id:
                values['payer'] = payer_id

        res =  super(ChequeManage, self).create(values)

        for check in res:
            if check.from_eoi:
                check.realestate_related_seq = self.env['ir.sequence'].next_by_code('eoi.account.payment')
            elif check.from_reservation:
                check.realestate_related_seq = self.env['ir.sequence'].next_by_code('reservation.account.payment')
            elif check.from_contract:
                check.realestate_related_seq = self.env['ir.sequence'].next_by_code('contract.account.payment')
        return res

    @api.depends(
        'sale_proposal_id.unit_id',
        'sale_reservation_id.unit_id',
        'allocation_ids.installment_id.unit_id',
        'allocation_ids.maintenance_id.unit_id'
    )
    def _compute_unit_id(self):
        for rec in self:
            if rec.sale_proposal_id and rec.sale_proposal_id.unit_id:
                rec.unit_id = rec.sale_proposal_id.unit_id
            elif rec.sale_reservation_id and rec.sale_reservation_id.unit_id:
                rec.unit_id = rec.sale_reservation_id.unit_id
            elif rec.allocation_ids:
                alloc_units = (
                        rec.allocation_ids.mapped('installment_id.unit_id') |
                        rec.allocation_ids.mapped('maintenance_id.unit_id')
                ).filtered(lambda u: u)
                rec.unit_id = alloc_units[0] if alloc_units else rec.unit_id
            else:
                rec.unit_id = rec.unit_id

    @api.onchange('eoi_id')
    def _onchange_eoi_id(self):
        """Selecting EOI populates linked Reservation, Proposal, and Unit if they exist"""
        if self.eoi_id:
            if self.eoi_id.customer_id:
                self.payer = self.eoi_id.customer_id

            reservation = self.env['real.estate.sale.reservation'].search([
                ('eoi_id', '=', self.eoi_id.id),
                ('state', 'not in', ['cancelled', 'expired'])
            ], limit=1)
            proposal = self.env['sale.proposal'].search([
                ('eoi_id', '=', self.eoi_id.id),
                ('state', '!=', 'cancelled')
            ], limit=1)

            if proposal:
                self.sale_proposal_id = proposal
                self.sale_reservation_id = proposal.sale_contract_reservation_id or reservation
                if proposal.unit_id:
                    self.unit_id = proposal.unit_id
            elif reservation:
                self.sale_reservation_id = reservation
                if reservation.unit_id:
                    self.unit_id = reservation.unit_id

    @api.onchange('unit_id')
    def _onchange_unit_id(self):
        """Selecting Unit populates Contract, Reservation, and EOI if they exist"""
        if self.unit_id:
            proposal = self.env['sale.proposal'].search([
                ('unit_id', '=', self.unit_id.id),
                ('state', '!=', 'cancelled')
            ], limit=1, order='create_date desc')

            reservation = self.env['real.estate.sale.reservation'].search([
                ('unit_id', '=', self.unit_id.id),
                ('state', 'not in', ['cancelled', 'expired'])
            ], limit=1, order='create_date desc')

            if proposal:
                self.sale_proposal_id = proposal
                self.sale_reservation_id = proposal.sale_contract_reservation_id or reservation
                self.eoi_id = proposal.eoi_id or (
                    self.sale_reservation_id.eoi_id if self.sale_reservation_id else False)
                if proposal.customer_id:
                    self.payer = proposal.customer_id
            elif reservation:
                self.sale_reservation_id = reservation
                if reservation.eoi_id:
                    self.eoi_id = reservation.eoi_id
                if reservation.customer_id:
                    self.payer = reservation.customer_id

    @api.onchange('sale_reservation_id')
    def _onchange_sale_reservation_id(self):
        """Selecting Reservation populates Unit, EOI, and Contract if they exist"""
        if self.sale_reservation_id:
            res = self.sale_reservation_id
            if res.customer_id:
                self.payer = res.customer_id
            if res.unit_id:
                self.unit_id = res.unit_id
            if res.eoi_id:
                self.eoi_id = res.eoi_id

            proposal = self.env['sale.proposal'].search([
                ('sale_contract_reservation_id', '=', res.id),
                ('state', '!=', 'cancelled')
            ], limit=1)
            if proposal:
                self.sale_proposal_id = proposal

    @api.onchange('sale_proposal_id')
    def _onchange_sale_proposal_id(self):
        """Selecting Proposal populates Unit, Reservation, and EOI if they exist"""
        if self.sale_proposal_id:
            prop = self.sale_proposal_id
            if prop.customer_id:
                self.payer = prop.customer_id
            if prop.unit_id:
                self.unit_id = prop.unit_id
            if prop.sale_contract_reservation_id:
                self.sale_reservation_id = prop.sale_contract_reservation_id
            self.eoi_id = prop.eoi_id or (
                prop.sale_contract_reservation_id.eoi_id
                if prop.sale_contract_reservation_id else False
            )