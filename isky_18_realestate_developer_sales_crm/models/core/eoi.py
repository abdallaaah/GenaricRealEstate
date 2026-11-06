from odoo import models, fields, api, _, Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import float_compare

# Single source for the manual-Paid group xmlid. Safe one-way import: installment_lines does
# not import this module.
from .installment_lines import MANUAL_PAID_GROUP

from odoo.addons.isky_18_realestate_developer_unit_inventory.models.selections import unit_type_selection, residential_type_selection, referred_by_selection, public_area_selection, \
    retail_type_selection, entertainment_type_selection, industrial_type_selection, finishing_type_selection, \
    payment_methods_selection, split_with_selection

unit_type_selection = unit_type_selection.copy()
referred_by_selection = referred_by_selection.copy()

unit_type_selection.remove(('gate', 'Gate'))
referred_by_selection.remove(('management', 'Management'))

class Eoi(models.Model):
    """EOi model is related to Sales"""
    _name = "eoi.eoi"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'realestate.sales.commission.hooks', 'realestate.approval.gate']

    name = fields.Char('EOI Reference', copy=False, readonly=True, index=True,
                       default='New')
    customer_id = fields.Many2one('res.partner')
    referred_by = fields.Selection(selection=referred_by_selection, string='Referred By')
    referred_by_employee_id = fields.Many2one('hr.employee')
    referred_by_partner_id = fields.Many2one('res.partner')
    other = fields.Char()
    brand_name = fields.Char(string='Arabic Name',compute='_compute_customer_info', store=True, inverse='_inverse_customer_info',copy=False)
    address = fields.Char(related='customer_id.contact_address')
    jop_position = fields.Char(related='customer_id.function')
    academic_qualifications = fields.Char(related="customer_id.academic_qualifications")
    reservation_amount = fields.Float('EOI Amount')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    unit_type = fields.Selection(selection= unit_type_selection, string='Unit Type', default='residential')
    public_area = fields.Selection(selection=public_area_selection, string='Public Area')
    retail_type = fields.Selection(selection=retail_type_selection, string='Retail Type')
    office_type_id = fields.Many2one('office.type', string='Office Type')
    residential_type = fields.Selection(selection=residential_type_selection, string='Residential Type')
    apartment_type_id = fields.Many2one('residential.sub.type', string='Apartment Type',
                                        domain=[('type', '=', 'apartment')])
    villa_type_id = fields.Many2one('residential.sub.type', string='Villa Type',
                                    domain=[('type', '=', 'villa')])
    loft_type_id = fields.Many2one('residential.sub.type', string='Loft Type',
                                   domain=[('type', '=', 'loft')])
    entertainment_type = fields.Selection(selection=entertainment_type_selection, string='Entertainment Type')
    industrial_type = fields.Selection(selection=industrial_type_selection, string='Industrial Type')
    active = fields.Boolean(default=True)
    status = fields.Selection([
        ('new', 'New'),
        ('submitted', 'Submitted'),
        ('paid', 'Paid'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('to_refunded', 'To Be Refunded'),
        ('refunded', 'Refunded')], string='Status', default='new', copy=False)
    internal_notes = fields.Char()
    # Supplement S2 (manual payment tracking, used in Mode B). 'deafult' was a typo, so this
    # field never actually had a default; fixed in Phase 3 step 2b. paid_date/paid_by_id satisfy
    # S2's "Setting Paid stores date and user" without creating any journal entry.
    is_paid = fields.Boolean(string='Paid', default=False, copy=False, tracking=True)
    paid_date = fields.Datetime(string='Paid On', readonly=True, copy=False)
    paid_by_id = fields.Many2one('res.users', string='Paid By', readonly=True, copy=False)
    in_sent_payment = fields.Boolean(default=False, copy=False)
    in_refund_payment = fields.Boolean(default=False)
    finishing_type = fields.Selection(selection=finishing_type_selection, string='Finishing Type')
    payment_methods = fields.Selection(selection=payment_methods_selection, default='cheque', string='Payment Method')
    payment_status = fields.Selection([
        ('partial', 'Partial'),
        ('complete', 'Complete'),
    ], string='Payment Status', default='complete')
    company_id = fields.Many2one('res.company', default=lambda self: self._default_company_id())

    # fields for partial payment lines
    eoi_payment_ids = fields.One2many('eoi.payment', 'eoi_id', string='EOI Payments')

    # fields for payment
    account_payment_ids = fields.One2many('account.payment', 'eoi_id', string='Payment')
    payment_count = fields.Integer(compute='_compute_payment_count', string='Payment Count')

    # cheque_manage_ids / cheque_count moved to
    # isky_18_realestate_developer_sales_cheques (Phase 3 step 3), supplement S1.

    # fields for reservations
    reservation_ids = fields.One2many('real.estate.sale.reservation', 'eoi_id', string='Reservations')
    reservation_count = fields.Integer(compute='_compute_reservation_count', string='Reservation Count')

    user_id = fields.Many2one(
        'res.users',
        string='Salesperson',
        default=lambda self: self.env.user,
        tracking=True,
        # domain on job_level_id.is_* removed: job.level lives in L3 (commission), and a
        # Many2many domain referencing it registers an implicit dependency that crashes
        # field-setup while this L2 module is loading, before L3 exists yet.
    )

    split_deal = fields.Boolean(string='Split Deal')

    split_with = fields.Selection(selection=split_with_selection, string='Split With')

    # Many2many fields for split with
    partner_ids = fields.Many2many(
        'res.partner',
        'eoi_partner_id_rel_contact',
        'eoi_id',
        'contact_id',
        string='Customers'
    )

    employee_ids = fields.Many2many(
        'hr.employee',
        'eoi_employee_id_rel',
        'eoi_id',
        'referral_id',
        string="Referral"
    )

    broker_ids = fields.Many2many(
        'res.partner',
        'eoi_partner_id_rel_broker_id',
        'eoi_id',
        'broker_id',
        string="Outside Broker",
        domain="[('is_broker','=',True)]"
    )

    ambassador_ids = fields.Many2many(
        'res.partner',
        'eoi_partner_id_rel_ambassador_id',
        'eoi_id',
        'ambassador_id',
        string="Ambassador",
        domain="[('is_ambassador','=',True)]"
    )

    non_sales_ids = fields.Many2many(
        'res.users',
        'eoi_res_user_id_rel_non_sales_id',
        'eoi_id',
        'non_sales_id',
        string='Non Sales'
    )

    sales_ids = fields.Many2many(
        'res.users',
        'eoi_res_user_id_rel_sales_id',
        'eoi_id',
        'sales_id',
        string='Sales',
        # domain on job_level_id.is_* removed: job.level lives in L3 (commission), and a
        # Many2many domain referencing it registers an implicit dependency that crashes
        # field-setup while this L2 module is loading, before L3 exists yet.
    )

    # commission_ids field (One2many to realestate.commission, L3) moved to
    # isky_18_realestate_developer_commission/models/core/eoi_commission_hierarchy_ext.py -
    # that model is L3's own, and L2 must not depend on L3.
    project_id = fields.Many2one('realestate.project')

    phase_one_id = fields.Many2one(
        'real.estate.project.phase',
        compute='_compute_phases',
        store=True,
    )
    phase_two_id = fields.Many2one(
        'real.estate.project.phase',
        compute='_compute_phases',
        store=True,
    )
    phase_three_id = fields.Many2one(
        'real.estate.project.phase',
        compute='_compute_phases',
        store=True,
    )
    phase_four_id = fields.Many2one(
        'real.estate.project.phase',
        compute='_compute_phases',
        store=True,
    )
    phase_domain_ids = fields.Many2many(
        'real.estate.project.phase',
        compute='_compute_phases',
        store=True,
    )
    phase_id = fields.Many2one(
        'real.estate.project.phase',
    )

    customer_code = fields.Char(string='Customer Code', compute='_compute_customer_info',inverse='_inverse_customer_info', store=True, copy=False)
    mobile = fields.Char(string='Customer Mobile Number', compute='_compute_customer_info',inverse='_inverse_customer_info', store=True, copy=False)
    email = fields.Char(string='Customer Email Address', compute='_compute_customer_info',inverse='_inverse_customer_info', store=True, copy=False)
    address_1 = fields.Text(string='Customer Address 1', compute='_compute_customer_info',inverse='_inverse_customer_info', store=True, copy=False)
    address_2 = fields.Text(string='Customer Address 2', compute='_compute_customer_info',inverse='_inverse_customer_info', store=True, copy=False)
    national_id = fields.Char(string='Customer National ID Number', compute='_compute_customer_info',inverse='_inverse_customer_info', store=True, copy=False)
    street_1 = fields.Char(string='Customer Street 1', compute='_compute_customer_info',inverse='_inverse_customer_info', store=True, copy=False)

    has_contract = fields.Boolean(string='Has Contract', compute='_compute_has_contract')
    is_broker_partner = fields.Boolean(compute='_compute_is_broker_partner')

    @api.depends('referred_by_partner_id')
    def _compute_has_contract(self):
        self.has_contract = False

        broker_ids = self.filtered('referred_by_partner_id').mapped('referred_by_partner_id.id')

        if broker_ids:
            contracts = self.env['broker.contract'].search([
                ('broker_company', 'in', broker_ids)
            ])

            brokers_with_contracts = set(contracts.mapped('broker_company.id'))

            for eoi in self:
                if eoi.referred_by_partner_id.id in brokers_with_contracts:
                    eoi.has_contract = True


    @api.depends('referred_by_partner_id')
    def _compute_is_broker_partner(self):
        for eoi in self:
            eoi.is_broker_partner = False
            if eoi.referred_by_partner_id and eoi.referred_by_partner_id.is_broker:
                eoi.is_broker_partner = True


    @api.depends('customer_id', 'customer_id.customer_code', 'customer_id.mobile', 'customer_id.email',
                 'customer_id.address_1', 'customer_id.address_2', 'customer_id.national_id','customer_id.street',
                 'customer_id.ref')
    def _compute_customer_info(self):
        for rec in self:
            if self.env.context.get('skip_customer_info_sync_from_eoi'):
                continue
            if rec.customer_id:
                rec.customer_code = rec.customer_id.customer_code
                rec.mobile = rec.customer_id.mobile
                rec.email = rec.customer_id.email
                rec.address_1 = rec.customer_id.address_1
                rec.address_2 = rec.customer_id.address_2
                rec.national_id = rec.customer_id.national_id
                rec.street_1 = rec.customer_id.street
                rec.brand_name = rec.customer_id.ref
            else:
                rec.customer_code = False
                rec.mobile = False
                rec.email = False
                rec.address_1 = False
                rec.address_2 = False
                rec.national_id = False
                rec.street_1 = False
                rec.brand_name = False

    def _inverse_customer_info(self):
        for rec in self:
            if rec.customer_id:
                rec.customer_id.with_context(skip_customer_info_sync_from_eoi=True).write({
                    'customer_code': rec.customer_code,
                    'mobile': rec.mobile,
                    'email': rec.email,
                    'address_1': rec.address_1,
                    'address_2': rec.address_2,
                    'national_id': rec.national_id,
                    'street': rec.street_1,
                    'ref': rec.brand_name,
                })

    def _default_company_id(self):
        developer_company = self.env.ref('base.main_company')
        return developer_company.id if developer_company else False

    @api.depends('project_id', 'project_id.project_phases_ids', 'project_id.project_phases_ids.is_phase_one','project_id.project_phases_ids.is_phase_two',
                 'project_id.project_phases_ids.is_phase_three', 'project_id.project_phases_ids.is_phase_four')
    def _compute_phases(self):
        for rec in self:
            if rec.project_id:
                phases = rec.project_id.project_phases_ids.filtered(lambda p: p.is_phase_one or p.is_phase_two or p.is_phase_three or p.is_phase_four)
                phase_one = phases.filtered(lambda p: p.is_phase_one)
                phase_two = phases.filtered(lambda p: p.is_phase_two)
                phase_three = phases.filtered(lambda p: p.is_phase_three)
                phase_four = phases.filtered(lambda p: p.is_phase_four)

                rec.phase_one_id = phase_one[0] if phase_one else False
                rec.phase_two_id = phase_two[0] if phase_two else False
                rec.phase_three_id = phase_three[0] if phase_three else False
                rec.phase_four_id = phase_four[0] if phase_four else False
                rec.phase_domain_ids = phases if phases else False
            else:
                rec.phase_one_id = False
                rec.phase_two_id = False
                rec.phase_three_id = False
                rec.phase_four_id = False
                rec.phase_domain_ids = False

    # compute_person_hierarchy: this copy was always shadowed by
    # eoi_commission_hierarchy_ext.py's (imported after this file - Odoo's MRO means the
    # later-imported one wins), so it never ran. Removed along with the field it targeted;
    # see eoi_commission_hierarchy_ext.py for the one that was actually active, now moved to
    # isky_18_realestate_developer_commission.

    @api.onchange('sales_ids')
    def _onchange_sales_ids(self):
        """Trigger recomputation when sales_ids changes in the UI"""
        self._build_commission_hierarchy()

    def write(self, vals):
        """Override write to recompute commission when sales_ids changes"""
        res = super(Eoi, self).write(vals)
        # Force recompute if sales_ids changed
        if 'sales_ids' in vals:
            self._build_commission_hierarchy()
        return res

    def update_split_deal(self, **vals):
        """
        Update split deal information for EOI
        """
        self.browse().check_access('write')
        for eoi in self:
            split_deal_vals = {
                'split_deal': vals.get('split_deal'),
                'split_with': vals.get('split_with') if vals.get('split_with') else None,
                'partner_ids': [(6, 0, vals.get('partner_ids'))] if vals.get('partner_ids') else None,
                'employee_ids': [(6, 0, vals.get('employee_ids'))] if vals.get('employee_ids') else None,
                'broker_ids': [(6, 0, vals.get('broker_ids'))] if vals.get('broker_ids') else None,
                'ambassador_ids': [(6, 0, vals.get('ambassador_ids'))] if vals.get('ambassador_ids') else None,
                'non_sales_ids': [(6, 0, vals.get('non_sales_ids'))] if vals.get('non_sales_ids') else None,
                'sales_ids': [(6, 0, vals.get('sales_ids'))] if vals.get('sales_ids') else None,
                'other': vals.get('other') if vals.get('other') else None,
            }
            split_deal_vals = {k: v for k, v in split_deal_vals.items() if v not in ('', None, [])}
            eoi.write(split_deal_vals)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('eoi.eoi') or _('New')
        return super().create(vals)

    def unlink(self):
        for rec in self:
            if rec.status == 'paid' or rec.status == 'accepted':
                raise ValidationError("You cannot delete paid EOI")
        return super().unlink()

    def action_submit(self):
        self.status = 'submitted'

    def action_mark_paid(self):
        """Supplement S2 manual payment tracking, the Mode B counterpart of registering a
        payment: record the EOI as paid, storing date and user, WITHOUT creating any
        account.payment or account.move. Works identically in Mode A and Mode B - it never
        touches the accounting layer.

        Gated on the same group as ticking an installment Paid by hand: both acknowledge money
        that has no payment or cheque record behind it.
        """
        self._check_manual_paid_group()
        for rec in self:
            if rec.is_paid:
                continue
            rec.write({
                'is_paid': True,
                'paid_date': fields.Datetime.now(),
                'paid_by_id': self.env.uid,
            })
            rec._message_log(body=_(
                "%(user)s marked this EOI as paid by hand. No journal entry was created.",
                user=self.env.user.name,
            ))

    def action_unmark_paid(self):
        """Undo action_mark_paid. Same group gate."""
        self._check_manual_paid_group()
        for rec in self:
            if not rec.is_paid:
                continue
            rec.write({'is_paid': False, 'paid_date': False, 'paid_by_id': False})
            rec._message_log(body=_(
                "%(user)s cleared the manual Paid mark on this EOI.",
                user=self.env.user.name,
            ))

    def _check_manual_paid_group(self):
        """Same group as installment.lines' manual Paid tick - see
        isky_18_realestate_developer_sales_crm/security/security.xml."""
        # S7: the group comes from the company configuration, not a hardcoded xmlid.
        if not self.env.su and not self._user_can_approve('manual_paid'):
            raise AccessError(self.env._(
                "Only users of the group 'Can Tick Installments as Paid' can mark an EOI as "
                "paid by hand."
            ))

    def _compute_reservation_count(self):
        for record in self:
            record.reservation_count = len(record.reservation_ids)

    def action_create_reservation(self):
        """Create a sale reservation from the accepted EOI"""
        self.ensure_one()

        commission_lines = []
        if self.commission_ids:
            for commission in self.commission_ids:
                commission_lines.append(Command.create({
                    'employee_id': commission.employee_id.id,
                    'jop_position': commission.jop_position,
                    'commission': commission.commission,
                }))

        # Prepare reservation values
        reservation_vals = {
            'from_eoi': True,
            'customer_id': self.customer_id.id,
            'customer_national_id': self.customer_id.national_id,
            'customer_code': self.customer_id.customer_code,
            'brand_name': self.customer_id.ref,
            'mobile': self.customer_id.mobile,
            'customer_email': self.customer_id.email,
            'customer_street': self.customer_id.street,
            'customer_street2': self.customer_id.street2,
            'customer_city': self.customer_id.city,
            'customer_state_id': self.customer_id.state_id.id if self.customer_id.state_id else False,
            'customer_country_id': self.customer_id.country_id.id if self.customer_id.country_id else False,
            'eoi_amount': self.reservation_amount,
            'currency_id': self.currency_id.id,
            'eoi_id': self.id,
            'unit_sales_price': 0.0,
            'payment_method': 'bank_transfer' if self.payment_methods == 'bank' else
            'bank_cheque' if self.payment_methods == 'cheque' else 'cash',
            'user_id': self.user_id.id if self.user_id else False,
            'split_deal': self.split_deal,
            'referred_by': self.referred_by if self.referred_by else False,
            'referred_by_partner_id' : self.referred_by_partner_id.id if self.referred_by_partner_id else False,
            'commission_ids': commission_lines,
        }

        # Pass opportunity_id if available
        if hasattr(self, 'opportunity_id') and self.opportunity_id:
            reservation_vals['opportunity_id'] = self.opportunity_id.id

        # Pass split_with selection
        if self.split_with:
            reservation_vals['split_with'] = self.split_with

        # Pass split with many2many fields
        if self.split_deal:
            if self.partner_ids:
                reservation_vals['partner_ids'] = [(6, 0, self.partner_ids.ids)]
            if self.employee_ids:
                reservation_vals['employee_ids'] = [(6, 0, self.employee_ids.ids)]
            if self.broker_ids:
                reservation_vals['broker_ids'] = [(6, 0, self.broker_ids.ids)]
            if self.ambassador_ids:
                reservation_vals['ambassador_ids'] = [(6, 0, self.ambassador_ids.ids)]
            if self.non_sales_ids:
                reservation_vals['non_sales_ids'] = [(6, 0, self.non_sales_ids.ids)]
            if self.sales_ids:
                reservation_vals['sales_ids'] = [(6, 0, self.sales_ids.ids)]
            if self.other:
                reservation_vals['other'] = self.other

        # Create the reservation
        reservation = self.env['real.estate.sale.reservation'].create(reservation_vals)

        #if there is payments or cheques related to this eoi then add the reservation_id as well to the PAID ONES
        if self.account_payment_ids:
            for payment in self.account_payment_ids:
                if payment.state == 'paid':
                    payment.sale_reservation_id = reservation.id

        self._link_cheques_to_reservation(reservation)

        # Open the created reservation form view
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'real.estate.sale.reservation',
            'name': _("Sale Reservation"),
            'view_mode': 'form',
            'res_id': reservation.id,
            'target': 'current',
        }

    def _return_cheques_on_refund(self):
        """Return this EOI's outstanding cheques to the client. Base: no cheque module, so
        nothing to do. sales_cheques overrides it."""
        return

    def _link_cheques_to_reservation(self, reservation):
        """Point this EOI's non-draft cheques at the reservation it just produced.
        Base: nothing to do - no cheque module. sales_cheques overrides it."""
        return

    def action_view_reservations(self):
        """Show all reservations linked to this EOI"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'real.estate.sale.reservation',
            'name': _("Reservations"),
            'target': 'current',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [('eoi_id', '=', self.id)],
            'context': {
                'default_eoi_id': self.id,
                'default_customer_id': self.customer_id.id,
                'default_eoi_amount': self.reservation_amount,
            }
        }

    def _compute_payment_count(self):
        for record in self:
            record.payment_count = len(record.account_payment_ids)

    def create_payment(self):
        self.ensure_one()
        if self.payment_methods in ['cash', 'bank']:
            payment = self.env['account.payment'].create({
                'partner_id': self.customer_id.id,
                'payment_type': 'inbound',
                'amount': self.reservation_amount,
                'eoi_id': self.id,
                'currency_id': self.currency_id.id,
                'memo': self.internal_notes,
                'payment_method_type': self.payment_methods,
                'journal_id': self.env['account.journal'].search([('type', '=', self.payment_methods)], limit=1).id,
                'is_down_payment': True,
                'from_eoi': True,
            })
            return {
                'name': _('Payment'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'account.payment',
                'res_id': payment.id,
                'type': 'ir.actions.act_window',
                'target': 'current',
            }
        return True

    def check_payment(self):
        for rec in self:
            if not self.account_payment_ids:
                raise ValidationError("EOI Payment is Not Complete")
            else:
                if rec.account_payment_ids[0].amount != self.reservation_amount:
                    raise ValidationError("The Payment Of This EOI Not Equal The Reservation Amount")

                # This method is only for cash and bank payments
                if rec.payment_methods == 'cheque':
                    raise ValidationError("Please use 'Check Cheque Payment' button for cheque payments")

                if rec.account_payment_ids[0].payment_type == 'inbound' and \
                        rec.account_payment_ids[0].state == 'paid':
                    rec.status = "paid"
                else:
                    raise ValidationError("EOI Payment is Not Complete")

    def check_partial_payment(self):
        for rec in self:
            if not rec.eoi_payment_ids:
                raise ValidationError(_("No partial payment lines found."))
            if any(not line.is_payed for line in rec.eoi_payment_ids):
                raise ValidationError(_("All partial payment lines must be paid first."))
            total_paid = sum(rec.eoi_payment_ids.mapped('amount'))
            if float_compare(total_paid, rec.reservation_amount, precision_digits=2) < 0:
                raise ValidationError(_(
                    "The total of partial payments (%(paid).2f) is less than the EOI Amount (%(total).2f).",
                    paid=total_paid, total=rec.reservation_amount,
                ))
            rec.status = "paid"

    def action_show_payment(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'name': _("Payment"),
            'target': 'current',
            'views': [(False, 'list'), (False, 'form')],
            'context': {
                'payment_methods': self.payment_methods,
            },
            'domain': [('eoi_id', '=', self.id), ('from_eoi', '=', True)]
        }

    # _compute_cheque_count(), create_cheque_payment(), check_cheque_payment() and
    # action_show_cheques() moved to isky_18_realestate_developer_sales_cheques
    # (Phase 3 step 3).

    def accept_eoi(self):
        self.status = 'accepted'

    def reject_eoi(self):
        self._return_cheques_on_refund()
        self.status = 'rejected'

    # here will need to make a refund payment with same amount
    def refund_eoi_payment(self):
        """Create refund payment if it doesn't exist already"""

        # Check if refund payment already exists
        existing_refund = self.account_payment_ids.filtered(
            lambda p: p.payment_type == 'outbound' and p.is_refund
        )

        if existing_refund:
            # Refund payment already exists, just update status
            self.status = 'to_refunded'
            return

        # Find the original payment to get the is_down_payment flag
        original_payment = self.account_payment_ids.filtered(
            lambda p: p.payment_type == 'inbound' and p.state == 'paid'
        )

        is_down_payment = original_payment[0].is_down_payment if original_payment else False

        # Create refund payment with context to skip validation
        payment = self.env['account.payment'].with_context(skip_eoi_payment_validation=True).create({
            'partner_id': self.customer_id.id,
            'payment_type': 'outbound',
            'amount': self.reservation_amount,
            'eoi_id': self.id,
            'currency_id': self.currency_id.id,
            'memo': self.internal_notes,
            'is_refund': True,
            'is_down_payment': is_down_payment,
        })

        # Set the flag after creation
        self.in_refund_payment = True
        self.status = 'to_refunded'

    def refund(self):
        # Find the refund payment related to this EOI
        refund_payment = self.account_payment_ids.filtered(
            lambda p: p.payment_type == 'outbound' and p.state == 'paid')

        # Check if the refund payment exists and is completed
        if not refund_payment:
            raise ValidationError(_("The refund payment has not been completed."))

        # If the refund payment is complete, set the status to 'refunded'
        self.status = 'refunded'

    def action_open_sale_proposal(self):
        # Create a new sale proposal with eoi_id and customer_id populated
        sale_proposal = self.env['sale.proposal'].create({
            'customer_id': self.customer_id.id,
            'eoi_id': self.id,
            'brand_name': self.brand_name,
            'referred_by': self.referred_by,
            'referred_by_employee_id': self.referred_by_employee_id.id if self.referred_by_employee_id else False,
            'referred_by_partner_id': self.referred_by_partner_id.id if self.referred_by_partner_id else False,
            'other': self.other.id if self.other else False,
        })
        # Open the created sale proposal form view
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.proposal',
            'name': _("Sale Proposal"),
            'view_mode': 'form',
            'res_id': sale_proposal.id,
            'target': 'current',
        }
