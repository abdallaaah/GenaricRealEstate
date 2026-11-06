from odoo import models, fields, api, _
from odoo.tools.safe_eval import datetime
from odoo.exceptions import ValidationError, UserError
import calendar
from datetime import date

import math

from odoo.addons.isky_18_realestate_developer_unit_inventory.models.selections import referred_by_selection, split_with_selection, contract_type_selection, ownership_selection
from dateutil.relativedelta import relativedelta
from collections import defaultdict

referred_by_selection = referred_by_selection.copy()

def add_months(source_date, months):
    """Helper function to add months to a date"""
    month = source_date.month - 1 + months
    year = int(source_date.year + month / 12)
    month = month % 12 + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


class SaleContract(models.Model):
    _name = "real.estate.sale.reservation"
    _inherit = ['mail.thread', 'mail.activity.mixin','installment.mixin', 'realestate.sales.installments.gate', 'realestate.split.parent.mixin', 'realestate.sales.commission.hooks', 'realestate.approval.gate']

    _split_child_fk = 'reservation_id'
    _split_parent_label = 'reservation'

    # C1: declared here, on the model that owns customer_new_ownership_ids, rather than on the
    # abstract parent mixin against a field that mixin does not have. The logic stays in the
    # mixin - this only carries the @api.constrains trigger.
    @api.constrains('customer_new_ownership_ids')
    def _check_ownership_split_total(self):
        return self._validate_split_children()

    name = fields.Char(string='Reservation Reference', required=True, copy=False, readonly=True, index=True,
                       default='New')
    customer_id = fields.Many2one('res.partner', string='Customer')
    customer_phone = fields.Char(related='customer_id.phone', string='Phone', readonly=True)
    customer_email = fields.Char(string='Customer Email Address', compute='_compute_customer_info',inverse='_inverse_customer_info', store=True, copy=False)
    customer_street = fields.Char(compute='_compute_customer_info', inverse='_inverse_customer_info', string='Street', store=True, copy=False)
    customer_street2 = fields.Char(compute='_compute_customer_info', inverse='_inverse_customer_info', string='Street 2', store=True, copy=False)
    customer_city = fields.Char(compute='_compute_customer_info', inverse='_inverse_customer_info', string='City', store=True, copy=False)
    customer_state_id = fields.Many2one('res.country.state', compute='_compute_customer_info', inverse='_inverse_customer_info', string='State', store=True, copy=False, domain="[('country_id', '=?', customer_country_id)]")
    customer_country_id = fields.Many2one('res.country',compute='_compute_customer_info', inverse='_inverse_customer_info', string='Country', store=True, copy=False)
    customer_national_id = fields.Char(string='Customer National ID Number', compute='_compute_customer_info',
                                       inverse='_inverse_customer_info', store=True, copy=False)
    customer_passport_number = fields.Char(related='customer_id.passport_number', string='Passport Number', readonly=True)
    customer_code = fields.Char(string='Customer Code', compute='_compute_customer_info',
                                inverse='_inverse_customer_info', store=True, copy=False)
    mobile = fields.Char(string='Customer Mobile Number', compute='_compute_customer_info',
                         inverse='_inverse_customer_info', store=True, copy=False)

    ownership = fields.Selection(selection=ownership_selection,string="Ownership",default='single')
    customer_ownership_ids = fields.Many2many('customer.ownership', string='Customer Ownership')
    customer_new_ownership_ids = fields.One2many('customer.ownership', 'reservation_id', string='Customer Ownership')

    brand_name = fields.Char(string='Arabic Name', compute='_compute_customer_info', inverse='_inverse_customer_info', store=True, copy=False)
    company_id = fields.Many2one('res.company', default=lambda self: self._default_company_id())
    state = fields.Selection([
        ('draft', 'Draft'),
        ('on_hold', 'On Hold'),
        ('initial_reservation', 'Initial Reservation'),
        ('exception_reservation', 'Exception Reservation'),
        ('reserved', 'Reserved'),
        ('paid', 'Paid'),
        ('contracted', 'Contracted'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ], default='draft', string='State')
    contract_type = fields.Selection(selection=contract_type_selection, default='domestic')
    unit_id = fields.Many2one('real.estate.unit')
    unit_name = fields.Char(related='unit_id.name')
    unit_number = fields.Char(related='unit_id.system_code')
    unit_type = fields.Selection(related='unit_id.unit_type')
    unit_area = fields.Float(related='unit_id.unit_area')
    unit_gross_area = fields.Float(related='unit_id.outdoor_gross_area')
    unit_location = fields.Char(related='unit_id.unit_location')
    delivery_date = fields.Date(related='unit_id.delivery_date', string='Delivery Date', store=True, readonly=True)
    contract_created = fields.Boolean(copy=False)
    unit_sales_price = fields.Float(string='Unit Sales Price', compute='_compute_unit_sales_price', store=True)

    initial_reservation_amount = fields.Float('Initial Reservation Amount',tracking=True)
    complete_reservation_amount = fields.Float('Remaining Reservation Amount', compute='_compute_remaining_reservation_amount', store=True, tracking=True)
    reservation_amount = fields.Float('Reservation Amount',tracking=True, compute='_compute_reservation_amount', store=True, readonly=False)
    reservation_start_date = fields.Date(string='Reservation Date', default=fields.Date.today())
    reservation_end_date = fields.Date()
    reservation_no_of_days = fields.Integer(string='Reservation No. of Days', compute='_compute_reservation_days',
                                            store=True)
    eoi_id = fields.Many2one('eoi.eoi')
    eoi_amount = fields.Float(
        string='EOI Amount',
        compute='_compute_eoi_amount',
        store=True,
    )
    eoi_date = fields.Date(string='Eoi Date', default=fields.Date.today())
    project_id = fields.Many2one('realestate.project')
    unit_project_phase_id = fields.Many2one('real.estate.project.phase', related='unit_id.project_phase', string='Unit Phase', store=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    payment_plan = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi_annually', 'Semi-Annually'),
        ('annually', 'Annually')
    ], string='Payment Plan')
    leasing_length_start_date = fields.Date(string='Leasing Start Date')
    leasing_length_end_date = fields.Date(string='Leasing End Date')
    payment_method = fields.Selection([
        ('bank_transfer', 'Bank Transfer'),
        ('bank_cheque', 'Bank check'),
        ('cash', 'Cash')
    ], string='Payment Method')
    payment_terms_id = fields.Many2one('account.payment.term', string='Payment Terms')

    def _get_formatted_payment_methods(self):
        self.ensure_one()
        method_labels = {
            'bank_transfer': 'تحويل بنكي',
            'bank_cheque': 'شيك بنكي',
            'cash': 'نقدي',
        }
        if self.payment_status == 'complete':
            return method_labels.get(self.payment_method, '')
        else:
            methods = []
            for rp in self.reservation_payment_ids:
                label = method_labels.get(rp.payment_method)
                if label and label not in methods:
                    methods.append(label)
            return " + ".join(methods) if methods else (method_labels.get(self.payment_method, '') if self.payment_method else '')

    # Bank Transfer
    bank_transfer_journal = fields.Many2one('account.journal', string='Bank Journal', domain=[('type', '=', 'bank')])
    transfer_reference = fields.Char()
    transfer_date = fields.Date()

    # Bank Cheque: bank_cheque_journal / cheque_number / cheque_due_date moved to
    # isky_18_realestate_developer_sales_cheques (Phase 3 step 3) - they only feed
    # create_cheque_payment(), which moved with them. The 'bank_cheque' value of
    # payment_method stays here: it is a stored selection value, not a cheque coupling.

    # Cash
    cash_journal = fields.Many2one('account.journal', string='Cash Journal', domain=[('type', '=', 'cash')])
    deposited_amount = fields.Float(string='Deposited Amount', compute='_compute_cash_amounts', store=True, readonly=False)
    remaining_amount = fields.Float(string='Remaining Amount', compute='_compute_cash_amounts', store=True, readonly=False)
    sale_reservation_proposal_id = fields.Many2one('sale.proposal')

    payment_plan_id = fields.Many2one(
        'down.payment.increase',
        string='Down Payment Increase Plan',
        compute='compute_payment_plan_id'
    )

    down_payment_date = fields.Date('Down Payment Date', compute='_compute_default_dates', store=True, readonly=False)
    delivery_payment = fields.Float('Delivery Payment')
    delivery_payment_date = fields.Date('Delivery Payment Date')
    post_contract_price = fields.Float('Down payment 2', compute="_compute_post_contract_price", store=True)
    post_contract_date = fields.Date(string='Down payment 2 Date', compute='_compute_default_dates', store=True, readonly=False)
    expected_delivery_date = fields.Date('Expected Delivery Date')
    expiry_date = fields.Datetime(index=True)
    remaining_time = fields.Char(compute='_compute_remaining_expiration_time')
    is_payment_checked = fields.Boolean(compute='_compute_is_payment_checked', store=True)
    stop_check_expiration = fields.Boolean()

    @api.depends('account_payment_ids', 'account_payment_ids.state')
    def _compute_is_payment_checked(self):
        # S6: the cheque half is added by sales_cheques, which redeclares this compute with
        # the cheque depends and calls super(). The field is latching - it is only ever set
        # to True here - so the override can safely run after this.
        for rec in self:
            matching_payments = False
            if rec.account_payment_ids:
                matching_payments = rec.account_payment_ids.filtered(
                    lambda p: p.payment_type == 'inbound' and p.state in ['to_check', 'in_process',
                                                                          'paid'] and p.from_down_payment == True
                )

            if matching_payments:
                rec.is_payment_checked = True
            else:
                rec.is_payment_checked = rec.is_payment_checked

    @api.onchange('eoi_id')
    def _change_eoi_id(self):
        if self.eoi_id:
            # add resservation_id to the eoi payment or cheques
            for payment in self.eoi_id.account_payment_ids:
                payment.sale_reservation_id = self.id

            self._link_eoi_cheques()

    # ----------------------------------------------------------------------------------
    # Cheque hooks (supplement S1, Phase 3 step 3)
    #
    # sales_crm must install without the optional cheque module, so every cheque-aware
    # branch is reduced to one of these. The base returns the cheque-free answer;
    # isky_18_realestate_developer_sales_cheques overrides each one. Each amount hook has
    # its own cheque-state filter because the original code filtered differently per call
    # site - they are deliberately not collapsed into a single helper.
    # ----------------------------------------------------------------------------------

    def _eoi_cheque_amount(self):
        """Incoming EOI cheques that still count toward the EOI amount."""
        return 0.0

    def _registered_cheque_amount(self):
        """Cheques registered against the down payment, draft included."""
        return 0.0

    def _checked_cheque_amount(self):
        """Cheques that satisfy check_payment(): anything past draft."""
        return 0.0

    def _contract_cheque_amount(self):
        """Cheques collected on this reservation, counted toward the contract down payment."""
        return 0.0

    def _link_eoi_cheques(self):
        """Point the EOI's cheques at this reservation."""
        return

    def _link_cheques_to_contract(self, contract_id):
        """Point this reservation's cheques at the contract it just produced."""
        return

    def _allocate_cheques_to_line(self, line, Allocation):
        """Create payment.allocation rows for this reservation's cheques against line."""
        return

    def _cheque_fund_entries(self):
        """Fund-pool entries for the FIFO waterfall in _reallocate_reservation_funds().
        Same dict shape as the payment entries built there."""
        return []

    def _deal_project(self):
        """A reservation carries project_id directly; fall back to the unit's project."""
        self.ensure_one()
        return self.project_id or self.unit_id.project_id

    def action_stop_checking_expiration(self):
        self.ensure_one()
        if not self.env.user.has_group('isky_18_realestate_developer_sales_crm.stop_checking_reservation_expiration'):
            raise ValidationError(_('You are not allowed to stop checking expiration date'))
        self.stop_check_expiration = True


    def _default_maintenance(self):
        return self.env['maintenance.config'].get_config().maintenance_default

    def _default_maintenance_price_method(self):
        return self.env['maintenance.config'].get_config().maintenance_price_method_default

    def _default_maintenance_percentage(self):
        return self.env['maintenance.config'].get_config().maintenance_percentage_default / 100.0

    def _default_maintenance_price(self):
        config = self.env['maintenance.config'].get_config()
        if config.maintenance_price_method_default == 'fixed_amount':
            return config.maintenance_amount_default
        return 0.0

    def _get_default_maintenance_template(self):
        return self.env['maintenance.template'].search([('default_for_reservation', '=', True)], limit=1)

    maintenance = fields.Boolean('Maintenance', default=_default_maintenance)
    maintenance_template_id = fields.Many2one('maintenance.template', string='Maintenance Template', default=_get_default_maintenance_template)
    maintenance_price_method = fields.Selection([
        ('fixed_amount', 'Fixed Amount'),
        ('percentage', 'Percentage From Unit Price'),
        ('discount', 'Percentage After Discount')
    ], string='Maintenance Price Method', default=_default_maintenance_price_method)
    maintenance_percentage = fields.Float('Maintenance Percentage', default=_default_maintenance_percentage)
    maintenance_price = fields.Float('Maintenance Amount', default=_default_maintenance_price, compute='_compute_maintenance_price', store=True, readonly=False)

    # Payment tracking fields
    account_payment_ids = fields.One2many('account.payment', 'sale_reservation_id', string='Payment')
    account_move_ids = fields.One2many('account.move', 'sale_reservation_id', string='Journal Entries')
    # cheque_manage_ids moved to isky_18_realestate_developer_sales_cheques (Phase 3 step 3).
    penalty_move_id = fields.Many2one('account.move', string='Penalty Journal Entry', readonly=True, copy=False)
    payment_count = fields.Integer(compute='_compute_payment_count', string='Payment Count')
    in_sent_payment = fields.Boolean(default=False, copy=False)
    internal_notes = fields.Text(string='Internal Notes')
    reservation_date = fields.Date('Reservation Date', readonly=True)
    contract_date = fields.Date('Contract Date', readonly=True)

    opportunity_id = fields.Many2one('crm.lead', string='Opportunity')

    user_id = fields.Many2one(
        'res.users',
        string='Salesperson',
        default=lambda self: self.env.user,
        tracking=True,
        # domain on job_level_id.is_* removed: job.level lives in L3 (commission), and a
        # Many2many domain referencing it registers an implicit dependency that crashes
        # field-setup while this L2 module is loading, before L3 exists yet.
    )

    referred_by = fields.Selection(selection=referred_by_selection, string="Referred By")
    referred_by_employee_id = fields.Many2one('hr.employee')
    referred_by_partner_id = fields.Many2one('res.partner')
    other = fields.Char()

    split_deal = fields.Boolean(string='Split Deal')

    split_with = fields.Selection(selection=split_with_selection, string='Split With')

    # Many2many fields for split with
    partner_ids = fields.Many2many(
        'res.partner',
        'reservation_partner_id_rel_contact',
        'reservation_id',
        'contact_id',
        string='Customers'
    )

    employee_ids = fields.Many2many(
        'hr.employee',
        'reservation_employee_id_rel',
        'reservation_id',
        'referral_id',
        string="Referral"
    )

    broker_ids = fields.Many2many(
        'res.partner',
        'reservation_partner_id_rel_broker_id',
        'reservation_id',
        'broker_id',
        string="Outside Broker",
        domain="[('is_broker','=',True)]"
    )

    ambassador_ids = fields.Many2many(
        'res.partner',
        'reservation_partner_id_rel_ambassador_id',
        'reservation_id',
        'ambassador_id',
        string="Ambassador",
        domain="[('is_ambassador','=',True)]"
    )

    non_sales_ids = fields.Many2many(
        'res.users',
        'reservation_res_user_id_rel_non_sales_id',
        'reservation_id',
        'non_sales_id',
        string='Non Sales'
    )

    sales_ids = fields.Many2many(
        'res.users',
        'reservation_res_user_id_rel_sales_id',
        'reservation_id',
        'sales_id',
        string='Sales',
        # domain on job_level_id.is_* removed: job.level lives in L3 (commission), and a
        # Many2many domain referencing it registers an implicit dependency that crashes
        # field-setup while this L2 module is loading, before L3 exists yet.
    )

    # commission_ids field (One2many to realestate.commission, L3) moved to
    # isky_18_realestate_developer_commission/models/core/sale_reservation_crm_ext.py -
    # that model is L3's own, and L2 must not depend on L3.

    sales_consultant_names = fields.Char(
        string='Sales Consultants',
        compute='_compute_sales_team_names',
    )
    sales_manager_names = fields.Char(
        string='Sales Managers',
        compute='_compute_sales_team_names',
    )
    sales_manager_names_ar = fields.Char(
        compute='_compute_sales_team_names',
    )
    sales_operation_names = fields.Char(
        compute='_compute_sales_team_names',
    )
    sales_operation_names_ar = fields.Char(
        compute='_compute_sales_team_names',
    )
    sales_manager_id = fields.Many2one(
        'res.users',
        compute='_compute_sales_manager',
        store=False,
    )

    payment_attachment = fields.Binary(string='Payment Attachment')
    reservation_payment_ids = fields.One2many('reservation.payment', 'sale_reservation_id')
    payment_status = fields.Selection([
    ('partial', 'Partial'),
    ('complete', 'Complete'),
    ],default='complete')

    from_eoi = fields.Boolean(string='From EOI')

    @api.depends(
        'eoi_id',
        'eoi_id.account_payment_ids.state',
        'eoi_id.account_payment_ids.amount',
        'eoi_id.account_payment_ids.payment_type',
    )
    def _compute_eoi_amount(self):
        for rec in self:
            if rec.eoi_id:
                valid_payments = rec.eoi_id.account_payment_ids.filtered(
                    lambda p: p.payment_type == 'inbound' and p.state not in ('canceled', 'rejected') and p.from_eoi == True
                )
                rec.eoi_amount = sum(valid_payments.mapped('amount')) + rec._eoi_cheque_amount()
            else:
                rec.eoi_amount = 0.0

    def _default_company_id(self):
        developer_company = self.env.ref('base.main_company')
        return developer_company.id if developer_company else False

    @api.depends('installment_template_id', 'installment_template_id.contracting_percentage',
                 'installment_template_2_id', 'installment_template_2_id.contracting_percentage',
                 'contracted_selling_price', 'apply_discount_on_post_contract', 'price_after_discount')
    def _compute_post_contract_price(self):
        for rec in self:
            contract_percentage = 0
            if rec.installment_template_id:
                contract_percentage = (rec.installment_template_id.contracting_percentage) / 100
            elif rec.installment_template_2_id:
                contract_percentage = (rec.installment_template_2_id.contracting_percentage) / 100

            amount = rec.price_after_discount if rec.apply_discount_on_post_contract else rec.contracted_selling_price
            rec.post_contract_price = amount * contract_percentage if contract_percentage else 0

    def _compute_sales_manager(self):
        for rec in self:
            member = self.env['crm.team.member'].search(
                [('user_id', '=', rec.user_id.id)],
                limit=1
            )
            rec.sales_manager_id = member.crm_team_id.sales_manager_id

    @api.depends('user_id', 'sales_ids', 'split_deal')
    def _compute_sales_team_names(self):
        all_users = self.mapped('user_id') | self.mapped('sales_ids')
        team_members = self.env['crm.team.member'].search([
            ('user_id', 'in', all_users.ids)
        ])

        user_to_manager = {}
        user_to_operation = {}
        for member in team_members:
            if member.crm_team_id and member.crm_team_id.user_id:
                user_to_manager[member.user_id.id] = member.crm_team_id.user_id
            if member.crm_team_id and member.crm_team_id.operation_id:
                user_to_operation[member.user_id.id] = member.crm_team_id.operation_id

        for rec in self:
            consultant_ids = set()
            consultant_names = []

            if rec.user_id:
                consultant_ids.add(rec.user_id.id)
                consultant_names.append(rec.user_id.name)

            if rec.split_deal:
                for person in rec.sales_ids:
                    if person.id not in consultant_ids:
                        consultant_ids.add(person.id)
                        consultant_names.append(person.name)

            rec.sales_consultant_names = ' / '.join(consultant_names) if consultant_names else ''

            manager_ids = set()
            manager_names = []
            manager_names_ar = []

            operation_ids = set()
            operation_names = []
            operation_names_ar = []

            for user_id in consultant_ids:
                manager = user_to_manager.get(user_id)
                if manager and manager.id not in manager_ids:
                    manager_ids.add(manager.id)
                    manager_names.append(manager.name)
                    manager_names_ar.append(manager.partner_id.ref or manager.name)

                operation = user_to_operation.get(user_id)
                if operation and operation.id not in operation_ids:
                    operation_ids.add(operation.id)
                    operation_names.append(operation.name)
                    operation_names_ar.append(operation.partner_id.ref or operation.name)

            rec.sales_manager_names = ' / '.join(manager_names) if manager_names else ''
            rec.sales_manager_names_ar = ' / '.join(manager_names_ar) if manager_names_ar else ''
            rec.sales_operation_names = ' / '.join(operation_names) if operation_names else ''
            rec.sales_operation_names_ar = ' / '.join(operation_names_ar) if operation_names_ar else ''


    new_total_gross_area = fields.Float(related='unit_id.new_total_gross_area', string='New Total Gross Area(Indoor + Terrace)', store=True)

    # NEW FIELDS FOR INSTALLMENTS
    installment_template_id = fields.Many2one('installment.template', string='Installment Template')
    installment_monthly_amount = fields.Float(related='installment_template_id.monthly_installment_amount')
    installment_quarterly_amount = fields.Float(related='installment_template_id.quarterly_installment_amount')
    installment_semi_annual_amount = fields.Float(related='installment_template_id.semi_annual_installment_amount')
    installment_annually_amount = fields.Float(related='installment_template_id.annual_installment_amount')
    monthly_installment_start_date = fields.Date(string='Monthly Start Date', compute='_compute_first_installment_start_dates', store=True, readonly=False)
    quarterly_installment_start_date = fields.Date(string='Quarterly Start Date', compute='_compute_first_installment_start_dates', store=True, readonly=False)
    semi_annual_installment_start_date = fields.Date(string='Semi Annual Start Date', compute='_compute_first_installment_start_dates', store=True, readonly=False)
    annual_installment_start_date = fields.Date(string='Annual Start Date', compute='_compute_first_installment_start_dates', store=True, readonly=False)

    @api.depends('reservation_start_date', 'unit_id.delivery_date')
    def _compute_default_dates(self):
        for rec in self:
            rec.down_payment_date = rec.reservation_start_date
            rec.post_contract_date = rec.unit_id.delivery_date

    @api.depends('reservation_start_date')
    def _compute_first_installment_start_dates(self):
        for rec in self:
            if rec.reservation_start_date:
                three_months_later = rec.reservation_start_date + relativedelta(months=3)
                rec.monthly_installment_start_date = three_months_later
                rec.quarterly_installment_start_date = three_months_later
                rec.semi_annual_installment_start_date = three_months_later
                rec.annual_installment_start_date = three_months_later
            else:
                rec.monthly_installment_start_date = False
                rec.quarterly_installment_start_date = False
                rec.semi_annual_installment_start_date = False
                rec.annual_installment_start_date = False

    # Second Installment Template
    installment_template_2_id = fields.Many2one('installment.template', string='Second Installment Template')
    installment_2_monthly_amount = fields.Float(related='installment_template_2_id.monthly_installment_amount')
    installment_2_quarterly_amount = fields.Float(related='installment_template_2_id.quarterly_installment_amount')
    installment_2_semi_annual_amount = fields.Float(related='installment_template_2_id.semi_annual_installment_amount')
    installment_2_annually_amount = fields.Float(related='installment_template_2_id.annual_installment_amount')
    monthly_installment_2_start_date = fields.Date(string='Monthly Start Date')
    quarterly_installment_2_start_date = fields.Date(string='Quarterly Start Date')
    semi_annual_installment_2_start_date = fields.Date(string='Semi Annual Start Date')
    annual_installment_2_start_date = fields.Date(string='Annual Start Date')

    # Maintenance Installment Start Dates
    maintenance_monthly_amount = fields.Float(related='maintenance_template_id.monthly_installment_amount')
    maintenance_quarterly_amount = fields.Float(related='maintenance_template_id.quarterly_installment_amount')
    maintenance_semi_annual_amount = fields.Float(related='maintenance_template_id.semi_annual_installment_amount')
    maintenance_annually_amount = fields.Float(related='maintenance_template_id.annual_installment_amount')
    monthly_maintenance_start_date = fields.Date(string='Monthly Maintenance Start Date', compute='_compute_first_maintenance_start_dates', store=True, readonly=False)
    quarterly_maintenance_start_date = fields.Date(string='Quarterly Maintenance Start Date', compute='_compute_first_maintenance_start_dates', store=True, readonly=False)
    semi_annual_maintenance_start_date = fields.Date(string='Semi Annual Maintenance Start Date', compute='_compute_first_maintenance_start_dates', store=True, readonly=False)
    annual_maintenance_start_date = fields.Date(string='Annual Maintenance Start Date', compute='_compute_first_maintenance_start_dates', store=True, readonly=False)

    installment_ids = fields.One2many(
        'installment.lines',
        'reservation_id',
        string='Installments'
    )
    maintenance_installment_ids = fields.One2many(
        'maintenance.installment.lines',
        'reservation_id',
        string='Maintenance Installments'
    )

    year_no = fields.Integer(string="Year number", store=True)
    payment_plan_line_id = fields.Many2one('price.plan.line',compute='_compute_plan_line')
    unit_has_discount = fields.Boolean(related='unit_id.has_discount',store=True)
    down_payment = fields.Float('Down Payment',  store=True, compute='_compute_installment_template_amounts', readonly=False)

    has_floor = fields.Boolean(compute='_compute_has_floor_building')
    has_building = fields.Boolean(compute='_compute_has_floor_building')
    # contracted_price = fields.Float(string="Contracted Price")

    # contracted fields
    contracted_build_up_area = fields.Float()
    contracted_terrace_area = fields.Float(string='Contracted Terrace Area')
    contracted_outdoor_area = fields.Float(string='Contracted Outdoor/Garden Area')
    contracted_total_area = fields.Float(compute='_compute_contracted_total_area')
    contracted_selling_price = fields.Float(compute="_compute_contracted_selling_price",
                                            string="Price Before Discount", readonly=False, store=True)


    has_unit = fields.Boolean(compute='_compute_has_unit')

    has_contract = fields.Boolean(string='Has Contract', compute='_compute_has_contract')
    is_broker_partner = fields.Boolean(compute='_compute_is_broker_partner')

    discount_percentage = fields.Float(string="Discount Percentage", tracking=True)
    price_after_discount = fields.Float(string="Final Price", compute='_compute_price_after_discount',
                                        inverse='_inverse_price_after_discount', store=True, readonly=False, tracking=True)
    discount_approved_by = fields.Many2one('discount.config', tracking=True, copy=False)

    can_edit_discount_percentage = fields.Boolean(compute='_compute_can_edit_discount_percentage')

    apply_discount_on_down_payment = fields.Boolean(default=True)
    apply_discount_on_post_contract = fields.Boolean(string='Apply Discount On Down Payment2', default=True)

    remaining_payment_amount = fields.Float(
        string='Remaining Amount To Pay',
        compute='_compute_remaining_payment_amount',
        store=True
    )

    @api.constrains('customer_id', 'customer_national_id')
    def _check_customer_national_id_or_passport(self):
        for rec in self:
            if (not rec.customer_id.passport_number or not rec.customer_id.passport_number.strip()) and (
                    not rec.customer_national_id or not rec.customer_national_id.strip()):
                raise ValidationError(_("Please provide either a National ID or a Passport Number for customer '%s'.",
                                        rec.customer_id.name))

    @api.depends('down_payment',
                 'account_payment_ids.amount', 'account_payment_ids.state')
    def _compute_remaining_payment_amount(self):
        for rec in self:
            expected_amount = rec.down_payment

            # Sum valid payments (exclude cancelled or rejected)
            valid_payments = rec.account_payment_ids.filtered(
                lambda p: p.payment_type == 'inbound' and p.state not in ('canceled',
                                                                          'rejected')
            )
            payment_amount = sum(valid_payments.mapped('amount'))

            total_registered = payment_amount + rec._registered_cheque_amount()
            remaining_payment_amount = max(0.0, expected_amount - total_registered)
            rec.remaining_payment_amount = rec._apply_rounding_config(remaining_payment_amount)

    def date_to_arabic(self, date_value):
        if not date_value:
            return ""

        arabic_months = {
            1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل",
            5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس",
            9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
        }
        return f"{date_value.day} {arabic_months[date_value.month]} {date_value.year}"

    def round_up_area(self, value):
        if not value:
            return 0.0
        return math.ceil(value)

    @api.depends('reservation_amount', 'complete_reservation_amount', 'payment_method', 'payment_status')
    def _compute_cash_amounts(self):
        for rec in self:
            if not rec.account_payment_ids:
                if rec.payment_method == 'cash' and rec.payment_status == 'complete':
                    rec.deposited_amount = rec.reservation_amount
                    rec.remaining_amount = rec.complete_reservation_amount
                else:
                    rec.deposited_amount = 0
                    rec.remaining_amount = 0
            else:
                rec.deposited_amount = rec.deposited_amount
                rec.remaining_amount = rec.remaining_amount

    def _compute_can_edit_discount_percentage(self):
        # S7: configurable stage.
        can_edit_discount_percentage = self._user_can_approve('edit_discount')
        for rec in self:
            rec.can_edit_discount_percentage = can_edit_discount_percentage

    @api.depends('contracted_selling_price', 'discount_percentage')
    def _compute_price_after_discount(self):
        for rec in self:
            if rec.contracted_selling_price:
                rec.price_after_discount = rec.contracted_selling_price * (1 - rec.discount_percentage / 100.0)
            else:
                rec.price_after_discount = 0.0

    def _inverse_price_after_discount(self):
        for rec in self:
            if rec.contracted_selling_price:
                rec.discount_percentage = (1 - rec.price_after_discount / rec.contracted_selling_price) * 100.0
            else:
                rec.discount_percentage = 0.0

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


    @api.depends('unit_id')
    def _compute_has_unit(self):
        for rec in self:
            if rec.unit_id :
                rec.has_unit = True

    @api.depends('maintenance_template_id', 'unit_id')
    def _compute_first_maintenance_start_dates(self):
        for rec in self:
            if rec.maintenance_template_id and rec.maintenance_template_id.default_for_reservation and rec.unit_id.delivery_date:
                start_date = rec.unit_id.delivery_date
                rec.monthly_maintenance_start_date = start_date
                rec.quarterly_maintenance_start_date = start_date
                rec.semi_annual_maintenance_start_date = start_date
                rec.annual_maintenance_start_date = start_date

    @api.depends('unit_id', 'contracted_build_up_area', 'contracted_terrace_area', 'contracted_outdoor_area')
    def _compute_contracted_total_area(self):
        for rec in self:
            rec.contracted_total_area = (
                    rec.contracted_build_up_area +
                    rec.contracted_terrace_area +
                    rec.contracted_outdoor_area
            )
    @api.depends('unit_sales_price')
    def _compute_contracted_selling_price(self):
        for rec in self:
            rec.contracted_selling_price = rec.unit_sales_price

    @api.depends('unit_id', 'unit_id.floor_id', 'unit_id.building_id')
    def _compute_has_floor_building(self):
        for rec in self:
            floor_id = rec.unit_id.floor_id
            building_id = rec.unit_id.building_id
            try:
                rec.has_floor = bool(floor_id and hasattr(floor_id, 'id') and floor_id.id)
                rec.has_building = bool(building_id and hasattr(building_id, 'id') and building_id.id)
            except:
                rec.has_floor = False
                rec.has_building = False

    @api.depends('unit_id.unit_type')
    def compute_payment_plan_id(self):
        for rec in self:
            if rec.unit_id:
                rec.payment_plan_id = self.env['down.payment.increase'].search(
                    [('unit_type', '=', rec.unit_id.unit_type)],
                    limit=1
                )
            else:
                rec.payment_plan_id = False

    @api.depends('unit_id', 'payment_plan_id', 'year_no', 'unit_sales_price', 'unit_has_discount',)
    def _compute_plan_line(self):
        for rec in self:
            rec.payment_plan_line_id = False
            if rec.unit_has_discount:
                continue
            elif rec.payment_plan_id and rec.year_no:
                plan_line = rec.payment_plan_id.price_plan_ids.filtered(
                    lambda l: l.year_no == rec.year_no
                )
                if plan_line:
                    rec.payment_plan_line_id = plan_line[0] if len(plan_line) > 1 else plan_line

    # _build_commission_hierarchy: this copy was always shadowed by
    # sale_reservation_crm_ext.py's (imported after this file - Odoo's MRO means the
    # later-imported one wins), so it never ran. Removed; see sale_reservation_crm_ext.py for
    # the one that was actually active, now moved to isky_18_realestate_developer_commission.

    @api.onchange('unit_id', 'unit_has_discount')
    def change_year_no(self):
        ICP = self.env['ir.config_parameter'].sudo()
        for rec in self:
            if rec.unit_id:
                if rec.unit_has_discount:
                    rec.year_no = rec.unit_id.effective_installment_years
                elif rec.unit_id.unit_type == 'residential':
                    rec.year_no = int(ICP.get_param('arkzayed.residential_default_years', 8) )
                elif rec.unit_id.unit_type in ['retail', 'office', 'medical']:
                    rec.year_no = int(ICP.get_param('arkzayed.non_residential_default_years', 7))

    @api.depends('unit_id', 'unit_id.total_price_unit')
    def _compute_unit_sales_price(self):
        for rec in self:
            rec.unit_sales_price = rec.unit_id.total_price_unit if rec.unit_id else 0.0

    @api.depends('installment_template_id', 'installment_template_id.reservation_percentage',
                 'contracted_selling_price', 'apply_discount_on_down_payment', 'price_after_discount',
                 'installment_template_2_id', 'installment_template_2_id.reservation_percentage')
    def _compute_installment_template_amounts(self):
        for rec in self:
            amount = rec.price_after_discount if rec.apply_discount_on_down_payment else rec.contracted_selling_price
            if rec.installment_template_id:
                if rec.installment_template_id.reservation_percentage:
                    down_payment = (rec.installment_template_id.reservation_percentage / 100) * amount if rec.installment_template_id.reservation_percentage else 0.0
                    rec.down_payment = rec._apply_rounding_config(down_payment)
            elif rec.installment_template_2_id:
                if rec.installment_template_2_id.reservation_percentage:
                    down_payment = (rec.installment_template_2_id.reservation_percentage / 100) * amount if rec.installment_template_2_id.reservation_percentage else 0.0
                    rec.down_payment = rec._apply_rounding_config(down_payment)
            else:
                rec.down_payment = 0

    @api.depends('eoi_amount', 'down_payment', 'payment_status')
    def _compute_reservation_amount(self):
        for rec in self:
            if rec.payment_status == 'complete':
                rec.reservation_amount = rec.down_payment - rec.eoi_amount
            else:
                rec.reservation_amount = 0


    @api.depends('customer_id', 'customer_id.customer_code', 'customer_id.mobile', 'customer_id.email',
                 'customer_id.street', 'customer_id.street2', 'customer_id.city',
                 'customer_id.state_id', 'customer_id.country_id', 'customer_id.national_id', 'customer_id.ref')
    def _compute_customer_info(self):
        for rec in self:
            if self.env.context.get('skip_customer_info_sync_from_reservation'):
                continue
            if rec.customer_id:
                rec.customer_code = rec.customer_id.customer_code
                rec.mobile = rec.customer_id.mobile
                rec.customer_email = rec.customer_id.email
                rec.customer_street = rec.customer_id.street
                rec.customer_street2 = rec.customer_id.street2
                rec.customer_city = rec.customer_id.city
                rec.customer_state_id = rec.customer_id.state_id
                rec.customer_country_id = rec.customer_id.country_id
                rec.customer_national_id = rec.customer_id.national_id
                rec.brand_name = rec.customer_id.ref
            else:
                rec.customer_code = False
                rec.mobile = False
                rec.customer_email = False
                rec.customer_street = False
                rec.customer_street2 = False
                rec.customer_city = False
                rec.customer_state_id = False
                rec.customer_country_id = False
                rec.customer_national_id = False
                rec.brand_name = False

    @api.onchange('payment_status')
    def onchange_payment_status(self):
        for rec in self:
            if rec.payment_status != 'complete':
                rec.payment_method = False

    def _inverse_customer_info(self):
        for rec in self:
            if rec.customer_id:
                vals = {
                    'customer_code': rec.customer_code,
                    'mobile': rec.mobile,
                    'email': rec.customer_email,
                    'street': rec.customer_street,
                    'street2': rec.customer_street2,
                    'city': rec.customer_city,
                    'state_id': rec.customer_state_id.id if rec.customer_state_id else False,
                    'country_id': rec.customer_country_id.id if rec.customer_country_id else False,
                    'ref': rec.brand_name,
                }
                # only push national_id if it actually has a value
                if rec.customer_national_id:
                    vals['national_id'] = rec.customer_national_id
                rec.customer_id.with_context(skip_customer_info_sync_from_reservation=True).write(vals)

    @api.depends('reservation_start_date', 'reservation_end_date')
    def _compute_reservation_days(self):
        for record in self:
            if record.reservation_start_date and record.reservation_end_date:
                record.reservation_no_of_days = (record.reservation_end_date - record.reservation_start_date).days
            else:
                record.reservation_no_of_days = 0

    def _compute_payment_count(self):
        for record in self:
            record.payment_count = len(record.account_payment_ids)

    @api.depends('maintenance_price_method', 'maintenance_percentage', 'contracted_selling_price','price_after_discount')
    def _compute_maintenance_price(self):
        for rec in self:
            if rec.maintenance_price_method == 'percentage' and rec.contracted_selling_price:
                rec.maintenance_price = rec.maintenance_percentage * rec.contracted_selling_price
            elif rec.maintenance_price_method == 'discount' and rec.price_after_discount:
                rec.maintenance_price = rec.maintenance_percentage * rec.price_after_discount
            elif rec.maintenance_price_method == 'fixed_amount':
                rec.maintenance_price = self.env['maintenance.config'].get_config().maintenance_amount_default

    @api.onchange('user_id','sales_ids','split_deal')
    def _onchange_commission_fields(self):
        self._build_commission_hierarchy()

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('sale.reservation') or _('New')
        record = super().create(vals)
        record.reservation_date = fields.Date.today()
        if record.user_id and not record.eoi_id:
            record._build_commission_hierarchy()
        return record

    def write(self, vals):
        result = super().write(vals)
        commission_fields = {'user_id', 'sales_ids', 'split_deal'}
        if commission_fields.intersection(vals.keys()):
            for rec in self:
                rec._build_commission_hierarchy()

        if vals.get('state') == 'reserved':
            for rec in self:
                if rec.unit_id and rec.reservation_date:
                    rec.unit_id.delivery_date = rec.reservation_date + relativedelta(
                        years=rec.unit_id.estimate_delivery_years or 0)

        return result

    def action_view_eoi(self):
        """Return the action to display the related EOI or raise an error if none exists"""
        self.ensure_one()
        if not self.eoi_id:
            raise ValidationError(_("No EOI is linked to this reservation."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('EOI'),
            'res_model': 'eoi.eoi',
            'view_mode': 'form',
            'res_id': self.eoi_id.id,
            'target': 'current',
        }

    # Add this method for "On Hold" button
    def action_hold_unit(self):
        """Block unit with 'On Hold' reason"""
        self.ensure_one()
        if self.unit_id and self.unit_id.unit_status not in ['available', 'available_for_sale']:
            raise ValidationError(_(f'Unit {self.unit_id.system_code} is not available for sale.'))

        expire_hours = self.env['ir.config_parameter'].sudo().get_param('arkzayed_18_realestate_development.onhold_reservation_expiration_hours')

        self.write({
            'state': 'on_hold',
            'expiry_date': fields.Datetime.now() + relativedelta(hours=int(expire_hours))
        })

        # Find the block reason marked for draft reservation (On Hold)
        hold_reason = self.env['block.reason'].search([('for_draft_reservation', '=', True)], limit=1)

        if not hold_reason:
            raise ValidationError(
                _("No block reason is configured for 'On Hold'. Please configure one in Block Reasons."))

        # Block the unit with the hold reason
        self.unit_id.write({
            'unit_status': 'blocked',
            'reason_id': hold_reason.id
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Unit On Hold'),
                'message': _('Unit has been placed on hold.'),
                'type': 'success',
                'sticky': False,
            }
        }

    # Add this method for "Initial Reservation" button
    def action_initial_reservation(self):
        """Block unit with 'Initial Reservation' reason"""
        self.ensure_one()
        expire_hours = self.env['ir.config_parameter'].sudo().get_param('arkzayed_18_realestate_development.onhold_reservation_expiration_hours')

        # Find the block reason marked for initial reservation
        initial_reason = self.env['block.reason'].search([('for_initial_reservation', '=', True)], limit=1)

        if not initial_reason:
            raise ValidationError(
                _("No block reason is configured for 'Initial Reservation'. Please configure one in Block Reasons."))

        # Block the unit with the initial reservation reason
        self.unit_id.write({
            'unit_status': 'blocked',
            'reason_id': initial_reason.id
        })

        # Update reservation state
        self.write({
            'state': 'initial_reservation',
            'expiry_date': fields.Datetime.now() + relativedelta(hours=int(expire_hours))
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Initial Reservation'),
                'message': _('Unit has been marked for initial reservation.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_exception_reservation(self):
        """Set reservation state to 'Exception Reservation'.

        Restricted to users in the Exception Reservation group.
        """
        self.ensure_one()
        if not self.env.user.has_group(
                'isky_18_realestate_developer_sales_crm.group_exception_reservation'):
            raise UserError(_(
                "You are not allowed to perform an Exception Reservation."))
        self.state = 'exception_reservation'

    def action_confirm(self):
        """Confirm the reservation"""
        # check that the user has the required group to confirm the reservation
        # S7: configurable stage.
        self._require_approval('confirm_reservation', _(
            "You are not allowed to confirm a reservation."))
        self._log_approval('confirm_reservation')
        if not self.installment_ids or not self.maintenance_installment_ids:
            raise ValidationError(_('Please create installment and maintenance installment first.'))
        if self.unit_id and self.unit_id.unit_status not in ['available', 'available_for_sale']:
            raise ValidationError(_(f'Unit {self.unit_id.system_code} is not available for sale.'))
        expire_hours = self.env['ir.config_parameter'].sudo().get_param('arkzayed_18_realestate_development.unpaid_reservation_expiration_hours')
        self.write({
            'state': 'reserved',
            'expiry_date': fields.Datetime.now() + relativedelta(hours=int(expire_hours))
        })
        self.unit_id.unit_status = 'reserved'

    def create_payment(self):
        """Create payment for bank transfer or cash AND allocate to Down Payment line"""
        self.ensure_one()
        if not self.installment_ids or not self.maintenance_installment_ids:
            raise ValidationError(_('Please create installment and maintenance installment first.'))
        if not self.payment_attachment:
            raise ValidationError(_("Please upload the Payment Attachment before creating a payment."))
        # Security Block
        if self.remaining_payment_amount <= 0.0:
            raise ValidationError(_("There is no remaining amount to be paid for this reservation."))
        if self.payment_method in ['bank_transfer', 'cash']:
            # Get the appropriate journal based on payment method
            journal = self.bank_transfer_journal if self.payment_method == 'bank_transfer' else self.cash_journal
            journal_type = 'bank' if self.payment_method == 'bank_transfer' else 'cash'
            if not journal:
                journal = self.env['account.journal'].search([('type', '=', journal_type)], limit=1)

                if not journal:
                    raise ValidationError(_("No %s journal found. Please create one first.") % journal_type)

            # Automatically set the amount to the exact remaining balance
            amount = self.remaining_payment_amount
            amount = self._apply_rounding_config(amount)

            memo = f'Reservation Payment - {self.name}'
            if self.payment_method == 'bank_transfer':
                memo = memo + ' - ' + self.transfer_reference if self.transfer_reference else memo

            payment = self.env['account.payment'].create({
                'partner_id': self.customer_id.id,
                'payment_type': 'inbound',
                'amount': amount,
                'sale_reservation_id': self.id,
                'eoi_id': self.eoi_id.id if self.eoi_id else False,
                'unit_id': self.unit_id.id if self.unit_id else False,
                'currency_id': self.currency_id.id,
                'memo': memo,
                'payment_method_type': journal_type,
                'journal_id': journal.id,
                'is_down_payment': True,
                'from_down_payment': True,
                'from_reservation': True,
            })
            if self.payment_method == 'bank_transfer' and self.transfer_date:
                payment.date = self.transfer_date

            # --- ALLOCATE TO DOWN PAYMENT INSTALLMENT LINE ---
            dp_lines = self.installment_ids.filtered(
                lambda l: l.is_down_payment or l.is_down_payment_reservation or (
                            l.name and 'Down Payment' in l.name)
            )
            if dp_lines:
                dp_line = dp_lines[0]
                self.env['payment.allocation'].create({
                    'payment_id': payment.id,
                    'installment_id': dp_line.id,
                    'allocated_amount': payment.amount,
                })
                dp_line.write({'payment_method_used': 'payment'})
            # -------------------------------------------------

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

    # create_cheque_payment() moved to isky_18_realestate_developer_sales_cheques
    # (Phase 3 step 3).

    def check_payment(self):
        """Check if payment is complete for bank transfer or cash"""
        for rec in self:
            if not rec.installment_ids or not rec.maintenance_installment_ids:
                raise ValidationError(_('Please create installment and maintenance installment first.'))
            if rec.state == 'initial_reservation':
                next_state = 'reserved'
            else:
                next_state = 'paid'

            payment_amount = 0
            if rec.account_payment_ids:
                matching_payments = rec.account_payment_ids.filtered(
                    lambda p: p.payment_type == 'inbound' and p.state in ['to_check', 'in_process',
                                                                          'paid']
                )
                payment_amount = sum(matching_payments.mapped('amount')) if matching_payments else 0
            expected_amount = rec.down_payment
            expected_amount = rec._apply_rounding_config(expected_amount)
            total_payments = payment_amount + rec._checked_cheque_amount()

            if total_payments < expected_amount:
                raise ValidationError(
                    f"No valid payment found matching the expected amount of {expected_amount}"
                )

            rec.state = next_state
            if next_state == 'reserved':
                rec.unit_id.unit_status = 'reserved'
                rec.reservation_date = fields.Date.today()

    def action_show_payment(self):
        """Show payments for this reservation"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'name': _("Payment"),
            'target': 'current',
            'views': [(False, 'list'), (False, 'form')],
            'context': {
                'payment_methods': 'bank' if self.payment_method == 'bank_transfer' else 'cash',
            },
            'domain': [('sale_reservation_id', '=', self.id)]
        }

    def action_show_penalty_move(self):
        """Show the penalty journal entry for this reservation"""
        self.ensure_one()
        if not self.penalty_move_id:
            raise ValidationError(_("No penalty journal entry found for this reservation."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'name': _("Penalty Journal Entry"),
            'target': 'current',
            'view_mode': 'form',
            'res_id': self.penalty_move_id.id,
        }

    # action_show_cheques() moved to isky_18_realestate_developer_sales_cheques
    # (Phase 3 step 3).

    def action_create_contract(self):
        """Modified to transfer installment lines to contract"""
        contract_vals = {
            'customer_id': self.customer_id.id,
            'national_id':self.customer_id.national_id,
            'customer_code':self.customer_id.customer_code,
            'mobile': self.customer_id.mobile,
            'email': self.customer_id.email,
            'address_1': self.customer_id.address_1,
            'address_2': self.customer_id.address_2,
            'brand_name': self.brand_name,
            'contract_type': self.contract_type,
            'unit_id': self.unit_id.id,
            'state': 'draft',
            'sale_contract_reservation_id': self.id,
            # UNIT INFO
            'contracted_build_up_area': self.contracted_build_up_area,
            'contracted_terrace_area': self.contracted_terrace_area,
            'contracted_outdoor_area': self.contracted_outdoor_area,
            'contracted_total_area' : self.contracted_total_area,
            'contracted_selling_price' : self.contracted_selling_price,
            # EOI
            'eoi_id': self.eoi_id.id,
            'eoi_amount': self.eoi_amount,
            'eoi_date': self.eoi_date,
            'reservation_payment': sum(self.reservation_payment_ids.mapped('amount')) if self.payment_status == 'partial' else self.reservation_amount,
            'reservation_payment_date': self.reservation_start_date,
            'down_payment_id': self.payment_plan_id.id if self.payment_plan_id else False,
            'down_payment': self.down_payment,
            'apply_discount_on_down_payment': self.apply_discount_on_down_payment,
            'down_payment_date': self.down_payment_date,
            'delivery_payment': self.delivery_payment,
            'delivery_payment_date': self.delivery_payment_date,
            'post_contract_price': self.post_contract_price,
            'apply_discount_on_post_contract': self.apply_discount_on_post_contract,
            'post_contract_date': self.post_contract_date,
            'expected_delivery_date': self.expected_delivery_date,
            'maintenance': self.maintenance,
            'maintenance_template_id': self.maintenance_template_id.id if self.maintenance_template_id else False,
            'maintenance_price_method': self.maintenance_price_method,
            'maintenance_percentage': (self.maintenance_percentage * 100) if self.maintenance_percentage else 0.0,
            'maintenance_price': self.maintenance_price,
            'split_deal': self.split_deal,
            'user_id': self.user_id.id if self.user_id else False,
            'installment_template_id': self.installment_template_id.id if self.installment_template_id else False,
            'monthly_installment_start_date': self.monthly_installment_start_date,
            'quarterly_installment_start_date': self.quarterly_installment_start_date,
            'semi_annual_installment_start_date': self.semi_annual_installment_start_date,
            'annual_installment_start_date': self.annual_installment_start_date,
            'installment_template_2_id': self.installment_template_2_id.id if self.installment_template_2_id else False,
            'monthly_installment_2_start_date': self.monthly_installment_2_start_date,
            'quarterly_installment_2_start_date': self.quarterly_installment_2_start_date,
            'semi_annual_installment_2_start_date': self.semi_annual_installment_2_start_date,
            'annual_installment_2_start_date': self.annual_installment_2_start_date,
            'monthly_maintenance_start_date': self.monthly_maintenance_start_date,
            'quarterly_maintenance_start_date': self.quarterly_maintenance_start_date,
            'semi_annual_maintenance_start_date': self.semi_annual_maintenance_start_date,
            'annual_maintenance_start_date': self.annual_maintenance_start_date,
            'referred_by': self.referred_by if self.referred_by else False,
            'referred_by_partner_id': self.referred_by_partner_id.id if self.referred_by_partner_id else False,
            'discount_percentage': self.discount_percentage,
        }

        # Pass split with fields
        if self.split_deal:
            contract_vals.update({
                'split_with': self.split_with,
                'partner_ids': [(6, 0, self.partner_ids.ids)] if self.partner_ids else False,
                'employee_ids': [(6, 0, self.employee_ids.ids)] if self.employee_ids else False,
                'broker_ids': [(6, 0, self.broker_ids.ids)] if self.broker_ids else False,
                'ambassador_ids': [(6, 0, self.ambassador_ids.ids)] if self.ambassador_ids else False,
                'non_sales_ids': [(6, 0, self.non_sales_ids.ids)] if self.non_sales_ids else False,
                'sales_ids': [(6, 0, self.sales_ids.ids)] if self.sales_ids else False,
                'other': self.other,
            })

        # Create contract
        contract_id = self.env['sale.proposal'].create(contract_vals)

        # Copy commission lines from reservation to contract
        if self.commission_ids:
            for commission in self.commission_ids:
                self.env['realestate.commission'].create({
                    'sale_proposal_id': contract_id.id,
                    'employee_id': commission.employee_id.id,
                    'jop_position': commission.jop_position,
                    'commission': commission.commission,
                })

        # Link existing installment lines directly to the contract to preserve payment links
        if self.installment_ids:
            self.installment_ids.write({
                'sale_proposal_id': contract_id.id,
                'partner_id': contract_id.customer_id.id,
            })

        # Link existing maintenance installment lines directly to the contract
        if self.maintenance_installment_ids:
            self.maintenance_installment_ids.write({
                'sale_proposal_id': contract_id.id,
                'partner_id': contract_id.customer_id.id,
            })

        # if user register cheque or payment then link them too to the sale proposal
        if self.account_payment_ids:
            self.account_payment_ids.write({'sale_proposal_id': contract_id.id})

        self._link_cheques_to_contract(contract_id)

        # Find the Down Payment line and link the payments/cheques specifically to it
        dp_lines = self.installment_ids.filtered(lambda l: l.is_down_payment_reservation)
        if dp_lines:
            dp_line = dp_lines[0]

            # Filter valid payments and cheques (excluding cancelled, rejected, or bounced ones)
            valid_payments = self.account_payment_ids.filtered(
                lambda p: p.state not in ('cancel', 'canceled', 'rejected') and p.payment_type == 'inbound'
            )
            # Calculate total collected for this reservation
            total_payments = sum(valid_payments.mapped('amount'))
            total_collected = round(total_payments + self._contract_cheque_amount(), 2)

            line_total_amount = round(dp_line.total_amount or dp_line.amount, 2)
            net_dp_needed = round(line_total_amount, 2)

            # Safety check: Ensure linked amount doesn't exceed the line's required amount
            if total_collected > net_dp_needed:
                raise ValidationError(_(
                    "Cannot link payments: The total collected amount (%(collected)s) "
                    "exceeds the Down Payment line amount (%(line_amount)s).",
                    collected=total_collected,
                    line_amount=net_dp_needed
                ))

            # Link valid payments to the line using Allocations (safely avoiding duplicates)
            Allocation = self.env['payment.allocation'].with_context(skip_allocation_check=True)
            if valid_payments:
                for pay in valid_payments:
                    if not Allocation.search([('payment_id', '=', pay.id), ('installment_id', '=', dp_line.id)]):
                        Allocation.create({
                            'payment_id': pay.id,
                            'installment_id': dp_line.id,
                            'allocated_amount': pay.amount
                        })
                dp_line.write({'payment_method_used': 'payment'})

            self._allocate_cheques_to_line(dp_line, Allocation)
        if contract_id:
            self.state = "contracted"
            self.unit_id.unit_status = 'reserved'
            self.contract_created = True
            if self.customer_new_ownership_ids:
                self.customer_new_ownership_ids.write({'contract_id': contract_id.id})

        return self.action_show_contract()

    def action_show_contract(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.proposal',
            'name': _("Contracts"),
            'target': 'current',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [('sale_contract_reservation_id', '=', self.id)]
        }

    def action_view_sale_proposal(self):
        """Return the action to display the related sale proposal or raise an error if none exists"""
        self.ensure_one()
        if not self.sale_reservation_proposal_id:
            raise ValidationError(_("No sale Proposal is linked to this reservation."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale Proposal'),
            'res_model': 'sale.proposal',
            'view_mode': 'form',
            'res_id': self.sale_reservation_proposal_id.id,
            'target': 'current',
        }

    def action_check_sale_reservation_schedule_action(self):
        reservations = self.env['real.estate.sale.reservation'].search(
            [('state', '=', 'reserved'), ('contract_created', '=', False),
             ('reservation_end_date', '=', datetime.date.today())])
        for rec in reservations:
            rec.unit_id.unit_status = 'available'
            rec.state = 'cancelled'

    def action_cancel(self):
        self.ensure_one()
        return {
            'name': 'Cancel Reservation',
            'type': 'ir.actions.act_window',
            'res_model': 'reservation.cancellation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_reservation_id': self.id,
            }
        }

    def action_print_unit_plan(self):
        self.ensure_one()
        if not self.unit_id:
            raise ValidationError(_("No unit is linked to this reservation."))
        if not self.unit_id.unit_plan:
            raise ValidationError(_("No unit plan is uploaded for this unit."))

        filename = self.unit_id.unit_plan_filename or 'unit_plan'
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content?model=real.estate.unit&id=%s&field=unit_plan&filename_field=unit_plan_filename&download=true' % self.unit_id.id,
            'target': 'new',
        }

    def action_print_payment_plan(self):
        self.ensure_one()
        if not self.unit_id:
            raise ValidationError(_("You should choose unit first."))

        if not self.installment_template_id and not self.maintenance_template_id:
            raise ValidationError(_("Please select an installment or maintenance template in the reservation first."))

        if not self.installment_ids and not self.maintenance_installment_ids:
            raise ValidationError(_("No installment or maintenance lines found for this reservation."))
        # Safely pass the source to the report via data
        data = {'print_from_model': self._name, 'print_from_id': self.id}
        return self.env.ref('arkzayed_18_realestate_development.unit_payment_plan_report').report_action(self.unit_id,
                                                                                                         data=data)

    @api.depends('down_payment', 'reservation_amount', 'eoi_amount', 'payment_status', 'reservation_payment_ids','reservation_payment_ids.amount')
    def _compute_remaining_reservation_amount(self):
        for rec in self:
            amount = rec.down_payment - rec.eoi_amount
            if len(rec.reservation_payment_ids) > 0 and rec.payment_status == 'partial':
                rec.complete_reservation_amount = amount - sum(rec.reservation_payment_ids.mapped('amount'))
            else:
                rec.complete_reservation_amount = amount - rec.reservation_amount

    def action_change_unit(self):
        self.ensure_one()
        return {
            'name': 'Upgrade / Downgrade Unit',
            'type': 'ir.actions.act_window',
            'res_model': 'reservation.change.unit.wizard',
            'view_mode': 'form',

            'target': 'new',
            'context': {
                'default_reservation_id': self.id,
                'default_old_unit_id': self.unit_id.id,
            }
        }

    def _reallocate_reservation_funds(self, line_type='installment'):
        """
        FIFO Waterfall Re-allocation Engine:
        1. Unlinks old allocations for active payments and cheques.
        2. Spreads remaining active funds sequentially across newly generated lines.
        """
        self.ensure_one()

        # Step 1: Identify Active / Confirmed Funds Pool
        active_payments = self.account_payment_ids.filtered(
            lambda p: p.payment_type == 'inbound' and p.state in (
                'to_check', 'cfo_approved', 'deputy_cfo_approved', 'in_process', 'paid'
            )
        )
        cheque_funds = self._cheque_fund_entries()

        if not active_payments and not cheque_funds:
            return

        # Step 2: Clear old payment.allocation records for active funds & lines of this reservation
        Allocation = self.env['payment.allocation'].with_context(skip_allocation_check=True)
        domain = [('installment_id.reservation_id', '=', self.id)] if line_type == 'installment' else [
            ('maintenance_id.reservation_id', '=', self.id)]

        old_allocations = Allocation.search(domain)
        if old_allocations:
            old_allocations.unlink()

        # Step 3: Build Funds Pool sorted chronologically by date
        fund_pool = []
        for p in active_payments:
            fund_pool.append({
                'type': 'payment',
                'alloc_field': 'payment_id',
                'record': p,
                'date': p.date or fields.Date.today(),
                'remaining_pool': p.amount
            })

        fund_pool.extend(cheque_funds)

        fund_pool.sort(key=lambda x: (x['date'] is False, x['date']))

        # Step 4: Target new lines sorted sequentially
        if line_type == 'installment':
            target_lines = self.installment_ids.sorted(key=lambda l: (l.date is False, l.date, l.serial))
        else:
            target_lines = self.maintenance_installment_ids.sorted(key=lambda l: (l.date is False, l.date, l.serial))

        # Step 5: Waterfall Spreading Algorithm
        for line in target_lines:
            line_amount_needed = line.total_amount if line.total_amount else line.amount

            for fund in fund_pool:
                if fund['remaining_pool'] <= 0.0001:
                    continue
                if line_amount_needed <= 0.0001:
                    break

                alloc_amt = min(fund['remaining_pool'], line_amount_needed)

                alloc_vals = {
                    'allocated_amount': alloc_amt,
                }

                alloc_vals[fund['alloc_field']] = fund['record'].id

                if line_type == 'installment':
                    alloc_vals['installment_id'] = line.id
                else:
                    alloc_vals['maintenance_id'] = line.id

                Allocation.create(alloc_vals)

                fund['remaining_pool'] -= alloc_amt
                line_amount_needed -= alloc_amt

                # Update payment method flag on the line
                line.write({'payment_method_used': fund['type']})

    def _apply_rounding_config(self, amount):
        """Apply apply_cents_in_last_line and apply_to_nearer_ten configuration rules to an amount."""
        if not amount:
            return 0.0

        ICP = self.env['ir.config_parameter'].sudo()
        apply_cents = ICP.get_param('arkzayed_18_realestate_development.apply_cents_in_last_line')
        apply_ten = ICP.get_param('arkzayed_18_realestate_development.apply_to_nearer_ten')

        res_amount = amount

        if apply_cents:
            res_amount = float(math.trunc(res_amount))

        if apply_ten:
            amount_int = math.trunc(res_amount)
            last_digit = amount_int % 10
            if last_digit < 5:
                res_amount -= last_digit
            elif last_digit >= 5:
                res_amount += (10 - last_digit)

        return res_amount

    def action_calculate_installments(self):
        """Calculate installments for reservation with cleanup and automated fund re-allocation"""
        # Step 5: installments toggle. Returns a warning rather than raising - the deal must
        # still complete with no lines.
        if not self._installments_allowed():
            return self._installments_off_notification()

        if not self.price_after_discount or self.price_after_discount <= 0:
            raise ValidationError(_("Unit sales price must be greater than zero."))

        if not self.installment_template_id:
            raise ValidationError(_("Please select an installment template."))

        paid_lines = self.installment_ids.filtered('paid')
        if paid_lines:
            raise UserError(_(
                "Cannot recalculate: %(count)d installment line(s) already have payments allocated. "
                "Paid lines cannot be regenerated. Adjust the remaining unpaid lines manually, or "
                "contact support to restructure this schedule.",
                count=len(paid_lines),
            ))

        self.installment_ids = self._prepare_reservation_installment_lines()

        if self.installment_ids:
            self._force_lines_to_match_total(
                self.installment_ids, self.price_after_discount, label=_('Installment')
            )

            self._reallocate_reservation_funds(line_type='installment')

            sorted_lines = self.installment_ids.sorted(key=lambda l: l.date)
            counter = 1
            for line in sorted_lines:
                line.serial = counter
                counter += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Installments calculated and active funds reallocated successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_calculate_maintenance_installments(self):
        """Calculate maintenance installments for reservation with cleanup and automated fund re-allocation"""
        if not self._installments_allowed():
            return self._installments_off_notification()

        if not self.maintenance:
            raise ValidationError(_("Maintenance is not enabled."))

        if not self.maintenance_price or self.maintenance_price <= 0:
            raise ValidationError(_("Maintenance price must be greater than zero."))

        if not self.maintenance_template_id:
            raise ValidationError(_("Please select a maintenance template."))

        paid_maint_lines = self.maintenance_installment_ids.filtered('paid')
        if paid_maint_lines:
            raise UserError(_(
                "Cannot recalculate: %(count)d maintenance line(s) already have payments allocated. "
                "Paid lines cannot be regenerated. Adjust the remaining unpaid lines manually, or "
                "contact support to restructure this schedule.",
                count=len(paid_maint_lines),
            ))

        self.maintenance_installment_ids = self._prepare_reservation_maintenance_lines()

        if self.maintenance_installment_ids:
            self._force_lines_to_match_total(
                self.maintenance_installment_ids, self.maintenance_price, label=_('Maintenance')
            )

            sorted_maint = self.maintenance_installment_ids.sorted(key=lambda l: l.date)
            maint_counter = 1
            for line in sorted_maint:
                line.serial = maint_counter
                maint_counter += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Maintenance installments calculated and active funds reallocated successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def _prepare_reservation_installment_lines(self):
        """Prepare installment lines for reservation"""
        # Step 5: gate before the clearing assignment below, so a project with installments
        # off neither creates lines nor destroys anything that already exists.
        if not self._installments_allowed():
            return []
        self.installment_ids = None
        installment_lines = []
        ind = 1

        # Calculate total installment amount (same as contract)
        total_installment_amount = self.price_after_discount

        fixed_amount = self.down_payment + self.delivery_payment + self.post_contract_price
        remaining_amount = total_installment_amount - fixed_amount

        if remaining_amount < 0:
            raise UserError(_(
                "Down Payment plus other fixed payments (%.2f) exceed the Price After Discount (%.2f). "
                "Please reduce the Down Payment amount."
            ) % (fixed_amount, total_installment_amount))

        elif remaining_amount > 0:
            template_total_pct = 0.0
            for template in (self.installment_template_id, self.installment_template_2_id):
                if template:
                    template_total_pct += (
                            template.monthly_installment_amount +
                            template.quarterly_installment_amount +
                            template.semi_annual_installment_amount +
                            template.annual_installment_amount
                    )
            scale_factor = 0
            if template_total_pct and total_installment_amount:
                scale_factor = remaining_amount / (template_total_pct * total_installment_amount)

            if self.installment_template_id:
                installment_lines, ind = self._process_reservation_template(
                    self.installment_template_id,
                    total_installment_amount,
                    installment_lines,
                    ind,
                    template_number=1,
                    scale_factor=scale_factor
                )

            # Process Second Installment Template
            if self.installment_template_2_id:
                installment_lines, ind = self._process_reservation_template(
                    self.installment_template_2_id,
                    total_installment_amount,
                    installment_lines,
                    ind,
                    template_number=2,
                    scale_factor=scale_factor
                )

        # Add down payment and delivery payment
        installment_lines = self._get_other_reservation_payment_data(installment_lines, ind)

        return installment_lines

    def _process_reservation_template(self, template, total_installment_amount, installment_lines, ind,
                                      template_number=1, scale_factor=1):
        """Process installment template for reservation (same logic as contract)"""

        # Determine which start dates to use
        if template_number == 1:
            monthly_start = self.monthly_installment_start_date
            quarterly_start = self.quarterly_installment_start_date
            semi_annual_start = self.semi_annual_installment_start_date
            annual_start = self.annual_installment_start_date
            template_label = ""
        else:
            monthly_start = self.monthly_installment_2_start_date
            quarterly_start = self.quarterly_installment_2_start_date
            semi_annual_start = self.semi_annual_installment_2_start_date
            annual_start = self.annual_installment_2_start_date
            template_label = " (Template 2)"

        # Monthly Installments
        if template.monthly_installment_amount > 0:
            if not monthly_start:
                raise UserError(_("Please select monthly installment start date for template %s!") % template_number)

            duration = template.monthly_installment_duration
            pricing = template.monthly_installment_amount * total_installment_amount * scale_factor
            installment_amount = pricing / float(duration or 1)
            date_payment = monthly_start

            for m in range(duration):
                installment_lines.append((0, 0, {
                    "name": _("Monthly Installment") + template_label,
                    "serial": ind,
                    "amount": installment_amount,
                    "date": date_payment,
                }))
                ind += 1
                date_payment = add_months(date_payment, 1)

        # Quarterly Installments
        if template.quarterly_installment_amount > 0:
            if not quarterly_start:
                raise UserError(_("Please select quarterly installment start date for template %s!") % template_number)

            duration = template.quarterly_installment_duration
            pricing = template.quarterly_installment_amount * total_installment_amount * scale_factor
            installment_amount = pricing / float(duration or 1)
            date_payment = quarterly_start

            for m in range(duration):
                installment_lines.append((0, 0, {
                    "name": _("Quarterly Installment") + template_label,
                    "serial": ind,
                    "amount": installment_amount,
                    "date": date_payment,
                }))
                ind += 1
                date_payment = add_months(date_payment, 3)

        # Semi Annual Installments
        if template.semi_annual_installment_amount > 0:
            if not semi_annual_start:
                raise UserError(
                    _("Please select semi-annual installment start date for template %s!") % template_number)

            duration = template.semi_annual_installment_duration
            pricing = template.semi_annual_installment_amount * total_installment_amount * scale_factor
            installment_amount = pricing / float(duration or 1)
            date_payment = semi_annual_start

            for m in range(duration):
                installment_lines.append((0, 0, {
                    "name": _("Semi Annual Installment") + template_label,
                    "serial": ind,
                    "amount": installment_amount,
                    "date": date_payment,
                }))
                ind += 1
                date_payment = add_months(date_payment, 6)

        # Annual Installments
        if template.annual_installment_amount > 0:
            if not annual_start:
                raise UserError(_("Please select annual installment start date for template %s!") % template_number)

            duration = template.annual_installment_duration
            pricing = template.annual_installment_amount * total_installment_amount * scale_factor
            installment_amount = pricing / float(duration or 1)
            date_payment = annual_start

            for m in range(duration):
                installment_lines.append((0, 0, {
                    "name": _("Reservation Annual Installment") + template_label,
                    "serial": ind,
                    "amount": installment_amount,
                    "date": date_payment,
                }))
                ind += 1
                date_payment = add_months(date_payment, 12)

        return installment_lines, ind

    def _get_other_reservation_payment_data(self, installment_lines, ind=1):
        """Add down payment and delivery payment to installment lines"""

        if self.down_payment > 0:
            if not self.down_payment_date:
                raise UserError(_("Please Add Down Payment Date."))
            installment_lines.append((0, 0, {
                "name": _('Down Payment'),
                "serial": ind,
                "amount": self.down_payment,
                "date": self.down_payment_date,
                "is_down_payment": True,
                "is_down_payment_reservation": True,
                "reservation_id": self.id
            }))
            ind += 1

        if self.delivery_payment:
            if not self.delivery_payment_date:
                raise UserError(_("Please Add Delivery Payment Date."))
            installment_lines.append((0, 0, {
                "name": _('Delivery Payment'),
                "serial": ind,
                "amount": self.delivery_payment,
                "date": self.delivery_payment_date,
            }))

        if self.post_contract_price:
            if not self.post_contract_date:
                raise UserError(_("Please Add Down Payment 2 Date."))
            installment_lines.append((0, 0, {
                "name": _('Down Payment 2'),
                "serial": ind,
                "amount": self.post_contract_price,
                "date": self.post_contract_date,
            }))

        return installment_lines

    def _prepare_reservation_maintenance_lines(self):
        if not self._installments_allowed():
            return []
        """Prepare maintenance installment lines for reservation"""
        self.maintenance_installment_ids = None
        maintenance_lines = []
        ind = 1

        if not self.maintenance_template_id:
            return maintenance_lines

        template = self.maintenance_template_id

        # Monthly Maintenance
        if template.monthly_installment_amount > 0:
            if not self.monthly_maintenance_start_date:
                raise UserError(_("Please select monthly maintenance start date!"))

            duration = template.monthly_installment_duration
            pricing = template.monthly_installment_amount * self.maintenance_price
            installment_amount = pricing / float(duration or 1)
            date_payment = self.monthly_maintenance_start_date

            for m in range(duration):
                maintenance_lines.append((0, 0, {
                    "name": _("Maintenance Installment"),
                    "serial": ind,
                    "amount": installment_amount,
                    "date": date_payment,
                    "partner_id": self.customer_id.id,
                }))
                ind += 1
                date_payment = add_months(date_payment, 1)

        # Quarterly Maintenance
        if template.quarterly_installment_amount > 0:
            if not self.quarterly_maintenance_start_date:
                raise UserError(_("Please select quarterly maintenance start date!"))

            duration = template.quarterly_installment_duration
            pricing = template.quarterly_installment_amount * self.maintenance_price
            installment_amount = pricing / float(duration or 1)
            date_payment = self.quarterly_maintenance_start_date

            for m in range(duration):
                maintenance_lines.append((0, 0, {
                    "name": _("Quarterly Maintenance Installment"),
                    "serial": ind,
                    "amount": installment_amount,
                    "date": date_payment,
                    "partner_id": self.customer_id.id,
                }))
                ind += 1
                date_payment = add_months(date_payment, 3)

        # Semi Annual Maintenance
        if template.semi_annual_installment_amount > 0:
            if not self.semi_annual_maintenance_start_date:
                raise UserError(_("Please select semi annual maintenance start date!"))

            duration = template.semi_annual_installment_duration
            pricing = template.semi_annual_installment_amount * self.maintenance_price
            installment_amount = pricing / float(duration or 1)
            date_payment = self.semi_annual_maintenance_start_date

            for m in range(duration):
                maintenance_lines.append((0, 0, {
                    "name": _("Semi Annual Maintenance Installment"),
                    "serial": ind,
                    "amount": installment_amount,
                    "date": date_payment,
                    "partner_id": self.customer_id.id,
                }))
                ind += 1
                date_payment = add_months(date_payment, 6)

        # Annual Maintenance
        if template.annual_installment_amount > 0:
            if not self.annual_maintenance_start_date:
                raise UserError(_("Please select annual maintenance start date!"))

            duration = template.annual_installment_duration
            pricing = template.annual_installment_amount * self.maintenance_price
            installment_amount = pricing / float(duration or 1)
            date_payment = self.annual_maintenance_start_date

            for m in range(duration):
                maintenance_lines.append((0, 0, {
                    "name": _("Annual Maintenance Installment"),
                    "serial": ind,
                    "amount": installment_amount,
                    "date": date_payment,
                    "partner_id": self.customer_id.id,
                }))
                ind += 1
                date_payment = add_months(date_payment, 12)

        return maintenance_lines

    def action_print_unit_plan_report(self):
        self.ensure_one()
        if not self.unit_id:
            raise ValidationError(_("You should choose unit first."))
        if not self.unit_id.unit_plan:
            raise ValidationError(_("Unit plan for this unit is not found."))
        if self.unit_id.unit_type in ["office", "retail", "medical", "residential"]:
            return self.env.ref('arkzayed_18_realestate_development.action_print_plan_in_reservation').report_action(self,)

    def action_print_initial_reservation_form(self):
        self.ensure_one()
        return self.env.ref('arkzayed_18_realestate_development.initial_reservation_report').report_action(self)

    def amount_to_arabic(self, amount):
        if not amount:
            return "صفر"

        amount = int(round(amount))
        if amount == 0:
            return "صفر"

        ones = ["", "واحد", "اثنان", "ثلاثة", "أربعة", "خمسة", "ستة", "سبعة", "ثمانية", "تسعة"]
        tens = ["", "عشرة", "عشرون", "ثلاثون", "أربعون", "خمسون", "ستون", "سبعون", "ثمانون", "تسعون"]
        teens = ["عشرة", "أحد عشر", "اثنا عشر", "ثلاثة عشر", "أربعة عشر", "خمسة عشر",
                 "ستة عشر", "سبعة عشر", "ثمانية عشر", "تسعة عشر"]
        hundreds = ["", "مائة", "مئتان", "ثلاثمائة", "أربعمائة", "خمسمائة",
                    "ستمائة", "سبعمائة", "ثمانمائة", "تسعمائة"]

        def two_digits(n):
            if n == 0:
                return ""
            if 10 <= n <= 19:
                return teens[n - 10]
            o = n % 10
            t = n // 10
            if o and t:
                return f"{ones[o]} و {tens[t]}"
            return ones[o] or tens[t]

        def three_digits(n):
            if n == 0:
                return ""
            h = n // 100
            r = n % 100
            parts = []
            if h:
                parts.append(hundreds[h])
            td = two_digits(r)
            if td:
                parts.append(td)
            return " و ".join(parts)

        parts = []

        billions = amount // 1_000_000_000
        amount %= 1_000_000_000
        millions = amount // 1_000_000
        amount %= 1_000_000
        thousands = amount // 1000
        remainder = amount % 1000

        if billions:
            parts.append(f"{three_digits(billions)} مليار")

        if millions:
            if millions == 1:
                parts.append("مليون")
            elif millions == 2:
                parts.append("مليونان")
            elif 3 <= millions <= 10:
                parts.append(f"{three_digits(millions)} ملايين")
            else:
                parts.append(f"{three_digits(millions)} مليون")

        if thousands:
            if thousands == 1:
                parts.append("ألف")
            elif thousands == 2:
                parts.append("ألفان")
            elif 3 <= thousands <= 10:
                parts.append(f"{three_digits(thousands)} آلاف")
            else:
                parts.append(f"{three_digits(thousands)} ألف")

        if remainder:
            parts.append(three_digits(remainder))

        return " و ".join([p for p in parts if p])

    @api.model
    def _cron_check_expired_reservation(self):
        if not self.env['ir.config_parameter'].sudo().get_param(
                'arkzayed_18_realestate_development.enable_reservation_expiry_cron'):
            return

        expired_reservations = self.env['real.estate.sale.reservation'].search(
            [('expiry_date', '<=', fields.Datetime.now()),
             ('stop_check_expiration', '=', False),
             '|',
             ('state', 'in', ['initial_reservation', 'on_hold']),
             '&', ('state', '=', 'reserved'), ('is_payment_checked', '=', False)
             ])
        if expired_reservations:
            on_hold_reservations = expired_reservations.filtered(
                lambda r: r.state in ['initial_reservation', 'on_hold'])
            if on_hold_reservations:
                on_hold_reservations.mapped('unit_id').with_context(skip_unit_history=True).sudo().write(
                    {'unit_status': 'onhold_expired_reservation'})

            unpaid_expired_reservations = expired_reservations.filtered(
                lambda r: r.state in ['reserved'] and r.is_payment_checked == False)
            if unpaid_expired_reservations:
                unpaid_expired_reservations.mapped('unit_id').with_context(skip_unit_history=True).sudo().write(
                    {'unit_status': 'expired_reservation'})
            expired_reservations.write({'state': 'expired'})

    def _compute_remaining_expiration_time(self):
        for rec in self:
            if not self.env['ir.config_parameter'].sudo().get_param(
                    'arkzayed_18_realestate_development.enable_reservation_expiry_cron'):
                rec.remaining_time = False
                continue

            if (rec.state in ['initial_reservation', 'on_hold'] or (
                    rec.state == 'reserved' and not rec.is_payment_checked)) and rec.expiry_date and not rec.stop_check_expiration:
                total_seconds = (rec.expiry_date - fields.Datetime.now()).total_seconds()
                total_seconds = total_seconds if total_seconds > 0 else 0

                days, remainder = divmod(int(total_seconds), 86400)
                hours, remainder = divmod(remainder, 3600)
                minutes, _ = divmod(remainder, 60)

                rec.remaining_time = self._format_remaining_time(days, hours, minutes)
            elif rec.state == 'expired':
                rec.remaining_time = 'Expired'
            else:
                rec.remaining_time = False

    def _format_remaining_time(self, days, hours, minutes):
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes or not parts:
            parts.append(f"{minutes}m")
        return f"{' '.join(parts)} left"

    def _get_installments_grouped_by_date(self):
        self.ensure_one()

        installments_by_date = defaultdict(lambda: {
            'unit': self.env['installment.lines'],
            'maintenance': self.env['maintenance.installment.lines'],
        })

        for inst in self.installment_ids:
            installments_by_date[inst.date]['unit'] |= inst
        for inst in self.maintenance_installment_ids:
            installments_by_date[inst.date]['maintenance'] |= inst

        total_price_unit = sum(self.installment_ids.mapped('total_amount'))

        result = []
        down_payment_count = 1
        installment_count = 1

        for date, vals in sorted(installments_by_date.items()):
            unit_lines = vals['unit']
            maintenance_lines = vals['maintenance']

            installment_amount = sum(unit_lines.mapped('total_amount')) if unit_lines else 0
            installment_percentage = round((installment_amount / total_price_unit) * 100, 2) if total_price_unit else 0

            if unit_lines and unit_lines[0].name == 'Down Payment':
                label = f'Down Payment {down_payment_count}'
                down_payment_count += 1
            elif unit_lines and unit_lines[0].name == 'Payment 1':
                label = "Payment 1"
            else:
                label = f'Installment {installment_count}'
                installment_count += 1
            maintenance_amount = maintenance_lines[0].total_amount if len(maintenance_lines) == 1 else 0

            result.append({
                'label': label,
                'date': date,
                'percentage': installment_percentage,
                'unit_amount': installment_amount,
                'maintenance_amount': maintenance_amount,
            })

        return result


    def action_unit_documents(self):
        self.ensure_one()
        if self.unit_id:
            return self.unit_id.action_unit_documents()
        else:
            raise ValidationError(_("You should choose unit first."))

    # action_copy_customer_ownership_ids() moved to
    # realestate.split.parent.mixin (Phase 3 step 5): it was duplicated verbatim here
    # and in the other deal model, differing only in the FK key.

    def action_recalc_installment_serial(self):
        for reservation in self:
            if reservation.installment_ids:
                sorted_lines = reservation.installment_ids.sorted(
                    key=lambda l: l.date
                )
                counter = 1
                for line in sorted_lines:
                    line.serial = counter
                    counter += 1

            if reservation.maintenance_installment_ids:
                sorted_maint_lines = reservation.maintenance_installment_ids.sorted(
                    key=lambda l: l.date
                )
                maint_counter = 1
                for maint_line in sorted_maint_lines:
                    maint_line.serial = maint_counter
                    maint_counter += 1