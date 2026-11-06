from odoo import models, fields, api, _
import calendar
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError, UserError
from babel.dates import format_date
from num2words import num2words
import xlsxwriter
import base64
from io import BytesIO
from odoo.tools import html_escape
import markupsafe
import math
from odoo.addons.isky_18_realestate_developer_unit_inventory.models.selections import referred_by_selection, payment_methods_selection, split_with_selection, \
    contract_type_selection, charge_for_selection, charge_area_selection, charge_price_selection, ownership_selection


def add_months(source_date, months):
    month = source_date.month - 1 + months
    year = int(source_date.year + month / 12)
    month = month % 12 + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


# Contract states in which collections generate sales commission / broker claims
COMMISSION_EXCLUDED_STATES = ('draft', 'draft_contract', 'pending_approvals', 'approved', 'cancelled', 'terminated')


class SaleProposal(models.Model):
    _name = 'sale.proposal'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'installment.mixin', 'realestate.sales.installments.gate', 'realestate.split.parent.mixin', 'realestate.sales.commission.hooks']

    _split_child_fk = 'contract_id'
    _split_parent_label = 'contract'
    _description = 'Sale Proposal'

    def _default_income_account(self):
        return self.env["ir.config_parameter"].sudo().get_param("arkzayed_18_realestate_development.income_account")

    name = fields.Char(string='Contract Reference', required=True, copy=False, readonly=True, index=True,
                       default='New')

    state = fields.Selection(selection=[
        ('draft', 'Draft Proposal'),
        ('draft_contract', 'Draft Contract'),
        ('pending_approvals', 'Pending Approvals'),
        ('approved', 'Approved'),
        ('signed_client', 'Signed by Client'),
        ('operation_review','Review By Operations'),
        ('finance_review','Review By Finance'),
        ('top_management','Top Management'),
        ('signed_ceo', 'Signed by CEO'),
        ('ready_to_deliver_contract', 'Ready to Deliver Contract'),
        ('sent_to_client', 'Sent To Client'),
        ('delivered_contract', 'Delivered Contract'),
        ('ready_to_deliver', 'Unit Ready to Handover'),
        ('delivered', 'Unit Handed Over'),
        ('cancelled', 'Cancelled'),
        ('terminated', 'Terminated'),
    ], default="draft", tracking=True)
    contract_type = fields.Selection(selection=contract_type_selection, default='domestic')
    is_old_contract = fields.Boolean(string='Old Contract', default=False)

    signed_by_client = fields.Boolean(string='Signed by Client', default=False)
    signed_by_ceo = fields.Boolean(string='Signed by CEO', default=False)
    client_signature_date = fields.Date(string='Client Signature Date')
    ceo_signature_date = fields.Date(string='CEO Signature Date')
    cancellation_reason = fields.Text(string='Cancellation Reason', tracking=True)
    cancelled_date = fields.Date(string='Cancellation Date', tracking=True)
    cancelled_by = fields.Many2one('res.users', string='Cancelled By', tracking=True)

    termination_date = fields.Date(string='Termination Date', tracking=True)
    terminated_by = fields.Many2one('res.users', string='Terminated By', tracking=True)

    customer_id = fields.Many2one('res.partner')
    tax_status = fields.Selection([("per_installment", "Per Installment"), ("tax_base_amount", "Tax Base Amount")],
                                  default="per_installment")
    ownership = fields.Selection(selection=ownership_selection,default='single')
    brand_name = fields.Char(string='Arabic Name', compute='_compute_customer_info', inverse='_inverse_customer_info', store=True, copy=False)
    customer_ownership_ids = fields.Many2many('customer.ownership')
    customer_new_ownership_ids = fields.One2many('customer.ownership', 'contract_id', string='Customer Ownership')

    unit_id = fields.Many2one('real.estate.unit')
    unit_project_phase_id = fields.Many2one('real.estate.project.phase', related='unit_id.project_phase', string='Unit Phase', store=True)
    building_id = fields.Many2one('real.estate.building', related='unit_id.building_id', string='Building', store=True)
    unit_number = fields.Char(related='unit_id.unit_number')
    unit_area = fields.Float(related='unit_id.unit_area')
    net_area = fields.Char(related='unit_id.net_area')
    unit_location = fields.Char(related='unit_id.unit_location')
    delivery_date = fields.Date(related='unit_id.delivery_date', string='Delivery Date', store=True, readonly=True)
    indoor_price_per_month_sqm = fields.Float(related='unit_id.indoor_price_per_month_sqm')
    outdoor_price_per_month_sqm = fields.Float(related='unit_id.outdoor_price_per_month_sqm')
    indoor_outdoor_price_per_month_sqm = fields.Float(related='unit_id.indoor_outdoor_price_per_month_sqm')
    indoor_price_sqm = fields.Float(related='unit_id.indoor_price_sqm', string="Indoor Price/SQM")
    outdoor_price_sqm = fields.Float(related='unit_id.outdoor_price_sqm', string="Outdoor Price/SQM")
    unit_price_per_meter = fields.Float('Unit Price / m²')
    outdoor_unit_price_per_meter = fields.Float('Outdoor Unit Price / m²')
    unit_price = fields.Float(compute='_compute_unit_price', store=True)
    unit_price_words = fields.Char(compute='_compute_unit_price_words', store=False)
    unit_plan = fields.Binary(string='Unit Plan', related='unit_id.unit_plan')
    floor_plan = fields.Binary(string='Floor Plan', related='unit_id.floor_plan')
    retail_type = fields.Selection(related='unit_id.retail_type', readonly=True, store=True)
    residential_type = fields.Selection(related='unit_id.residential_type', readlonly=True, store=True)

    contract_issue_date = fields.Date('Issue Date', default=fields.Date.context_today)
    contract_delivery_period = fields.Float("Handover Period")
    contract_issue_week_day = fields.Char(compute='_compute_week_day', store=True)

    def _default_maintenance(self):
        return self.env['maintenance.config'].get_config().maintenance_default

    def _default_maintenance_price_method(self):
        return self.env['maintenance.config'].get_config().maintenance_price_method_default

    def _default_maintenance_percentage(self):
        return self.env['maintenance.config'].get_config().maintenance_percentage_default

    def _default_maintenance_price(self):
        config = self.env['maintenance.config'].get_config()
        if config.maintenance_price_method_default == 'fixed_amount':
            return config.maintenance_amount_default
        return 0.0



    maintenance = fields.Boolean(default=_default_maintenance)
    maintenance_template_id = fields.Many2one('maintenance.template')
    maintenance_price_method = fields.Selection(
        [('fixed_amount', 'Fixed Amount'),
         ('percentage', 'Percentage From Unit Price'),
         ('discount', 'Percentage After Discount')
         ],
        default=_default_maintenance_price_method)
    maintenance_percentage = fields.Float(default=_default_maintenance_percentage)
    maintenance_price = fields.Float('Maintenance Amount', default=_default_maintenance_price)
    maintenance_price_words = fields.Char(compute='_compute_maintenance_price_words', store=False)
    maintenance_monthly_amount = fields.Float(related='maintenance_template_id.monthly_installment_amount')
    maintenance_quarterly_amount = fields.Float(related='maintenance_template_id.quarterly_installment_amount')
    maintenance_semi_annual_amount = fields.Float(related='maintenance_template_id.semi_annual_installment_amount')
    maintenance_annually_amount = fields.Float(related='maintenance_template_id.annual_installment_amount')
    monthly_maintenance_start_date = fields.Date()
    quarterly_maintenance_start_date = fields.Date()
    semi_annual_maintenance_start_date = fields.Date()
    annual_maintenance_start_date = fields.Date()
    maintenance_first_year = fields.Float()
    maintenance_first_year_date = fields.Date()

    charge_for = fields.Selection(selection=charge_for_selection)
    charge_area = fields.Selection(selection=charge_area_selection)
    charge_price = fields.Selection(selection=charge_price_selection)
    reservation_payment = fields.Float('Reservation Payment')
    reservation_payment_date = fields.Date()
    unit_type = fields.Selection(related='unit_id.unit_type',store=True)
    down_payment_id = fields.Many2one(
        'down.payment.increase',
        compute='compute_down_payment_id',
        string='Down Payment Increase Plan',
        help="Select a price increase plan to automatically apply to the unit price",
        store=True
    )
    year_no = fields.Integer(string="Year number", store=True)
    payment_plan_line_id = fields.Many2one('price.plan.line',compute='_compute_plan_line')
    unit_has_discount = fields.Boolean(related='unit_id.has_discount',store=True)

    down_payment = fields.Float('Down Payment',  store=True,compute='_compute_installment_template_amounts')
    down_payment_date = fields.Date()
    delivery_payment = fields.Float()
    delivery_payment_date = fields.Date()
    down_payment_remaining = fields.Float(
        string='Down Payment Remaining',
        compute='_compute_down_payment_remaining',
        store=True
    )
    post_contract_price = fields.Float('Down Payment 2', compute="_compute_post_contract_price", store=True)
    post_contract_date = fields.Date('Down Payment 2 Date')
    expected_delivery_date = fields.Date('Expected Delivery Date',compute="_compute_expected_delivery_date")
    allowance_period = fields.Integer('Allowance Period (Years)')
    expected_after_allowance = fields.Date('Expected After Allowance', compute="_compute_expected_after_allowance")
    extra_period = fields.Integer('Extra Period (Years)')
    extra_period_date = fields.Date('Extra Period Date', compute="_compute_extra_period_date")
    contract_amount = fields.Float(compute='compute_contract_amount')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id,
                                  domain=[('active', '=', True)])

    installment_template_id = fields.Many2one('installment.template')
    installment_monthly_amount = fields.Float(related='installment_template_id.monthly_installment_amount')
    installment_quarterly_amount = fields.Float(related='installment_template_id.quarterly_installment_amount')
    installment_semi_annual_amount = fields.Float(related='installment_template_id.semi_annual_installment_amount')
    installment_annually_amount = fields.Float(related='installment_template_id.annual_installment_amount')
    monthly_installment_start_date = fields.Date(compute='_compute_first_installment_start_dates', store=True, readonly=False)
    quarterly_installment_start_date = fields.Date(compute='_compute_first_installment_start_dates', store=True, readonly=False)
    semi_annual_installment_start_date = fields.Date(compute='_compute_first_installment_start_dates', store=True, readonly=False)
    annual_installment_start_date = fields.Date(compute='_compute_first_installment_start_dates', store=True, readonly=False)

    @api.depends('reservation_payment_date')
    def _compute_first_installment_start_dates(self):
        for rec in self:
            if rec.reservation_payment_date:
                rec.monthly_installment_start_date = rec.reservation_payment_date
                rec.quarterly_installment_start_date = rec.reservation_payment_date
                rec.semi_annual_installment_start_date = rec.reservation_payment_date
                rec.annual_installment_start_date = rec.reservation_payment_date
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

    account_income = fields.Many2one("account.account", "Income Account")
    service_account_id = fields.Many2one("account.account")
    market_fees_account_id = fields.Many2one("account.account")

    include_free_parking = fields.Boolean('Free Parking')
    separate_parking_price = fields.Boolean()
    charging_slots = fields.Selection([("specific slots", "Specific Slots"), ("number of slots", "Number Of Slots")])
    slots = fields.Selection([("specific slots", "Specific Slots"), ("number of slots", "Number Of Slots")])
    number_of_slots = fields.Integer(compute="_compute_parking_from_apartment_type", store=True, readonly=False)
    number_of_slots_for_report = fields.Integer(default=0)
    parking_price = fields.Float()
    parking_installment_template_id = fields.Many2one('maintenance.template', domain=[('type', '=', 'parking')])
    monthly_parking_duration = fields.Integer(related="parking_installment_template_id.monthly_installment_duration")
    quarter_parking_duration = fields.Integer(related="parking_installment_template_id.quarterly_installment_duration")
    semi_parking_annual_duration = fields.Integer(
        related="parking_installment_template_id.semi_annual_installment_duration")
    annual_parking_duration = fields.Integer(related="parking_installment_template_id.annual_installment_duration")
    monthly_parking_installment_start_date = fields.Date()
    quarterly_parking_installment_start_date = fields.Date()
    semi_annual_parking_installment_start_date = fields.Date()
    annual_parking_installment_start_date = fields.Date()

    construction_deposit = fields.Float()
    lg_required = fields.Boolean(deafult=False)

    installment_ids = fields.One2many('installment.lines', 'sale_proposal_id')

    delay_payment = fields.Float('Delay of payment')

    maintenance_installment_ids = fields.One2many('maintenance.installment.lines', 'sale_proposal_id')

    lg_number = fields.Char()
    bank_name = fields.Char()
    lg_amount = fields.Float()
    lg_expiry_date = fields.Date(string='Expiry Date')

    parking_lines_ids = fields.One2many('real.estate.unit', 'sale_proposal_parking_id', string='Parking Lines')

    delivery_conditions = fields.Text()
    delivery_terms = fields.Text()
    refund_policy = fields.Text()
    cancellation_policy = fields.Text()

    installment_parking_line_ids = fields.One2many('loan.line', 'installments_parking_sale_proposal_id')

    charging_parking_lines_ids = fields.One2many('real.estate.unit', 'sale_proposal_parking_charging_id',
                                                 string='Parking Charging Lines')

    referred_by = fields.Selection(selection=referred_by_selection)
    referred_by_employee_id = fields.Many2one('hr.employee')
    referred_by_partner_id = fields.Many2one('res.partner')
    other = fields.Char()

    total_unit_selling_price = fields.Float(string="Unit Selling Price", related='unit_price')
    maintenance_1st_year_advance_percentage = fields.Float(string="Maintenance 1st Year Advance Payment %")
    maintenance_1st_year_advance = fields.Float(string="Maintenance 1st Year Advance Payment",
                                                compute="_compute_maintenance_1st_year_advance")
    maintenance_vat = fields.Float(string="Maintenance VAT Amount", compute="_compute_maintenance_vat", store=True)
    maintenance_vat_id = fields.Many2one('account.tax')
    unit_vat = fields.Float(string="Unit VAT Amount", compute="_compute_unit_vat")
    unit_vat_id = fields.Many2one('account.tax')
    total_unit_price_incl_maintenance = fields.Float(string="Total Unit Price (including Maintenance price)",
                                                     compute="_compute_total_unit_price_incl_maintenance")
    note = fields.Text()

    eoi_id = fields.Many2one(comodel_name="eoi.eoi", string="EOI")
    eoi_amount = fields.Float(
        string='EOI Amount',
        compute='_compute_eoi_amount',
        store=True,
    )
    eoi_date = fields.Date(string='Eoi Date', default=fields.Date.today())

    payment_methods = fields.Selection(selection=payment_methods_selection, default='cheque', string='Payment Method')
    analytic_account_id = fields.Many2one(comodel_name="account.analytic.account")
    company_id = fields.Many2one('res.company', default=lambda self: self._default_company_id())

    # The cheque-generation configuration block (cheque_is_serial, number_of_banks,
    # cheque_starting_number*, bank_id*, bank_*_installments_count, cheque_ids,
    # linked_cheque_ids, cheque_count) moved to
    # isky_18_realestate_developer_sales_cheques (Phase 3 step 3), supplement S1:
    # every one of those fields exists only to drive cheque creation.

    sale_contract_reservation_id = fields.Many2one('real.estate.sale.reservation', string='Reservation')
    sale_reserved = fields.Boolean(string='Sale Reserved', default=False, copy=False)

    # Journal Entry Fields
    delivery_move_id = fields.Many2one('account.move', string='Delivery Journal Entry', readonly=True, copy=False)
    journal_entry_count = fields.Integer(string='Journal Entries', compute='_compute_journal_entry_count')

    delivery_invoice_id = fields.Many2one('account.move', string='Delivery Invoice', readonly=True, copy=False)
    invoice_count = fields.Integer(string='Invoices', compute='_compute_invoice_count')

    archive_place_id = fields.Many2one(
        'archive.place',
        string='Archive Place',
        index=True,
        tracking=True,
        help="Physical storage location of the hard-copy contract"
    )

    # approvals
    finance_user_approve = fields.Boolean(string='Finance Approval', tracking=True)
    finance_approve = fields.Boolean(string='Finance Two Approval', tracking=True)
    manager_approve = fields.Boolean(string='Manager Approval', tracking=True)

    is_finance_approver = fields.Boolean(compute='_compute_approval_group_membership')
    is_finance_two_approver = fields.Boolean(compute='_compute_approval_group_membership')
    is_manager_approver = fields.Boolean(compute='_compute_approval_group_membership')

    def _deal_project(self):
        """A contract has no project_id of its own (step 0 finding): resolve through the unit,
        then through the reservation it came from."""
        self.ensure_one()
        return self.unit_id.project_id or self.sale_contract_reservation_id.project_id

    def _default_company_id(self):
        developer_company = self.env.ref('base.main_company')
        return developer_company.id if developer_company else False

    @api.depends('unit_id', 'name')
    @api.depends_context('show_unit_in_name')
    def _compute_display_name(self):
        """Show "Unit (Contract Reference)" instead of just the contract reference,
        but only when explicitly requested via context (e.g. the Commission Summary
        Report wizard's contract picker) so every other reference to a contract
        elsewhere in the system is unaffected."""
        if not self.env.context.get('show_unit_in_name'):
            return super()._compute_display_name()
        for rec in self:
            unit_name = rec.unit_id.display_name if rec.unit_id else ''
            rec.display_name = '%s (%s)' % (unit_name, rec.name) if unit_name else (rec.name or '')

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if self.env.context.get('show_unit_in_name') and name:
            domain = ['|', ('name', operator, name), ('unit_id.system_code', operator, name)] + list(args or [])
            records = self.search(domain, limit=limit)
            return [(record.id, record.display_name) for record in records]
        return super().name_search(name=name, args=args, operator=operator, limit=limit)

    @api.depends_context('uid')
    def _compute_approval_group_membership(self):
        is_finance = self.env.user.has_group('isky_18_realestate_developer_sales_crm.group_finance_approval')
        is_finance_two = self.env.user.has_group('isky_18_realestate_developer_sales_crm.group_finance_two_approval')
        is_manager = self.env.user.has_group('isky_18_realestate_developer_sales_crm.group_manager_approval')
        for rec in self:
            rec.is_finance_approver = is_finance
            rec.is_finance_two_approver = is_finance_two
            rec.is_manager_approver = is_manager

    # Broker
    broker_contract_id = fields.Many2one('broker.contract', string='Broker Contract')
    split_commission_with_agents = fields.Boolean(
        string='Split Commission with Agents',
        help="When enabled, the agents selected below each get their own claim for "
             "their commission %."
    )
    agent_commission_ids = fields.Many2many(
        'broker.team.member',
        string='Agents',
        help="Team members who will each receive their own commission claim for this contract."
    )

    @api.onchange('split_commission_with_agents')
    def _onchange_split_commission_with_agents(self):
        if not self.split_commission_with_agents:
            self.agent_commission_ids = [(5, 0, 0)]

    @api.onchange('referred_by_partner_id')
    def _onchange_referred_by_partner_id_agents(self):
        self.agent_commission_ids = [(5, 0, 0)]

    # Broker Claim
    broker_claim_id = fields.Many2one('broker.claim', string='Broker Claim',)
    broker_claim_created = fields.Boolean(string='Broker Claim Created', default=False, copy=False)

    # Ambassador Claim
    ambassador_claim_id = fields.Many2one('broker.claim', string='Ambassador Claim')
    ambassador_claim_created = fields.Boolean(string='Ambassador Claim Created', default=False, copy=False)

    user_id = fields.Many2one(
        'res.users',
        string='Salesperson',
        tracking=True,
        # domain on job_level_id.is_* removed: job.level lives in L3 (commission), and a
        # Many2many domain referencing it registers an implicit dependency that crashes
        # field-setup while this L2 module is loading, before L3 exists yet.
    )

    # Commission tracking
    total_collected_amount = fields.Float(
        string='Total Collected',
        compute='_compute_collection_amounts',
        store=True
    )
    collection_percentage = fields.Float(
        string='Collection %',
        compute='_compute_collection_amounts',
        store=True
    )

    # commission_achievement_ids / non_sales_claim_ids / all_commission_claim_ids (One2many to
    # realestate.commission.achievement / broker.claim, both L3) - and the two *_count integer
    # fields that compute off them, since @api.depends on a field that doesn't exist in this
    # module's own _fields yet (it's added later by commission's _inherit) fails the same way -
    # moved to isky_18_realestate_developer_commission/models/core/sale_proposal_crm_ext.py.
    # L2 must not depend on L3.

    split_deal = fields.Boolean(string='Split Deal')
    split_with = fields.Selection(selection=split_with_selection, string='Split With')

    partner_ids = fields.Many2many(
        'res.partner',
        'sale_proposal_partner_rel',
        'proposal_id',
        'partner_id',
        string='Customers'
    )

    employee_ids = fields.Many2many(
        'hr.employee',
        'sale_proposal_employee_rel',
        'proposal_id',
        'employee_id',
        string="Referral"
    )

    broker_ids = fields.Many2many(
        'res.partner',
        'sale_proposal_broker_rel',
        'proposal_id',
        'broker_id',
        string="Outside Broker",
        domain="[('is_broker','=',True)]"
    )

    ambassador_ids = fields.Many2many(
        'res.partner',
        'sale_proposal_ambassador_rel',
        'proposal_id',
        'ambassador_id',
        string="Ambassador",
        domain="[('is_ambassador','=',True)]"
    )

    non_sales_ids = fields.Many2many(
        'res.users',
        'sale_proposal_non_sales_rel',
        'proposal_id',
        'user_id',
        string='Non Sales'
    )

    sales_ids = fields.Many2many(
        'res.users',
        'sale_proposal_sales_rel',
        'proposal_id',
        'sales_user_id',
        string='Sales',
        # domain on job_level_id.is_* removed: job.level lives in L3 (commission), and a
        # Many2many domain referencing it registers an implicit dependency that crashes
        # field-setup while this L2 module is loading, before L3 exists yet.
    )

    # commission_ids field (One2many to realestate.commission, L3) moved to
    # isky_18_realestate_developer_commission/models/core/sale_proposal_crm_ext.py -
    # that model is L3's own, and L2 must not depend on L3.

    # Collection Entry
    client_sign_collection_move_id = fields.Many2one(
        'account.move',
        string='Client Signature Collection Entry',
        readonly=True,
        copy=False
    )
    client_sign_collection_count = fields.Integer(
        string='Collection Entries',
        compute='_compute_client_sign_collection_count'
    )

    # Add field for count
    sale_reservation_count = fields.Integer(
        string='Reservations',
        compute='_compute_sale_reservation_count'
    )

    # contracted fields
    contracted_build_up_area = fields.Float()
    contracted_terrace_area = fields.Float(string='Contracted Terrace Area')
    contracted_outdoor_area = fields.Float(string='Contracted Outdoor/Garden Area')
    contracted_total_area = fields.Float(compute='_compute_contracted_total_area', store=True)
    contracted_selling_price = fields.Float(compute="_compute_contracted_selling_price", inverse="_inverse_contracted_selling_price", string="Price Before Discount", readonly=False)
    new_total_gross_area = fields.Float(related='unit_id.new_total_gross_area', string='New Total Gross Area(Indoor + Terrace)', store=True)

    paid_installments_amount = fields.Float(
        string='Paid Amount',
        compute='_compute_paid_installments',
        store=True,
        help="Total amount of installments marked as paid"
    )

    installments_due_to_date_amount = fields.Float(
        string='Installments Due To Date',
        compute='_compute_installments_due_to_date_amount',
        store=True,
        index=True,
        help="Sum of installment amounts with date on or before today, "
             "only for contracts in active stages (pending_approvals, approved, "
             "signed_client, signed_ceo, ready_to_deliver, delivered)."
    )

    paid_installments_percentage = fields.Float(
        string='Collection Percentage',
        compute='_compute_paid_installments',
        store=True,
        help="Percentage of unit price that has been collected through paid installments"
    )

    paid_maintenance_amount = fields.Float(
        string='Paid Maintenance Amount',
        compute='_compute_paid_maintenance',
        store=True,
        help="Total amount of maintenance installments marked as paid"
    )

    paid_maintenance_percentage = fields.Float(
        string='Maintenance Collection Percentage',
        compute='_compute_paid_maintenance',
        store=True,
        help="Percentage of maintenance price that has been collected"
    )

    down_payment_words = fields.Char(compute='_compute_down_payment_words', store=False)

    has_floor = fields.Boolean(compute='_compute_has_floor_building')
    has_building = fields.Boolean(compute='_compute_has_floor_building')
    is_vip = fields.Boolean(string='VIP Customer', default=False)

    additional_owners_block = fields.Html(string="Additional Owners (Contract)",compute="_compute_additional_owners_block",store=False,sanitize=False,)

    buyer_signature_block = fields.Html(string="Buyer Signature Block",compute="_compute_buyer_signature_block",store=False,sanitize=False)
    signatures_section = fields.Html(string="Signatures Section",compute="_compute_signatures_section",store=False,sanitize=False)
    installment_payments_regular = fields.Boolean("منتظم أقساط")
    maintenance_payments_regular = fields.Boolean("منتظم صيانة")
    payment_regularity_state = fields.Selection(
        [('regular', 'منتظم'),
         ('installment_regular', 'منتظم أقساط'),
         ('maintenance_regular', 'منتظم صيانة'),
         ('irregular', 'غير منتظم')],
        string='Payment State',
        compute='_compute_payment_regularity_state',
        store=True,
    )

    customer_code = fields.Char(string='Customer Code', compute='_compute_customer_info',
                                inverse='_inverse_customer_info', store=True, copy=False)
    mobile = fields.Char(string='Customer Mobile Number', compute='_compute_customer_info',
                         inverse='_inverse_customer_info', store=True, copy=False)
    email = fields.Char(string='Customer Email Address', compute='_compute_customer_info',
                        inverse='_inverse_customer_info', store=True, copy=False)
    address_1 = fields.Text(string='Customer Address 1', compute='_compute_customer_info',
                            inverse='_inverse_customer_info', store=True, copy=False)
    address_2 = fields.Text(string='Customer Address 2', compute='_compute_customer_info',
                            inverse='_inverse_customer_info', store=True, copy=False)
    address = fields.Char(related='customer_id.street', string='Address', readonly=False, store=True)
    national_id = fields.Char(string='Customer National ID Number', compute='_compute_customer_info',
                              inverse='_inverse_customer_info', store=True, copy=False)

    has_contract = fields.Boolean(string='Has Contract', compute='_compute_has_contract')
    is_broker_partner = fields.Boolean(compute='_compute_is_broker_partner')

    discount_percentage = fields.Float(string="Discount Percentage", tracking=True)
    discount_approved_by = fields.Many2one('discount.config', tracking=True, copy=False)
    price_after_discount = fields.Float(string="Final Price", compute='_compute_price_after_discount',
                                        inverse='_inverse_price_after_discount', store=True, readonly=False, tracking=True)

    old_customer_id = fields.Many2one(
        'res.partner',
        copy=False,
    )
    ownership_changed = fields.Boolean(copy=False)
    ownership_change_journal_id = fields.Many2one(
        'account.move',
        string='Ownership Change Journal Entry',
        readonly=True,
        copy=False,
    )
    ownership_change_journal_count = fields.Integer(
        string='Ownership Change Journal', compute='_compute_ownership_change_journal_count')
    apply_discount_on_down_payment = fields.Boolean(default=True)
    apply_discount_on_post_contract = fields.Boolean(string='Apply Discount On Down Payment2', default=True)
    payment_ids = fields.One2many('account.payment', 'sale_proposal_id', string='Payments')
    # Payments whose MAIN contract is another one but that settle installments of
    # THIS contract through allocations (multi-contract customer payments).
    linked_payment_ids = fields.Many2many(
        'account.payment',
        string='Linked Payments',
        compute='_compute_linked_payment_ids',
    )
    payment_count = fields.Integer(string='Payment Count', compute='_compute_payment_count')

    show_create_installments = fields.Boolean(
        string='Show Create Installments',
        compute="_compute_show_create_installments",
        default=False,
        copy=False
    )
    show_create_maintenance = fields.Boolean(
        string='Show Create Maintenance',
        compute="_compute_show_create_maintenance",
        default=False,
        copy=False
    )

    force_recalculate_installments = fields.Boolean(default=False, copy=False)
    force_recalculate_maintenance = fields.Boolean(default=False, copy=False)

    @api.constrains('customer_id', 'national_id')
    def _check_customer_national_id_or_passport(self):
        for rec in self:
            if (not rec.customer_id.passport_number or not rec.customer_id.passport_number.strip()) and (
                    not rec.national_id or not rec.national_id.strip()):
                raise ValidationError(_("Please provide either a National ID or a Passport Number for customer '%s'.",
                                        rec.customer_id.name))

    @api.depends('installment_ids', 'force_recalculate_installments', 'state',
                 'sale_contract_reservation_id', 'sale_contract_reservation_id.installment_ids')
    def _compute_show_create_installments(self):
        for rec in self:
            rec.show_create_installments = False
            if rec.state in ['draft', 'draft_contract', 'pending_approvals']:
                rec.show_create_installments = True
                if rec.sale_contract_reservation_id and rec.sale_contract_reservation_id.installment_ids:
                    # Hide if it came directly from a reservation that already calculated lines
                    rec.show_create_installments = False
                if rec.force_recalculate_installments:
                    # Always show if user changed a template/price manually in the contract
                    rec.show_create_installments = True
                if not rec.installment_ids:
                    # Show if it's a direct contract (no reservation) and has no lines yet
                    rec.show_create_installments = True
                if not rec.force_recalculate_installments:
                    rec.show_create_installments = False

    @api.depends('maintenance_installment_ids', 'force_recalculate_maintenance', 'state', 'maintenance',
                 'sale_contract_reservation_id', 'sale_contract_reservation_id.maintenance_installment_ids')
    def _compute_show_create_maintenance(self):
        for rec in self:
            rec.show_create_maintenance = False
            if rec.maintenance:
                rec.show_create_maintenance = True

            if rec.state in ['draft', 'draft_contract', 'pending_approvals']:
                rec.show_create_maintenance = True
                if rec.sale_contract_reservation_id and rec.sale_contract_reservation_id.maintenance_installment_ids:
                    # 2. Hide if it came directly from a reservation that already calculated lines
                    rec.show_create_maintenance = False

                if rec.force_recalculate_maintenance:
                    # 1. Always show if user changed a template/price manually in the contract
                    rec.show_create_maintenance = True
                if not rec.maintenance_installment_ids:
                    # 3. Show if it's a direct contract (no reservation) and has no lines yet
                    rec.show_create_maintenance = True
                if not rec.force_recalculate_maintenance:
                    rec.show_create_maintenance = False

    @api.onchange(
        'price_after_discount', 'contracted_selling_price', 'discount_percentage',
        'installment_template_id', 'installment_template_2_id',
        'down_payment', 'delivery_payment', 'post_contract_price',
        'monthly_installment_start_date', 'quarterly_installment_start_date',
        'semi_annual_installment_start_date', 'annual_installment_start_date'
    )
    def _onchange_installment_triggers(self):
        if self.state in ['draft', 'draft_contract', 'pending_approvals'] and self.installment_ids:
            self.force_recalculate_installments = True

    @api.onchange(
        'maintenance_price', 'maintenance_template_id', 'maintenance',
        'maintenance_price_method', 'maintenance_percentage',
        'monthly_maintenance_start_date', 'quarterly_maintenance_start_date',
        'semi_annual_maintenance_start_date', 'annual_maintenance_start_date'
    )
    def _onchange_maintenance_triggers(self):
        if self.state in ['draft', 'draft_contract', 'pending_approvals'] and self.maintenance_installment_ids:
            self.force_recalculate_maintenance = True

    @api.depends(
        'installment_ids.allocation_ids.payment_id',
        'maintenance_installment_ids.allocation_ids.payment_id',
        'payment_ids',
    )
    def _compute_linked_payment_ids(self):
        for rec in self:
            allocated_payments = (
                rec.installment_ids.mapped('allocation_ids.payment_id')
                | rec.maintenance_installment_ids.mapped('allocation_ids.payment_id')
            )
            rec.linked_payment_ids = allocated_payments - rec.payment_ids

    @api.depends('payment_ids', 'linked_payment_ids')
    def _compute_payment_count(self):
        for rec in self:
            rec.payment_count = len(rec.payment_ids | rec.linked_payment_ids)

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

    def action_change_ownership(self):
        self.ensure_one()
        return {
            'name': _('Change Ownership'),
            'type': 'ir.actions.act_window',
            'res_model': 'contract.change.ownership.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_contract_id': self.id,
                'default_current_customer_id': self.customer_id.id,
            }
        }

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


    @api.depends('customer_id', 'customer_id.customer_code', 'customer_id.mobile', 'customer_id.email',
                 'customer_id.address_1', 'customer_id.address_2',
                 'customer_id.national_id', 'customer_id.ref')
    def _compute_customer_info(self):
        for rec in self:
            if self.env.context.get('skip_customer_info_sync_from_contract'):
                continue
            if rec.customer_id:
                rec.customer_code = rec.customer_id.customer_code
                rec.mobile = rec.customer_id.mobile
                rec.email = rec.customer_id.email
                rec.address_1 = rec.customer_id.address_1
                rec.address_2 = rec.customer_id.address_2
                rec.national_id = rec.customer_id.national_id
                rec.brand_name = rec.customer_id.ref
            else:
                rec.customer_code = False
                rec.mobile = False
                rec.email = False
                rec.address_1 = False
                rec.address_2 = False
                rec.national_id = False
                rec.brand_name = False

    def _inverse_customer_info(self):
        for rec in self:
            if rec.customer_id:
                rec.customer_id.with_context(skip_customer_info_sync_from_contract=True).write({
                    'customer_code': rec.customer_code,
                    'mobile': rec.mobile,
                    'email': rec.email,
                    'address_1': rec.address_1,
                    'address_2': rec.address_2,
                    'national_id': rec.national_id,
                    'ref': rec.brand_name,
                })

    @api.depends('installment_payments_regular', 'maintenance_payments_regular')
    def _compute_payment_regularity_state(self):
        for rec in self:
            if rec.installment_payments_regular and rec.maintenance_payments_regular:
                rec.payment_regularity_state = 'regular'
            elif rec.installment_payments_regular:
                rec.payment_regularity_state = 'installment_regular'
            elif rec.maintenance_payments_regular:
                rec.payment_regularity_state = 'maintenance_regular'
            else:
                rec.payment_regularity_state = 'irregular'
    @api.depends(
        'ownership',
        'customer_id',
        'customer_id.name',
        'customer_id.national_id',
        'customer_id.passport_number',
        'customer_id.phone',
        'customer_id.email',
        'customer_id.contact_address',
        'customer_id.country_id',
        'address',
        'customer_new_ownership_ids',
        'customer_new_ownership_ids.customer_id',
        'customer_new_ownership_ids.customer_id.name',
        'customer_new_ownership_ids.customer_id.national_id',
        'customer_new_ownership_ids.customer_id.passport_number',
        'customer_new_ownership_ids.customer_id.phone',
        'customer_new_ownership_ids.customer_id.email',
        'customer_new_ownership_ids.customer_id.contact_address',
        'customer_new_ownership_ids.customer_id.country_id',
        'customer_new_ownership_ids.customer_id.street',
    )
    def _compute_additional_owners_block(self):
        for rec in self:
            blocks = []

            # Single ownership
            if rec.ownership == 'single':
                if not rec.customer_id:
                    rec.additional_owners_block = ''
                    continue

                c = rec.customer_id
                name = c.ref or '......................'
                id_no = getattr(c, 'national_id', False) or getattr(c, 'passport_number', False) or '......................'
                nationality = (c.country_id.nationality if c.country_id else '') or '......................'
                address = rec.address or '......................'
                phone = (c.mobile or '').replace(' ', '') or '......................'
                email = c.email or '......................'

                name = html_escape(name)
                id_no = html_escape(id_no)
                nationality = html_escape(nationality)
                address = html_escape(address)
                phone = html_escape(phone)
                email = html_escape(email)

                # Each line is its own right-aligned paragraph (not inherited
                # justify, and not the "ثانيا: " line's hanging indent) so
                # the name lines up with the rest instead of starting further
                # right at the hanging-indent position.
                lines = [
                    f"الإسم: {name}",
                    f"رقم قومي / جواز سفر رقم: {id_no}",
                    f"الجنسية: {nationality}",
                    f"العنوان: {address}",
                    f'رقم التليفون: <span dir="ltr">{phone}</span>',
                    f"البريد الإلكتروني: {email}",
                ]
                rec.additional_owners_block = "".join(
                    f'<p dir="rtl" style="text-align:right; text-indent:0; margin:0;">{line}</p>'
                    for line in lines
                )

            # Multiple ownership
            elif rec.ownership == 'multiple':
                if not rec.customer_new_ownership_ids:
                    rec.additional_owners_block = ''
                    continue

                for owner in rec.customer_new_ownership_ids:
                    c = owner.customer_id
                    if not c:
                        continue

                    name = c.ref or '......................'
                    id_no = getattr(c, 'national_id', False) or getattr(c, 'passport_number', False) or '......................'
                    nationality = (c.country_id.nationality if c.country_id else '') or '......................'
                    address = c.street or '......................'
                    phone = (c.phone or '').replace(' ', '') or '......................'
                    email = c.email or '......................'

                    name = html_escape(name)
                    id_no = html_escape(id_no)
                    nationality = html_escape(nationality)
                    address = html_escape(address)
                    phone = html_escape(phone)
                    email = html_escape(email)

                    owner_lines = [
                        f"الإسم: {name}",
                        f"رقم قومي / جواز سفر رقم: {id_no}",
                        f"الجنسية: {nationality}",
                        f"العنوان: {address}",
                        f'رقم التليفون: <span dir="ltr">{phone}</span>',
                        f"البريد الإلكتروني: {email}",
                    ]
                    blocks.extend(
                        f'<p dir="rtl" style="text-align:right; text-indent:0; margin:0;">{line}</p>'
                        for line in owner_lines
                    )
                    blocks.append('<p dir="rtl" style="margin:0;">&nbsp;</p>')

                rec.additional_owners_block = "".join(blocks)


            else:
                rec.additional_owners_block = ''

    @api.depends('installment_template_id', 'installment_template_id.contracting_percentage',
                 'installment_template_2_id', 'installment_template_2_id.contracting_percentage',
                 'contracted_selling_price', 'price_after_discount', 'sale_contract_reservation_id',
                 'sale_contract_reservation_id.post_contract_price', 'apply_discount_on_post_contract')
    def _compute_post_contract_price(self):
        for rec in self:
            contract_percentage = 0
            if rec.installment_template_id:
                contract_percentage = (rec.installment_template_id.contracting_percentage) / 100
            elif rec.installment_template_2_id:
                contract_percentage = (rec.installment_template_2_id.contracting_percentage) / 100

            amount = rec.price_after_discount if rec.apply_discount_on_post_contract else rec.contracted_selling_price
            rec.post_contract_price = amount * contract_percentage if contract_percentage else 0

    @api.depends(
        'ownership',
        'customer_id',
        'customer_id.name',
        'customer_new_ownership_ids',
        'customer_new_ownership_ids.customer_id',
        'customer_new_ownership_ids.customer_id.name',
    )
    def _compute_signatures_section(self):

        def _sig_line(label, name, line_width_px=240):
            name = html_escape(name or '')
            return f"""
                <div style="margin-bottom:28px; text-align:right;">
                    <div style="margin-bottom:10px;">
                        <strong>{label}</strong> {name}
                    </div>
                    <div>
                        <strong>التوقيع:</strong>
                    </div>
                </div>
            """

        for rec in self:
            mode = rec.ownership
            if mode not in ('single', 'multiple'):
                mode = 'multiple' if rec.customer_new_ownership_ids else 'single'

            buyer_lines = ""

            if mode == 'single':
                buyer_name = rec.customer_id.ref if rec.customer_id else ''
                buyer_lines = _sig_line("الاسم:", buyer_name)

            else:
                owners = rec.customer_new_ownership_ids
                if owners:
                    for owner in owners:
                        c = owner.customer_id
                        if not c:
                            continue
                        buyer_lines += _sig_line("الاسم:", c.ref)
                else:
                    buyer_name = rec.customer_id.ref if rec.customer_id else ''
                    buyer_lines = _sig_line("الاسم:", buyer_name)

            buyer_block = f"""
                <div dir="rtl" style="width:100%; box-sizing:border-box;">
                    {buyer_lines}
                </div>
            """

            seller_block = """
                <div dir="rtl" style="width:100%; box-sizing:border-box; text-align:right;">
                    <div style="font-weight:bold; margin-bottom:30px;">
                        شركة ذا آرك جروب للتطوير العقاري
                    </div>
                    <div style="margin-bottom:6px;">
                        <strong>عنه:</strong> محمد امين الدخميسي
                    </div>
                    <div style="margin-bottom:25px;">
                        <strong>الصفة:</strong> المدير التنفيذي
                    </div>
                    <div>
                        <strong>التوقيع:</strong>
                    </div>
                </div>
            """

            rec.signatures_section = f"""
                <div dir="rtl" style="width:100%; font-family:Arial;">

                    <div style="width:48%; display:inline-block; vertical-align:top; text-align:right;">
                        <div style="font-weight:bold; margin-bottom:6px;">
                            الطرف الأول البائع
                        </div>
                        {seller_block}
                    </div>

                    <div style="width:48%; display:inline-block; vertical-align:top; text-align:right;">
                        <div style="font-weight:bold; margin-bottom:15px;">
                            الطرف الثاني المشتري
                        </div>
                        {buyer_block}
                    </div>

                </div>
            """

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

    @api.depends('price_after_discount')
    def _compute_unit_price_words(self):
        for rec in self:
            if rec.price_after_discount:
                rec.unit_price_words = num2words(round(rec.price_after_discount), lang='ar', to='currency',
                                                 currency='EGP')
            else:
                rec.unit_price_words = False

    @api.depends('down_payment')
    def _compute_down_payment_words(self):
        for rec in self:
            if rec.down_payment:
                rec.down_payment_words = num2words(round(rec.down_payment), lang='ar', to='currency',
                                                   currency='EGP')
            else:
                rec.down_payment_words = False

    @api.depends('contract_issue_date')
    def _compute_week_day(self):
        for rec in self:
            if rec.contract_issue_date:
                rec.contract_issue_week_day = format_date(
                    rec.contract_issue_date,
                    format='EEEE',
                    locale='ar'
                )
            else:
                rec.contract_issue_week_day = False

    @api.depends('maintenance_price')
    def _compute_maintenance_price_words(self):
        for rec in self:
            if rec.maintenance_price:
                rec.maintenance_price_words = num2words(round(rec.maintenance_price), lang='ar', to='currency',
                                                        currency='EGP')
            else:
                rec.maintenance_price_words = False

    @api.depends(
        'installment_ids.paid',
        'installment_ids.paid_amount',
        'installment_ids.amount',
        'price_after_discount',
    )
    def _compute_paid_installments(self):
        """Calculate total paid installments and collection percentage"""
        for rec in self:
            # Sum all paid installment amounts: a ticked installment counts in full, whatever
            # part of it payments and cheques actually cover.
            paid_amount = sum(
                line.amount for line in rec.installment_ids if line.paid
            )

            # sum partial paid installments lines: only the money really registered against
            # them, and never more than the installment itself.
            partially_paid_amount = sum(
                min(line.paid_amount, line.amount)
                for line in rec.installment_ids if not line.paid and line.paid_amount > 0.0
            )

            total_collected = paid_amount + partially_paid_amount


            rec.paid_installments_amount = total_collected

            # Calculate percentage based on unit price
            if rec.price_after_discount > 0:
                rec.paid_installments_percentage = (total_collected / rec.price_after_discount) * 100
            else:
                rec.paid_installments_percentage = 0.0

    _ACTIVE_CONTRACT_STATES_FOR_DUE = (
        'pending_approvals', 'sent_to_client','approved', 'signed_client',
        'signed_ceo', 'ready_to_deliver_contract', 'delivered_contract','ready_to_deliver', 'delivered',
    )

    @api.depends(
        'state',
        'installment_ids.amount',
        'installment_ids.date',
    )
    def _compute_installments_due_to_date_amount(self):
        today = fields.Date.today()
        active_states = self._ACTIVE_CONTRACT_STATES_FOR_DUE
        for rec in self:
            if rec.state in active_states:
                rec.installments_due_to_date_amount = sum(
                    line.amount for line in rec.installment_ids
                    if line.date and line.date <= today
                )
            else:
                rec.installments_due_to_date_amount = 0.0

    @api.depends(
        'maintenance_installment_ids.paid',
        'maintenance_installment_ids.amount',
        'maintenance_price'
    )
    def _compute_paid_maintenance(self):
        """Calculate total paid maintenance installments and collection percentage"""
        for rec in self:
            # Sum all paid maintenance installment amounts
            paid_amount = sum(
                line.amount for line in rec.maintenance_installment_ids if line.paid
            )

            rec.paid_maintenance_amount = paid_amount

            # Calculate percentage based on maintenance price
            if rec.maintenance_price > 0:
                rec.paid_maintenance_percentage = (paid_amount / rec.maintenance_price) * 100
            else:
                rec.paid_maintenance_percentage = 0.0

    @api.onchange('number_of_slots')
    def onchange_method(self):
        self.number_of_slots_for_report = self.number_of_slots

    @api.depends('unit_id.unit_type')
    def compute_down_payment_id(self):
        for rec in self:
            if rec.unit_id:
                rec.down_payment_id = self.env['down.payment.increase'].search(
                    [('unit_type', '=', rec.unit_id.unit_type)],
                    limit=1
                )
            else:
                rec.down_payment_id = False

    @api.depends('unit_id', 'down_payment_id', 'year_no', 'unit_price', 'unit_has_discount', )
    def _compute_plan_line(self):
        for rec in self:
            rec.payment_plan_line_id = False
            if rec.unit_has_discount:
                continue
            elif rec.down_payment_id and rec.year_no:
                plan_line = rec.down_payment_id.price_plan_ids.filtered(
                    lambda l: l.year_no == rec.year_no
                )
                if plan_line:
                    rec.payment_plan_line_id = plan_line[0] if len(plan_line) > 1 else plan_line

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
    def _compute_unit_price(self):
        for rec in self:
            if rec.unit_id:
                rec.unit_price = rec.unit_id.total_price_unit if rec.unit_id else 0.0

    # @api.depends('payment_plan_line_id', 'payment_plan_line_id.down_payment', 'unit_id',
    #              'unit_price', 'unit_id.has_discount', 'unit_id.effective_down_payment',
    #              'installment_template_id', 'installment_template_id.contracting_percentage')
    # def _compute_down_payment(self):
    #     for rec in self:
    #         rec.down_payment = 0.0
    #         sales_price = rec.price_after_discount
    #         if rec.installment_template_id and rec.installment_template_id.contracting_percentage:
    #             rec.down_payment = (rec.installment_template_id.contracting_percentage / 100) * sales_price
    #         elif rec.unit_id.has_discount:
    #             down_payment_percentage = rec.unit_id.effective_down_payment
    #             if down_payment_percentage and sales_price:
    #                 rec.down_payment = (down_payment_percentage / 100) * sales_price
    #         elif rec.payment_plan_line_id and sales_price:
    #             down_payment_percentage = rec.payment_plan_line_id.down_payment
    #             if down_payment_percentage:
    #                 rec.down_payment = (down_payment_percentage / 100) * sales_price

    @api.depends('unit_id', 'contracted_build_up_area', 'contracted_terrace_area', 'contracted_outdoor_area')
    def _compute_contracted_total_area(self):
        for rec in self:
            rec.contracted_total_area = (
                    rec.contracted_build_up_area +
                    rec.contracted_terrace_area +
                    rec.contracted_outdoor_area
            )

    @api.onchange('unit_id')
    def _onchange_unit_id_contracted_outdoor(self):
        if self.unit_id and self.unit_id.outdoor_gross_area:
            self.contracted_outdoor_area = self.unit_id.outdoor_gross_area

    @api.depends('installment_template_id', 'installment_template_id.reservation_percentage',
                 'contracted_selling_price', 'apply_discount_on_down_payment', 'price_after_discount',
                 'installment_template_2_id', 'installment_template_2_id.reservation_percentage')
    def _compute_installment_template_amounts(self):
        for rec in self:
            amount = rec.price_after_discount if rec.apply_discount_on_down_payment else rec.contracted_selling_price
            if rec.installment_template_id:
                if rec.installment_template_id.reservation_percentage:
                    rec.down_payment = (rec.installment_template_id.reservation_percentage / 100) * amount if rec.installment_template_id.reservation_percentage else 0.0
            elif rec.installment_template_2_id:
                if rec.installment_template_2_id.reservation_percentage:
                    rec.down_payment = (rec.installment_template_2_id.reservation_percentage / 100) * amount if rec.installment_template_2_id.reservation_percentage else 0.0
            else:
                rec.down_payment = 0

    @api.depends('unit_price', 'sale_contract_reservation_id',
                 'sale_contract_reservation_id.contracted_selling_price')
    def _compute_contracted_selling_price(self):
        for rec in self:
            # When the contract originates from a reservation, mirror the
            # reservation's contracted selling price; otherwise fall back to the
            # unit price (contracts created directly).
            if rec.sale_contract_reservation_id:
                rec.contracted_selling_price = rec.sale_contract_reservation_id.contracted_selling_price
            else:
                rec.contracted_selling_price = rec.unit_price

    def _inverse_contracted_selling_price(self):
        sellable_states = ('available', 'available_for_sale')
        for rec in self:
            if rec.unit_id and rec.unit_id.unit_status not in sellable_states:
                continue
            rec.unit_price = rec.contracted_selling_price

    @api.depends('sale_contract_reservation_id')
    def _compute_sale_reservation_count(self):
        for rec in self:
            rec.sale_reservation_count = 1 if rec.sale_contract_reservation_id else 0

    # Add booking amount field
    booking_amount = fields.Float(compute='_compute_booking_amount')
    booking_amount_words = fields.Char(compute='_compute_booking_amount', store=True)

    @api.depends('eoi_amount', 'reservation_payment')
    def _compute_booking_amount(self):
        for rec in self:
            rec.booking_amount = rec.eoi_amount + rec.reservation_payment
            if rec.booking_amount:
                rec.booking_amount_words = num2words(rec.booking_amount,lang='ar', to='currency',
                                            currency='EGP')
            else:
                rec.booking_amount_words = False

    def action_view_sale_reservation(self):
        """Smart button to view sale reservation"""
        self.ensure_one()

        if not self.sale_contract_reservation_id:
            raise UserError(_("No reservation has been created for this contract."))

        return {
            'name': _('Sale Reservation'),
            'type': 'ir.actions.act_window',
            'res_model': 'real.estate.sale.reservation',
            'view_mode': 'form',
            'res_id': self.sale_contract_reservation_id.id,
            'target': 'current',
        }

    def _create_client_sign_collection_entry(self):
        """Create draft collection journal entry when signed by client"""
        self.ensure_one()

        # Skip if already created
        if self.client_sign_collection_move_id:
            return None

        # Get configuration parameters
        Parameters = self.env['ir.config_parameter'].sudo()

        debit_account_id = Parameters.get_param('arkzayed_18_realestate_development.collection_debit_account_id')
        credit_gis_account_id = Parameters.get_param('arkzayed_18_realestate_development.collection_credit_gis_account_id')
        credit_oaya_account_id = Parameters.get_param('arkzayed_18_realestate_development.collection_credit_oaya_account_id')
        gis_percentage = float(Parameters.get_param('arkzayed_18_realestate_development.collection_gis_percentage') or 0)
        oaya_percentage = float(Parameters.get_param('arkzayed_18_realestate_development.collection_oaya_percentage') or 0)
        journal_id = Parameters.get_param('arkzayed_18_realestate_development.collection_journal_id')

        # Validate configuration
        if not all([debit_account_id, credit_gis_account_id, credit_oaya_account_id, journal_id]):
            raise ValidationError(_(
                "Please configure collection accounts and journal in Accounting Configuration:\n"
                "- Collection Debit Account\n"
                "- Collection Credit Account - GIS\n"
                "- Collection Credit Account - OAYA\n"
                "- Collection Journal"
            ))

        # Calculate total amount from EOI + Reservation
        total_amount = (self.eoi_amount or 0.0) + (self.reservation_payment or 0.0)

        # Skip if no amount
        if total_amount <= 0:
            return None

        # Calculate amounts based on configured percentages
        gis_amount = round((total_amount * gis_percentage) / 100, 2)
        oaya_amount = round((total_amount * oaya_percentage) / 100, 2)

        # Total credit is sum of GIS + OAYA
        total_credit = gis_amount + oaya_amount

        # Debit amount matches the total credit to balance the entry
        debit_amount = total_credit

        line_ids = []

        # Debit line - Collection Expense
        line_ids.append((0, 0, {
            'name': _('Collection Expense - %s (EOI + Reservation)') % self.name,
            'account_id': int(debit_account_id),
            'partner_id': self.customer_id.id,
            'debit': debit_amount,
            'credit': 0.0,
            'analytic_distribution': {self.analytic_account_id.id: 100} if self.analytic_account_id else False,
        }))

        # Credit line 1 - GIS
        if gis_amount > 0:
            line_ids.append((0, 0, {
                'name': _('GIS Collection (%.2f%%) - %s') % (gis_percentage, self.name),
                'account_id': int(credit_gis_account_id),
                'partner_id': self.customer_id.id,
                'debit': 0.0,
                'credit': gis_amount,
                'analytic_distribution': {self.analytic_account_id.id: 100} if self.analytic_account_id else False,
            }))

        # Credit line 2 - OAYA
        if oaya_amount > 0:
            line_ids.append((0, 0, {
                'name': _('OAYA Collection (%.2f%%) - %s') % (oaya_percentage, self.name),
                'account_id': int(credit_oaya_account_id),
                'partner_id': self.customer_id.id,
                'debit': 0.0,
                'credit': oaya_amount,
                'analytic_distribution': {self.analytic_account_id.id: 100} if self.analytic_account_id else False,
            }))

        # Create draft journal entry
        move_vals = {
            'journal_id': int(journal_id),
            'date': fields.Date.today(),
            'ref': _('Collection - %s (EOI: %s + Reservation: %s)') % (
                self.name,
                self.currency_id.symbol + ' ' + str(self.eoi_amount or 0),
                self.currency_id.symbol + ' ' + str(self.reservation_payment or 0)
            ),
            'line_ids': line_ids,
            'is_revenue_split_entry': True,
        }

        move = self.env['account.move'].create(move_vals)
        self.client_sign_collection_move_id = move.id

        return move

    @api.depends('client_sign_collection_move_id')
    def _compute_client_sign_collection_count(self):
        for rec in self:
            rec.client_sign_collection_count = 1 if rec.client_sign_collection_move_id else 0

    def action_view_client_sign_collection_entry(self):
        """Smart button to view client signature collection entry"""
        self.ensure_one()
        if not self.client_sign_collection_move_id:
            raise UserError(_("No collection journal entry has been created yet."))

        return {
            'name': _('Collection Journal Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.client_sign_collection_move_id.id,
            'target': 'current',
        }

    @api.depends('delivery_move_id')
    def _compute_journal_entry_count(self):
        for rec in self:
            rec.journal_entry_count = 1 if rec.delivery_move_id else 0

    @api.depends('ownership_change_journal_id')
    def _compute_ownership_change_journal_count(self):
        for rec in self:
            rec.ownership_change_journal_count = 1 if rec.ownership_change_journal_id else 0

    def action_view_ownership_change_journal(self):
        """Smart button to view ownership change journal entry"""
        self.ensure_one()
        if not self.ownership_change_journal_id:
            raise UserError(_("No ownership change journal entry has been created yet."))

        return {
            'name': _('Ownership Change Journal Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.ownership_change_journal_id.id,
            'target': 'current',
        }

    def action_view_journal_entries(self):
        """Smart button to view delivery journal entry"""
        self.ensure_one()
        if not self.delivery_move_id:
            raise UserError(_("No journal entry has been created yet."))

        return {
            'name': _('Delivery Journal Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.delivery_move_id.id,
            'target': 'current',
        }

    def _create_delivery_journal_entry(self):
        """Create journal entry when contract is delivered"""
        self.ensure_one()

        # Get configuration parameters
        ICP = self.env['ir.config_parameter'].sudo()
        maintenance_account_id = ICP.get_param(
            "arkzayed_18_realestate_development.maintenance_account_id")

        # Get deferred revenue account based on contract type
        if self.contract_type == 'overseas':
            deferred_revenue_account_id = ICP.get_param(
                'arkzayed_18_realestate_development.deferred_revenue_overseas_account')
            deferred_revenue_account = self.env['account.account'].browse(int(deferred_revenue_account_id)) if deferred_revenue_account_id else None
        else:
            deferred_revenue_account = self.company_id.deferred_revenue_account_id

        # Validate configuration
        if not maintenance_account_id:
            raise ValidationError(_("Please configure Maintenance Account in Accounting Configuration."))
        if not deferred_revenue_account:
            if self.contract_type == 'overseas':
                raise ValidationError(
                    _("Please configure Deferred Revenue for Overseas Account in Accounting → Configuration → Settings."))
            else:
                raise ValidationError(
                    _("Please configure Deferred Revenue Account in Accounting → Configuration → Settings."))

        # Validate customer accounts
        if not self.customer_id.property_account_receivable_id:
            raise ValidationError(_("Customer must have an Account Receivable configured."))
        if not self.customer_id.property_account_down_payment_receivable_id:
            raise ValidationError(_("Customer must have an Account Down Payment Receivable configured."))

        # Get sales journal (standard journal for sales)
        sales_journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        if not sales_journal:
            raise ValidationError(_("Please configure a Sales Journal."))

        # Prepare journal entry lines
        line_ids = []

        # Calculate amounts
        down_payment = self.down_payment
        receivable_amount = self.contract_amount - down_payment

        # Line 1: Debit - Account Receivable
        line_ids.append((0, 0, {
            'name': _('Contract Receivable - %s') % self.name,
            'account_id': self.customer_id.property_account_receivable_id.id,
            'partner_id': self.customer_id.id,
            'debit': receivable_amount,
            'credit': 0.0,
            'analytic_distribution': {self.analytic_account_id.id: 100} if self.analytic_account_id else False,
        }))

        # Line 2: Debit - Down Payment Receivable (only if down_payment > 0)
        if down_payment > 0:
            line_ids.append((0, 0, {
                'name': _('EOI & Reservation - %s') % self.name,
                'account_id': self.customer_id.property_account_down_payment_receivable_id.id,
                'partner_id': self.customer_id.id,
                'debit': down_payment,
                'credit': 0.0,
                'analytic_distribution': {self.analytic_account_id.id: 100} if self.analytic_account_id else False,
            }))

        # Line 3: Credit - Maintenance Account
        if self.maintenance_price > 0:
            line_ids.append((0, 0, {
                'name': _('Maintenance Revenue - %s') % self.name,
                'account_id': int(maintenance_account_id),
                'partner_id': self.customer_id.id,
                'debit': 0.0,
                'credit': self.maintenance_price,
                'analytic_distribution': {self.analytic_account_id.id: 100} if self.analytic_account_id else False,
            }))

        # Line 4: Credit - Deferred Revenue Account (from Odoo standard)
        line_ids.append((0, 0, {
            'name': _('Unit Deferred Revenue - %s') % self.name,
            'account_id': deferred_revenue_account.id,
            'partner_id': self.customer_id.id,
            'debit': 0.0,
            'credit': self.price_after_discount,
            'analytic_distribution': {self.analytic_account_id.id: 100} if self.analytic_account_id else False,
        }))

        # Create journal entry
        move_vals = {
            'journal_id': sales_journal.id,
            'date': fields.Date.today(),
            'ref': self.name,
            'line_ids': line_ids,
        }

        move = self.env['account.move'].create(move_vals)
        self.delivery_move_id = move.id

        # Post the journal entry
        move.action_post()

        return move

    @api.depends('contract_delivery_period', 'contract_issue_date')
    def _compute_expected_delivery_date(self):
        for rec in self:
            if rec.contract_issue_date and rec.contract_delivery_period:
                # contract_delivery_period is a float number of years; relativedelta
                # only accepts integer years/months, so split it into years + months + days.
                whole_years = int(rec.contract_delivery_period)
                rem_months = (rec.contract_delivery_period - whole_years) * 12
                whole_months = int(rem_months)
                rem_days = int(round((rem_months - whole_months) * 30))
                rec.expected_delivery_date = rec.contract_issue_date + relativedelta(
                    years=whole_years, months=whole_months, days=rem_days
                )
            else:
                rec.expected_delivery_date = False

    @api.depends('expected_delivery_date', 'allowance_period')
    def _compute_expected_after_allowance(self):
        for rec in self:
            if rec.expected_delivery_date and rec.allowance_period:
                rec.expected_after_allowance = rec.expected_delivery_date + relativedelta(
                    years=rec.allowance_period
                )
            else:
                rec.expected_after_allowance = False

    @api.depends('expected_after_allowance', 'extra_period')
    def _compute_extra_period_date(self):
        for rec in self:
            if rec.expected_after_allowance and rec.extra_period:
                rec.extra_period_date = rec.expected_after_allowance + relativedelta(
                    years=rec.extra_period
                )
            else:
                rec.extra_period_date = False


    @api.depends('delivery_invoice_id')
    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = 1 if rec.delivery_invoice_id else 0

    def action_view_invoices(self):
        """Smart button to view delivery invoice"""
        self.ensure_one()
        if not self.delivery_invoice_id:
            raise UserError(_("No invoice has been created yet."))

        return {
            'name': _('Delivery Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.delivery_invoice_id.id,
            'target': 'current',
        }

    def _create_delivery_invoice(self):
        """Create invoice when contract is delivered"""
        self.ensure_one()

        # Find product with is_unit = True
        unit_product = self.env['product.template'].search([('is_unit', '=', True)], limit=1)
        if not unit_product:
            raise ValidationError(_("Please configure a product with 'Is Unit' checked in the system."))

        # Get INCOME account from product (not expense)
        accounts = unit_product.get_product_accounts()
        income_account = accounts.get('income')
        if not income_account:
            raise ValidationError(_("The unit product must have an Income account configured."))

        # Get Odoo's standard deferred revenue account from company settings
        deferred_revenue_account = self.company_id.deferred_revenue_account_id
        if not deferred_revenue_account:
            raise ValidationError(
                _("Please configure Deferred Revenue Account in Accounting → Configuration → Settings."))

        # Get sales journal
        sales_journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        if not sales_journal:
            raise ValidationError(_("Please configure a Sales Journal."))

        # Prepare invoice line - this will create the credit side
        invoice_line_vals = {
            'product_id': unit_product.id,
            'name': _('Unit: %s - %s') % (self.unit_number or '', self.name),
            'quantity': 1,
            'price_unit': self.price_after_discount,
            'account_id': income_account.id,  # Credit side = Income Account from product
            'tax_ids': [(5, 0, 0)],  # Remove all taxes (clear taxes)
            'analytic_distribution': {self.analytic_account_id.id: 100} if self.analytic_account_id else False,
        }

        # Create invoice with is_contract flag
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.customer_id.id,
            'invoice_date': fields.Date.today(),
            'journal_id': sales_journal.id,
            'currency_id': self.currency_id.id,
            'is_contract': True,  # Mark as contract invoice - this skips the validation
            'sale_proposal_id': self.id,
            'invoice_line_ids': [(0, 0, invoice_line_vals)],
        }

        # Create invoice
        invoice = self.env['account.move'].create(invoice_vals)

        # Replace the auto-created receivable line with deferred revenue
        for line in invoice.line_ids:
            if line.account_id.account_type == 'asset_receivable':
                line.with_context(check_move_validity=False).write({
                    'account_id': deferred_revenue_account.id,
                })

        # Store reference
        self.delivery_invoice_id = invoice.id

        return invoice
    
    def action_reallocate_unit(self):
        self.ensure_one()
        if not self.unit_id:
            raise UserError(_("No unit is currently assigned to this contract."))
        return {
            'name': _('Reallocate Unit'),
            'type': 'ir.actions.act_window',
            'res_model': 'contract.reallocate.unit.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_contract_id': self.id,
                'default_old_unit_id': self.unit_id.id,
            }
        }

    def action_create_draft_contract(self):
        """Move from Draft Proposal to Draft Contract"""
        self.ensure_one()

        if not self.unit_id:
            raise ValidationError(_("Please Select Unit"))

        # Create analytic account
        sale_plan = self.env['account.analytic.plan'].search([('is_sale', '=', True)])
        if sale_plan:
            analytic_account = self.env['account.analytic.account'].create({
                'name': self.name,
                'plan_id': sale_plan.id,
            })
            self.analytic_account_id = analytic_account.id
        else:
            raise ValidationError(_("No plan with the Sale flag set to True found."))

        self.state = 'pending_approvals'
        self.unit_id.unit_status = 'reserved'

    def action_sent_to_client(self):
        self.ensure_one()

        if self.contract_type != 'overseas':
            raise UserError(_('Contract type is not supported.'))

        self.state = 'sent_to_client'

    def action_operation_manager_approve(self):
        """Move from Pending Approvals to Approved"""
        self.ensure_one()

        # Validate that both approvals are checked
        if not self.finance_user_approve:
            raise ValidationError(_("Finance approval is required before proceeding."))

        if not self.finance_approve:
            raise ValidationError(_("Finance Two approval is required before proceeding."))

        if not self.manager_approve:
            raise ValidationError(_("Manager approval is required before proceeding."))

        self.state = 'approved'

    def action_sign_by_client(self):
        """Client signs the contract - makes all fields readonly"""
        self.ensure_one()

        if self.contract_type in ['domestic', 'overseas']:
            if not self.delivery_move_id and not self.is_old_contract:
                self._create_delivery_journal_entry()

        # Create collection entry for EOI + Reservation (skip for old contracts)
        collection_entry_created = False
        if not self.client_sign_collection_move_id and not self.is_old_contract:
            try:
                self._create_client_sign_collection_entry()
                collection_entry_created = True
            except Exception as e:
                # Post warning to chatter if collection entry fails
                self.message_post(
                    body=_("⚠️ Collection entry could not be created: %s") % str(e),
                    message_type='comment'
                )

        # Update state and signature info
        self.write({
            'state': 'signed_client',
            'signed_by_client': True,
            'client_signature_date': fields.Date.today(),
        })

        # Update reservation contract date
        if self.sale_contract_reservation_id:
            self.sale_contract_reservation_id.write({
                'contract_date': fields.Date.today(),
            })

        # Automatically check and create broker claim when signed by client
        if self.referred_by == 'broker':
            self._check_and_create_broker_claim()
        self._check_and_create_non_sales_claims()

    def action_review_by_operation(self):
        self.write({
            'state': 'operation_review'
        })

    def action_review_by_finance(self):
        self.write({
            'state':'finance_review'
        })

    def action_top_management(self):
        self.write({
            'state':'top_management'
        })

    def action_sign_by_ceo(self):
        """CEO signs the contract"""
        self.ensure_one()

        if not self.signed_by_client:
            raise ValidationError(_("Contract must be signed by client first."))

        # Validate customer information
        if self.customer_id.company_type == 'person':
            if not self.customer_id.passport_number and not self.customer_id.national_id:
                raise ValidationError(_("You should enter passport No or National ID."))
        elif self.customer_id.company_type == 'company':
            if not self.customer_id.cr:
                raise ValidationError(_("You should enter CR No."))
            if not self.customer_id.vat:
                raise ValidationError(_("You should enter Tax ID."))

        self.write({
            'state': 'signed_ceo',
            'signed_by_ceo': True,
            'ceo_signature_date': fields.Date.today(),
        })

    def action_ready_to_deliver_contract(self):
        self.ensure_one()

        if not self.signed_by_ceo:
            raise ValidationError(_("Contract must be signed by CEO first."))

        self.state = 'ready_to_deliver_contract'

    def action_deliver_contract(self):
        self.ensure_one()

        if self.state != 'ready_to_deliver_contract' and self.contract_type != 'overseas':
            raise ValidationError(_("Contract must be in 'Ready to Deliver Contract' state."))
        if self.state != 'sent_to_client' and self.contract_type == 'overseas':
            raise ValidationError(_("Contract must be in 'Sent To Client' state."))

        self.state = 'delivered_contract'

    def action_ready_to_deliver(self):
        """Mark contract as ready for delivery"""
        self.ensure_one()

        if not self.signed_by_ceo:
            raise ValidationError(_("Contract must be signed by CEO first."))

        # Create journal entry
        # if not self.delivery_move_id:
        #     self._create_delivery_journal_entry()

        self.state = 'ready_to_deliver'

    def action_deliver(self):
        """Deliver the unit, create journal entry and invoice"""
        self.ensure_one()

        if self.state != 'ready_to_deliver':
            raise ValidationError(_("Contract must be in 'Ready to Deliver' state."))

        # Create contract invoice
        if not self.delivery_invoice_id:
            self._create_delivery_invoice()

        self.state = 'delivered'
        self.unit_id.unit_status = 'delivered'

    def action_cancel_contract(self):
        """Cancel contract at any stage"""
        self.ensure_one()

        return {
            'name': _('Cancel Contract'),
            'type': 'ir.actions.act_window',
            'res_model': 'contract.cancellation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_proposal_id': self.id,
            }
        }

    def action_reset_to_draft(self):
        """Reset cancelled contract back to draft"""
        self.ensure_one()

        if self.state != 'cancelled':
            raise ValidationError(_("Only cancelled contracts can be reset to draft."))

        self.write({
            'state': 'draft',
            'signed_by_client': False,
            'signed_by_ceo': False,
            'client_signature_date': False,
            'ceo_signature_date': False,
            'cancellation_reason': False,
            'cancelled_date': False,
            'cancelled_by': False,
        })

        if self.unit_id:
            self.unit_id.unit_status = 'available'

    @api.depends('down_payment', 'eoi_amount', 'reservation_payment')
    def _compute_down_payment_remaining(self):
        for rec in self:
            rec.down_payment_remaining = rec.down_payment - (rec.eoi_amount + rec.reservation_payment)

    # _compute_linked_cheque_ids() and _compute_cheque_count() moved to
    # isky_18_realestate_developer_sales_cheques (Phase 3 step 3).

    # action_create_cheques(), action_open_combined_cheque_wizard(), _generate_cheques()
    # and action_view_cheques() moved to isky_18_realestate_developer_sales_cheques
    # (Phase 3 step 3).

    def action_view_payments(self):
        """View payments related to this proposal (own + multi-contract linked)."""
        self.ensure_one()
        return {
            'name': _('Payments'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', (self.payment_ids | self.linked_payment_ids).ids)],
            'context': {
                'default_sale_proposal_id': self.id,
            }
        }


    @api.onchange('customer_id')
    def customer_onchange(self):
        if self.customer_id:
            self.brand_name = self.customer_id.ref

    @api.onchange('unit_id')
    def unit_id_on_change(self):
        if self.unit_id:
            if self.unit_id.warning_msg:
                msg = self.unit_id.warning_msg
                raise ValidationError(msg)

    @api.depends('unit_id', 'unit_id.has_parking', 'unit_id.number_of_slots')
    def _compute_parking_from_apartment_type(self):
        for rec in self:
            if rec.unit_id and rec.unit_id.has_parking and rec.unit_id.number_of_slots > 0:
                rec.include_free_parking = True
                rec.slots = 'number of slots'
                rec.number_of_slots = rec.unit_id.number_of_slots
            else:
                rec.include_free_parking = False
                rec.slots = False
                rec.number_of_slots = 0

    @api.depends('price_after_discount', 'maintenance_price')
    def compute_contract_amount(self):
        for rec in self:
            rec.contract_amount = (rec.price_after_discount or 0) + (rec.maintenance_price or 0)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('sale.proposal') or _('New')

        proposal = super().create(vals)

        if proposal.referred_by == 'broker':
            proposal._check_and_create_broker_claim()
        proposal._check_and_create_non_sales_claims()

        if proposal.user_id:
            proposal._build_commission_hierarchy()

        return proposal

    def write(self, vals):
        """Override write to check broker claim and commission achievements when amounts change"""
        if 'finance_user_approve' in vals and not self.env.user.has_group(
                'isky_18_realestate_developer_sales_crm.group_finance_approval'):
            raise UserError(_("Only users in the 'Finance Approval' group can change the Finance Approval."))
        if 'finance_approve' in vals and not self.env.user.has_group(
                'isky_18_realestate_developer_sales_crm.group_finance_two_approval'):
            raise UserError(_("Only users in the 'Finance Two Approval' group can change the Finance Two Approval."))
        if 'manager_approve' in vals and not self.env.user.has_group(
                'isky_18_realestate_developer_sales_crm.group_manager_approval'):
            raise UserError(_("Only users in the 'Manager Approval' group can change the Manager Approval."))
        # if the contracted_selling_price was updated or changed just edit its value inside the unit
        if 'contracted_selling_price' in vals:
            self.unit_id.contracted_selling_price = vals['contracted_selling_price']

        commission_fields = {'user_id', 'sales_ids', 'split_deal'}
        if commission_fields.intersection(vals.keys()):
            for rec in self:
                rec._build_commission_hierarchy()

        # --- NEW: Trigger Recalculate Flags ---
        installment_triggers = [
            'price_after_discount', 'contracted_selling_price', 'discount_percentage',
            'installment_template_id', 'installment_template_2_id',
            'down_payment', 'delivery_payment', 'post_contract_price',
            'monthly_installment_start_date', 'quarterly_installment_start_date',
            'semi_annual_installment_start_date', 'annual_installment_start_date'
        ]
        maintenance_triggers = [
            'maintenance_price', 'maintenance_template_id', 'maintenance',
            'maintenance_price_method', 'maintenance_percentage',
            'monthly_maintenance_start_date', 'quarterly_maintenance_start_date',
            'semi_annual_maintenance_start_date', 'annual_maintenance_start_date'
        ]

        if any(field in vals for field in installment_triggers):
            vals['force_recalculate_installments'] = True

        if any(field in vals for field in maintenance_triggers):
            vals['force_recalculate_maintenance'] = True

        result = super(SaleProposal, self).write(vals)

        # Once the contract is signed by the client, the unit is sold.
        if vals.get('state') == 'signed_client':
            for rec in self:
                if rec.unit_id:
                    rec.unit_id.unit_status = 'sold'

        # Trigger fields for broker claim
        broker_trigger_fields = ['eoi_amount', 'reservation_payment', 'price_after_discount', 'referred_by',
                                 'referred_by_partner_id', 'broker_contract_id']

        if any(field in vals for field in broker_trigger_fields):
            for record in self:
                if record.referred_by == 'broker':
                    record._check_and_create_broker_claim()
                record._check_and_create_non_sales_claims()

        return result

    @api.onchange('maintenance_price_method', 'maintenance_percentage', 'price_after_discount','price_after_discount')
    def calc_maintenance_price(self):
        for rec in self:
            if rec.maintenance_price_method == 'percentage':
                rec.maintenance_price = rec.maintenance_percentage * rec.unit_price / 100
            elif rec.maintenance_price_method == 'discount':
                rec.maintenance_price = rec.maintenance_percentage * rec.price_after_discount / 100
            elif rec.maintenance_price_method == 'fixed_amount':
                rec.maintenance_price = self.env['maintenance.config'].get_config().maintenance_amount_default

    @api.depends('maintenance_price', 'maintenance_1st_year_advance_percentage')
    def _compute_maintenance_1st_year_advance(self):
        for rec in self:
            rec.maintenance_1st_year_advance = (
                                                           rec.maintenance_1st_year_advance_percentage / 100) * rec.maintenance_price

    @api.depends('maintenance_1st_year_advance', 'maintenance_vat_id', 'maintenance_vat_id.amount')
    def _compute_maintenance_vat(self):
        for rec in self:
            rec.maintenance_vat = (rec.maintenance_vat_id.amount / 100) * rec.maintenance_1st_year_advance

    @api.depends('total_unit_selling_price', 'unit_vat_id.amount')
    def _compute_unit_vat(self):
        for rec in self:
            rec.unit_vat = (rec.unit_vat_id.amount / 100) * rec.total_unit_selling_price

    @api.depends('total_unit_selling_price', 'maintenance_price')
    def _compute_total_unit_price_incl_maintenance(self):
        for rec in self:
            rec.total_unit_price_incl_maintenance = rec.total_unit_selling_price + rec.maintenance_price

    @api.onchange('reservation_payment_date')
    def _onchange_reservation_payment_date(self):
        for rec in self:
            if rec.reservation_payment_date:
                rec.post_contract_date = rec.down_payment_date = rec.reservation_payment_date + relativedelta(months=3)

    def action_calculate_maintenance(self):
        """Calculate maintenance installments for contract with cleanup and automated fund re-allocation"""
        if not self._installments_allowed():
            return self._installments_off_notification()

        if self.state not in ['draft', 'pending_approvals']:
            raise ValidationError(_("Maintenance can only be calculated in Draft or Draft Contract state."))

        paid_maint_lines = self.maintenance_installment_ids.filtered('paid')
        if paid_maint_lines:
            raise UserError(_(
                "Cannot recalculate: %(count)d maintenance line(s) already have payments allocated. "
                "Paid lines cannot be regenerated. Adjust the remaining unpaid lines manually, or "
                "contact support to restructure this schedule.",
                count=len(paid_maint_lines),
            ))

        # Sync maintenance parameters to reservation
        if self.sale_contract_reservation_id:
            self.sale_contract_reservation_id.write({
                'maintenance': self.maintenance,
                'maintenance_template_id': self.maintenance_template_id.id if self.maintenance_template_id else False,
                'maintenance_price_method': self.maintenance_price_method,
                'maintenance_percentage': self.maintenance_percentage,
                'maintenance_price': self.maintenance_price,
                'monthly_maintenance_start_date': self.monthly_maintenance_start_date,
                'quarterly_maintenance_start_date': self.quarterly_maintenance_start_date,
                'semi_annual_maintenance_start_date': self.semi_annual_maintenance_start_date,
                'annual_maintenance_start_date': self.annual_maintenance_start_date,
            })

        if self.maintenance and (self.maintenance_price > 0.0 or self.contract_amount > 0.00):
            self.maintenance_installment_ids = self._prepare_lines()

            if self.maintenance_installment_ids:
                self._force_lines_to_match_total(
                    self.maintenance_installment_ids, self.maintenance_price, label=_('Maintenance')
                )

            self.force_recalculate_maintenance = False

            if self.maintenance_installment_ids:
                sorted_maint = self.maintenance_installment_ids.sorted(key=lambda l: l.date)
                maint_counter = 1
                for line in sorted_maint:
                    line.serial = maint_counter
                    maint_counter += 1

    def _prepare_installment_lines(self):
        # Step 5: gate before the clearing assignment, so nothing existing is destroyed.
        if not self._installments_allowed():
            return []
        self.installment_ids = None
        installment_lines = []
        ind = 1
        # Updated calculation using down_payment_remaining
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

            # Process First Installment Template
            if self.installment_template_id:
                installment_lines, ind = self._process_template(
                    self.installment_template_id,
                    total_installment_amount,
                    installment_lines,
                    ind,
                    template_number=1,
                    scale_factor=scale_factor
                )

            # Process Second Installment Template
            if self.installment_template_2_id:
                installment_lines, ind = self._process_template(
                    self.installment_template_2_id,
                    total_installment_amount,
                    installment_lines,
                    ind,
                    template_number=2,
                    scale_factor=scale_factor
                )

        installment_lines = self.get_other_payment_data(installment_lines, ind)
        res_id = self.sale_contract_reservation_id.id if self.sale_contract_reservation_id else False
        # Ensure EVERY line dictionary contains BOTH proposal and reservation IDs
        for line_command in installment_lines:
            if line_command[0] == 0:  # Command.create
                line_command[2]['sale_proposal_id'] = self.id
                if res_id:
                    line_command[2]['reservation_id'] = res_id
        return installment_lines

    def _process_template(self, template, total_installment_amount, installment_lines, ind, template_number=1, scale_factor=1):
        """Process installment template and return updated lines and index"""

        # Determine which start dates to use based on template number
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
            installment_monthly_duration = template.monthly_installment_duration
            installment_monthly_amount = template.monthly_installment_amount
            pricing = installment_monthly_amount * total_installment_amount  * scale_factor
            mon = installment_monthly_duration
            date_payment = monthly_start

            if not date_payment:
                raise UserError(
                    _("Please select first monthly installment start date for template %s!") % template_number)



            installment_amount = (pricing / float(mon or 1))
            m = 0
            while m < mon:
                installment_lines.append((0, 0, {
                    "name": _("Monthly Installment") + template_label,
                    "serial": ind,
                    "amount": installment_amount,
                    "date": date_payment,
                    "vat_id": self.unit_vat_id.id,
                }))
                ind += 1
                date_payment = add_months(date_payment, int(1))
                m += 1

        # Quarterly Installments
        if template.quarterly_installment_amount > 0:
            installment_quarterly_duration = template.quarterly_installment_duration
            installment_quarterly_amount = template.quarterly_installment_amount
            pricing = installment_quarterly_amount * total_installment_amount * scale_factor
            mon = installment_quarterly_duration
            repetition = 3
            date_payment = quarterly_start

            if not date_payment:
                raise UserError(
                    _("Please select first quarterly installment start date for template %s!") % template_number)



            installment_amount = (pricing / float(mon or 1))
            m = 0
            while m < mon:
                installment_lines.append((0, 0, {
                    "name": _("Quarterly Installment") + template_label,
                    "serial": ind,
                    "amount": installment_amount,
                    "date": date_payment,
                    "vat_id": self.unit_vat_id.id,
                }))
                ind += 1
                date_payment = add_months(date_payment, int(repetition))
                m += 1

        # Semi Annual Installments
        if template.semi_annual_installment_amount > 0:
            installment_semi_annual_duration = template.semi_annual_installment_duration
            installment_semi_annual_amount = template.semi_annual_installment_amount
            pricing = installment_semi_annual_amount * total_installment_amount * scale_factor
            mon = installment_semi_annual_duration
            repetition = 6
            date_payment = semi_annual_start

            if not date_payment:
                raise UserError(
                    _("Please select first semi-annual installment start date for template %s!") % template_number)



            installment_amount = (pricing / float(mon or 1))
            m = 0
            while m < mon:
                installment_lines.append((0, 0, {
                    "name": _("Semi Annual Installment") + template_label,
                    "serial": ind,
                    "amount": installment_amount,
                    "date": date_payment,
                    "vat_id": self.unit_vat_id.id,
                }))
                ind += 1
                date_payment = add_months(date_payment, int(repetition))
                m += 1

        # Annual Installments
        if template.annual_installment_amount > 0:
            installment_annual_duration = template.annual_installment_duration
            installment_annual_amount = template.annual_installment_amount
            pricing = installment_annual_amount * total_installment_amount * scale_factor
            mon = installment_annual_duration
            repetition = 12
            date_payment = annual_start

            if not date_payment:
                raise UserError(
                    _("Please select first annual installment start date for template %s!") % template_number)



            installment_amount = (pricing / float(mon or 1))
            m = 0
            while m < mon:
                installment_lines.append((0, 0, {
                    "name": _("Annual Installment") + template_label,
                    "serial": ind,
                    "amount": installment_amount,
                    "date": date_payment,
                    "vat_id": self.unit_vat_id.id,
                }))
                ind += 1
                date_payment = add_months(date_payment, int(repetition))
                m += 1

        return installment_lines, ind

    def _prepare_lines(self):
        if not self._installments_allowed():
            return []
        self.maintenance_installment_ids = None
        maintenance_lines = []
        if self.maintenance_template_id:
            if self.maintenance_template_id.monthly_installment_amount > 0:
                maintenance_monthly_duration = self.maintenance_template_id.monthly_installment_duration
                maintenance_monthly_amount = self.maintenance_template_id.monthly_installment_amount
                ind = 1
                pricing = maintenance_monthly_amount * self.maintenance_price
                mon = maintenance_monthly_duration
                date_payment = self.monthly_maintenance_start_date
                if not self.monthly_maintenance_start_date:
                    raise UserError(_("Please select first monthly maintenance start_date date!"))


                installment_amount = (pricing / float(mon or 1))
                m = 0
                while m < mon:
                    maintenance_lines.append((0, 0, {
                        "name": _("Maintenance Installment"),
                        "serial": ind,
                        "amount": installment_amount,
                        "date": date_payment,
                        "vat_id": self.unit_vat_id.id,
                        "partner_id": self.customer_id.id,
                    }))
                    ind += 1
                    date_payment = add_months(date_payment, int(1))
                    m += 1
                ind += 1
            if self.maintenance_template_id.quarterly_installment_amount > 0:
                maintenance_quarterly_duration = self.maintenance_template_id.quarterly_installment_duration
                maintenance_quarterly_amount = self.maintenance_template_id.quarterly_installment_amount
                ind = 1
                pricing = maintenance_quarterly_amount * self.maintenance_price
                mon = maintenance_quarterly_duration
                repetition = 3
                date_payment = self.quarterly_maintenance_start_date
                if not date_payment:
                    raise UserError(_("Please select first monthly maintenance start_date date!"))

                installment_amount = (pricing / float(mon or 1))
                m = 0
                while m < mon:
                    maintenance_lines.append((0, 0, {
                        "name": _("Quarterly Maintenance Installment"),
                        "serial": ind,
                        "amount": installment_amount,
                        "date": date_payment,
                        "vat_id": self.unit_vat_id.id,
                        "partner_id": self.customer_id.id,
                    }))
                    ind += 1
                    date_payment = add_months(date_payment, int(repetition))
                    m += 1
                ind += 1
            if self.maintenance_template_id.semi_annual_installment_amount > 0:
                maintenance_semi_annual_duration = self.maintenance_template_id.semi_annual_installment_duration
                maintenance_semi_annual_amount = self.maintenance_template_id.semi_annual_installment_amount
                ind = 1
                pricing = maintenance_semi_annual_amount * self.maintenance_price
                mon = maintenance_semi_annual_duration
                repetition = 6
                date_payment = self.semi_annual_maintenance_start_date
                if not date_payment:
                    raise UserError(_("Please select Semi annual maintenance start date!"))


                installment_amount = (pricing / float(mon or 1))
                m = 0
                while m < mon:
                    maintenance_lines.append((0, 0, {
                        "name": _("Semi Annual Maintenance Installment"),
                        "serial": ind,
                        "amount": installment_amount,
                        "date": date_payment,
                        "vat_id": self.maintenance_vat_id.id,
                        "partner_id": self.customer_id.id,
                    }))
                    ind += 1
                    date_payment = add_months(date_payment, int(repetition))
                    m += 1
                ind += 1
            if self.maintenance_template_id.annual_installment_amount > 0:
                maintenance_annual_duration = self.maintenance_template_id.annual_installment_duration
                maintenance_annual_amount = self.maintenance_template_id.annual_installment_amount
                ind = 1
                pricing = maintenance_annual_amount * self.maintenance_price
                mon = maintenance_annual_duration
                repetition = 12
                date_payment = self.semi_annual_maintenance_start_date
                if not date_payment:
                    raise UserError(_("Please select Semi annual maintenance start date!"))


                installment_amount = (pricing / float(mon or 1))
                m = 0
                while m < mon:
                    maintenance_lines.append((0, 0, {
                        "name": _("Annual Maintenance Installment"),
                        "serial": ind,
                        "amount": installment_amount,
                        "date": date_payment,
                        "vat_id": self.maintenance_vat_id.id,
                        "partner_id": self.customer_id.id,
                    }))
                    ind += 1
                    date_payment = add_months(date_payment, int(repetition))
                    m += 1
                ind += 1
        res_id = self.sale_contract_reservation_id.id if self.sale_contract_reservation_id else False
        # Ensure EVERY maintenance line contains BOTH proposal and reservation IDs
        for line_command in maintenance_lines:
            if line_command[0] == 0:  # Command.create
                line_command[2]['sale_proposal_id'] = self.id
                if res_id:
                    line_command[2]['reservation_id'] = res_id
        return maintenance_lines

    def _snapshot_foreign_payment_allocations(self, line_type='installment'):
        """Capture how much each *foreign* payment/cheque currently holds on THIS
        contract's lines of the given type, before those lines (and their
        cascade-deleted allocations) are replaced by action_calculate.

        A foreign fund is one whose MAIN contract (sale_proposal_id) is a different
        contract: this contract is only an *additional* contract for it, so
        _reallocate_proposal_funds (which works off this contract's own payment_ids /
        cheque_ids) would otherwise drop its allocation.

        Returns {'payment': {payment_id: amount}, 'cheque': {cheque_id: amount}}.
        """
        self.ensure_one()
        lines = self.installment_ids if line_type == 'installment' else self.maintenance_installment_ids
        snapshot = {'payment': {}, 'cheque': {}}
        for line in lines:
            for alloc in line.allocation_ids:
                kind = alloc._fund_kind()
                if not kind:
                    continue
                rec = alloc._allocation_parent()
                bucket = snapshot[kind]
                if rec.sale_proposal_id and rec.sale_proposal_id != self:
                    bucket[rec.id] = bucket.get(rec.id, 0.0) + alloc.allocated_amount
        return snapshot

    # ----------------------------------------------------------------------------------
    # Cheque hooks (supplement S1, Phase 3 step 3). sales_cheques overrides each one.
    # ----------------------------------------------------------------------------------

    def _eoi_cheque_amount(self):
        """Incoming EOI cheques that still count toward the EOI amount."""
        return 0.0

    def _line_cheque_info(self, installment):
        """Report columns describing the cheque settling this line, if any."""
        return {'cheque_no': '', 'bank_name': '', 'has_cheque': False}

    def _cheque_fund_entries(self, foreign_chq_snap, line_type):
        """Fund-pool entries for the FIFO waterfall in _reallocate_proposal_funds():
        foreign cheques at priority 0, this contract's own cheques at priority 1. Same dict
        shape as the payment entries built there."""
        return []

    def _payment_amount_held_outside(self, fund, line_type):
        """Amount this payment/cheque currently holds on allocations that are NOT this
        contract's lines of the given type (i.e. this contract's other-type lines,
        plus any other contract's lines). Used to shrink the pool of a multi-contract
        fund so it is never allocated twice."""
        self.ensure_one()
        total = 0.0
        for alloc in fund.allocation_ids:
            line = alloc.installment_id or alloc.maintenance_id
            if not line:
                continue
            is_self_target = (line.sale_proposal_id == self) and (
                (line_type == 'installment' and alloc.installment_id)
                or (line_type == 'maintenance' and alloc.maintenance_id)
            )
            if not is_self_target:
                total += alloc.allocated_amount
        return total

    def _reallocate_proposal_funds(self, line_type='installment', foreign_snapshot=None):
        """
        FIFO Waterfall Re-allocation Engine for Contract:
        1. Unlinks old allocations for active payments and cheques.
        2. Spreads remaining active funds sequentially across newly generated lines.

        Multi-contract funds are handled safely:
        - ``foreign_snapshot`` ({'payment': {id: amount}, 'cheque': {id: amount}}) are
          payments/cheques whose main contract is another one; their amount on this
          contract's lines is re-created exactly.
        - For this contract's OWN payments/cheques, the available pool is the fund
          amount minus whatever that fund already holds on other contracts' lines, so
          it is never allocated twice.
        """
        self.ensure_one()
        foreign_snapshot = foreign_snapshot or {}
        foreign_pay_snap = foreign_snapshot.get('payment', {})
        foreign_chq_snap = foreign_snapshot.get('cheque', {})

        # Step 1: Identify Active / Confirmed Funds Pool
        active_payments = self.payment_ids.filtered(
            lambda p: p.payment_type == 'inbound' and p.state in (
                'to_check', 'cfo_approved', 'deputy_cfo_approved', 'in_process', 'paid'
            )
        )
        foreign_payments = self.env['account.payment'].browse(list(foreign_pay_snap.keys())).exists()

        # Both the foreign (priority 0) and the own (priority 1) cheque entries.
        cheque_funds = self._cheque_fund_entries(foreign_chq_snap, line_type)

        if not active_payments and not foreign_payments and not cheque_funds:
            return

        # Step 2: Clear old payment.allocation records for active funds & lines of this contract
        Allocation = self.env['payment.allocation'].with_context(skip_allocation_check=True)
        domain = [('installment_id.sale_proposal_id', '=', self.id)] if line_type == 'installment' else [
            ('maintenance_id.sale_proposal_id', '=', self.id)]

        old_allocations = Allocation.search(domain)
        if old_allocations:
            old_allocations.unlink()

        # Step 3: Build Funds Pool sorted chronologically by date.
        # Priority 0 = foreign funds (reclaim exactly the space they held),
        # priority 1 = this contract's own funds.
        fund_pool = []
        for p in foreign_payments:
            pool = foreign_pay_snap.get(p.id, 0.0)
            if pool <= 0.0001:
                continue
            fund_pool.append({
                'type': 'payment',
                'alloc_field': 'payment_id',
                'record': p,
                'date': p.date or fields.Date.today(),
                'remaining_pool': pool,
                'priority': 0,
            })

        for p in active_payments:
            pool = p.amount - self._payment_amount_held_outside(p, line_type)
            if pool <= 0.0001:
                continue
            fund_pool.append({
                'type': 'payment',
                'alloc_field': 'payment_id',
                'record': p,
                'date': p.date or fields.Date.today(),
                'remaining_pool': pool,
                'priority': 1,
            })

        fund_pool.extend(cheque_funds)

        fund_pool.sort(key=lambda x: (x['priority'], x['date'] is False, x['date']))

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
                method_used = fund['type']
                line.write({'payment_method_used': method_used})

    def action_calculate(self):
        """Calculate installments for contract with cleanup and automated fund re-allocation"""
        # Step 5: installments toggle. Returns a warning rather than raising.
        if not self._installments_allowed():
            return self._installments_off_notification()

        if self.state not in ['draft', 'pending_approvals']:
            raise ValidationError(_("Installments can only be calculated in Draft or Draft Contract state."))

        paid_lines = self.installment_ids.filtered('paid')
        if paid_lines:
            raise UserError(_(
                "Cannot recalculate: %(count)d installment line(s) already have payments allocated. "
                "Paid lines cannot be regenerated. Adjust the remaining unpaid lines manually, or "
                "contact support to restructure this schedule.",
                count=len(paid_lines),
            ))

        if self.sale_contract_reservation_id:
            self.sale_contract_reservation_id.write({
                'installment_template_id': self.installment_template_id.id,
                'monthly_installment_start_date': self.monthly_installment_start_date,
                'quarterly_installment_start_date': self.quarterly_installment_start_date,
                'semi_annual_installment_start_date': self.semi_annual_installment_start_date,
                'annual_installment_start_date': self.annual_installment_start_date,
            })

        if self.total_unit_selling_price > 0.0 or self.contract_amount > 0.00:
            # Capture multi-contract payments' hold on this contract's lines BEFORE
            # the lines (and their cascade-deleted allocations) are replaced.
            foreign_snapshot = self._snapshot_foreign_payment_allocations(line_type='installment')
            self.installment_ids = self._prepare_installment_lines()
            if self.installment_ids:
                self._force_lines_to_match_total(
                    self.installment_ids, self.price_after_discount, label=_('Installment')
                )
                # Cleanup draft/cancelled records and reallocate active funds sequentially
                self._reallocate_proposal_funds(line_type='installment', foreign_snapshot=foreign_snapshot)

                sorted_lines = self.installment_ids.sorted(key=lambda l: l.date)

                counter = 1
                for line in sorted_lines:
                    line.serial = counter
                    counter += 1

        self.force_recalculate_installments = False

    def get_other_payment_data(self, installment_lines, ind=1):
        if self.down_payment:
            if not self.down_payment_date:
                raise UserError(_("Please Add Down Payment Date."))
            obj = {
                "name": _('Down Payment'),
                "serial": ind,
                "amount": self.down_payment,
                "date": self.down_payment_date,
                "is_down_payment": True,
            }
            if self.sale_contract_reservation_id:
                obj["is_down_payment_reservation"] = True
            installment_lines.append((0, 0, obj))
        if self.delivery_payment:
            if not self.delivery_payment_date:
                raise UserError(_("Please Add Delivery Payment Date."))
            obj = {
                "name": _('Delivery Payment'),
                "serial": ind,
                "amount": self.delivery_payment,
                "date": self.delivery_payment_date,
            }
            installment_lines.append((0, 0, obj))

        if self.post_contract_price:
            if not self.post_contract_date:
                raise UserError(_("Please Add Post Contract Date."))
            obj = {
                "name": _('Down Payment 2'),
                "serial": ind,
                "amount": self.post_contract_price,
                "date": self.post_contract_date,
            }
            installment_lines.append((0, 0, obj))

        return installment_lines

    def action_calculate_parking_installment(self):
        if self.state not in ['draft', 'draft_contract']:
            raise ValidationError(_("Parking installments can only be calculated in Draft or Draft Contract state."))

        [line.unlink() for line in self.installment_parking_line_ids]
        for rec in self:
            template = self.env['maintenance.template'].browse(self.parking_installment_template_id.id)

            if template.monthly_installment_duration > 0 and self.monthly_parking_installment_start_date:
                name = "Monthly Parking Installment"
                parking_initial_amount = (
                                                 template.monthly_installment_amount * rec.parking_price) / template.monthly_installment_duration
                amount = parking_initial_amount
                date = self.monthly_parking_installment_start_date
                vat_id = self.unit_vat_id.id
                for line in range(0, template.monthly_installment_duration):
                    self.add_monthly_parking_lines(date, amount, name, vat_id)
                    date = date + relativedelta(months=1)
            if template.quarterly_installment_duration > 0 and self.quarterly_parking_installment_start_date:
                name = "Quarterly Parking Installment"
                parking_initial_amount = (
                                                 template.quarterly_installment_amount * rec.parking_price) / template.quarterly_installment_duration
                amount = parking_initial_amount
                date = self.quarterly_parking_installment_start_date
                vat_id = self.unit_vat_id.id

                for line in range(0, template.quarterly_installment_duration):
                    self.add_monthly_parking_lines(date, amount, name, vat_id)
                    date = date + relativedelta(months=3)

            if template.semi_annual_installment_duration > 0 and self.semi_annual_parking_installment_start_date:
                name = "Semi Annual Parking Installment"
                parking_initial_amount = (
                                                 template.semi_annual_installment_amount * rec.parking_price) / template.semi_annual_installment_duration
                amount = parking_initial_amount
                date = self.semi_annual_parking_installment_start_date
                vat_id = self.unit_vat_id.id

                for line in range(0, template.semi_annual_installment_duration):
                    self.add_monthly_parking_lines(date, amount, name, vat_id)
                    date = date + relativedelta(months=6)

            if template.annual_installment_duration > 0 and self.annual_parking_installment_start_date:
                name = "Annual Parking Installment"
                parking_initial_amount = (
                                                 template.annual_installment_amount * rec.parking_price) / template.annual_installment_duration
                amount = parking_initial_amount
                date = self.annual_parking_installment_start_date
                vat_id = self.unit_vat_id.id

                for line in range(0, template.annual_installment_duration):
                    self.add_monthly_parking_lines(date, amount, name, vat_id)
                    date = date + relativedelta(years=1)

    def add_monthly_parking_lines(self, date, amount, name, vat_id):
        # Just create the parking line, don't recalculate unit_price
        self.env['loan.line'].create({
            'installments_parking_sale_proposal_id': self.id,
            'date': date,
            'amount': amount,
            'name': name,
            'vat_id': vat_id,
        })

    @api.onchange('include_free_parking')
    def _onchange_include_free_parking(self):
        if self.include_free_parking == False:
            self.slots = None

    @api.onchange('referred_by', 'referred_by_partner_id')
    def _onchange_broker_contract(self):
        """Auto-populate broker contract when broker is selected"""
        if self.referred_by == 'broker' and self.referred_by_partner_id:
            # Find active broker contract for this broker
            today = fields.Date.today()
            broker_contract = self.env['broker.contract'].search([
                ('broker_company', '=', self.referred_by_partner_id.id),
                ('contract_start_date', '<=', today),
                ('contract_end_date', '>=', today),
            ], limit=1)

            if broker_contract:
                self.broker_contract_id = broker_contract.id

    def _get_total_collected_amount(self):
        """Calculate total collected amount (EOI + Reservation + Paid Installments)"""
        self.ensure_one()

        total_collected = (self.eoi_amount or 0.0) + (self.reservation_payment or 0.0)

        for installment in self.installment_ids:
            for alloc in installment.allocation_ids:
                if alloc._is_collected():
                    total_collected += alloc.allocated_amount

        return total_collected

    def _get_collection_percentage(self):
        """Calculate current collection percentage"""
        self.ensure_one()

        if not self.price_after_discount or self.price_after_discount == 0:
            return 0.0

        total_collected = self._get_total_collected_amount()
        collection_percentage = (total_collected / self.price_after_discount) * 100

        return collection_percentage

    def _get_applicable_broker_commission(self):
        """Get applicable broker commission based on contract lines ONLY"""
        self.ensure_one()

        if not self.broker_contract_id:
            return 0.0

        today = fields.Date.today()

        # Find applicable contract line based on date - ONLY use lines, not main contract
        for line in self.broker_contract_id.line_ids:
            if line.start_date and line.end_date and line.start_date <= today <= line.end_date:
                return line.commission

        # If no line found, return 0 (don't use main contract commission)
        return 0.0

    def _is_commission_eligible(self):
        """Collections generate commission once the client signed, until the contract is cancelled/terminated"""
        self.ensure_one()
        return self.state not in COMMISSION_EXCLUDED_STATES

    def _get_installment_collection_percentage(self):
        """Collected % of the unit price from unit installments only (maintenance excluded)"""
        self.ensure_one()
        if not self.price_after_discount or self.price_after_discount <= 0:
            return 0.0
        collected = 0.0
        for installment in self.installment_ids:
            for alloc in installment.allocation_ids:
                if alloc._is_collected():
                    collected += alloc.allocated_amount
        return collected / self.price_after_discount * 100

    def _ensure_broker_contract(self):
        """Link the referring broker's contract valid on the contract issue date (or today)"""
        self.ensure_one()
        if self.broker_contract_id or self.referred_by != 'broker' or not self.referred_by_partner_id:
            return
        BrokerContract = self.env['broker.contract']
        for ref_date in filter(None, (self.contract_issue_date, fields.Date.today())):
            broker_contract = BrokerContract.search([
                ('broker_company', '=', self.referred_by_partner_id.id),
                ('contract_start_date', '<=', ref_date),
                ('contract_end_date', '>=', ref_date),
            ], limit=1)
            if broker_contract:
                self.broker_contract_id = broker_contract
                return

    def _get_applicable_commission(self, contract):
        """Get applicable commission based on contract lines"""
        self.ensure_one()

        if not contract:
            return 0.0

        today = fields.Date.today()

        # Find applicable contract line based on date
        for line in contract.line_ids:
            if line.start_date and line.end_date and line.start_date <= today <= line.end_date:
                return line.commission

        return 0.0

    def _check_and_create_broker_claim(self):
        """Check if collection percentage is met and create broker claim"""
        self.ensure_one()

        # Skip if not referred by broker
        if self.referred_by != 'broker':
            return

        # Skip if broker claim already created
        if self.broker_claim_created:
            return

        # Link the broker's active contract when it was not selected on the form
        self._ensure_broker_contract()

        # Skip if no broker contract
        if not self.broker_contract_id:
            return

        self._create_claim_for_partner(
            partner=self.referred_by_partner_id,
            contract=self.broker_contract_id,
            claim_type='broker'
        )

    def _check_and_create_ambassador_claim(self):
        """Check if collection percentage is met and create ambassador claim"""
        self.ensure_one()

        # Skip if not referred by ambassador
        if self.referred_by != 'ambassador':
            return

        # Skip if ambassador claim already created
        if self.ambassador_claim_created:
            return

        # Find ambassador's broker contract
        ambassador_contract = self.env['broker.contract'].search([
            ('broker_company', '=', self.referred_by_partner_id.id),
            ('contract_start_date', '<=', fields.Date.today()),
            ('contract_end_date', '>=', fields.Date.today()),
        ], limit=1)

        if not ambassador_contract:
            return

        self._create_claim_for_partner(
            partner=self.referred_by_partner_id,
            contract=ambassador_contract,
            claim_type='ambassador'
        )

    def _create_claim_for_partner(self, partner, contract, claim_type='broker'):
        """
        Unified method to create claims for broker or ambassador

        :param partner: res.partner record (broker or ambassador)
        :param contract: broker.contract record
        :param claim_type: 'broker' or 'ambassador'
        """
        self.ensure_one()

        # Get required collection percentage from contract
        required_collection = contract.collection or 0.0

        # Calculate collection percentage ONLY from unit installments (exclude maintenance)
        total_collected_for_claim = 0.0

        # Add ONLY installment payments (exclude maintenance)
        for installment in self.installment_ids:
            for alloc in installment.allocation_ids:
                if alloc._is_collected():
                    total_collected_for_claim += alloc.allocated_amount

        # Calculate percentage based on unit price only (not including maintenance)
        current_collection = (total_collected_for_claim / self.price_after_discount * 100) if self.price_after_discount > 0 else 0.0

        # Check if collection threshold is met
        if current_collection >= required_collection:

            # Get commission percentage
            commission_percentage = self._get_applicable_commission(contract)

            if commission_percentage > 0:
                # Agents selected on the contract each get their own claim at their own rate
                agent_members = self.agent_commission_ids if self.split_commission_with_agents \
                    else self.env['broker.team.member']

                # Create broker claim (works for both broker and ambassador)
                claim = self.env['broker.claim'].create({
                    'broker_company': partner.id,
                    'claim_type': claim_type,
                    'unit_id': self.unit_id.id,
                    'sale_proposal_id': self.id,
                    'unit_sold_price': self.price_after_discount,
                    'commission': commission_percentage,
                    'collection_percentage': current_collection,
                })

                # Update sale proposal based on claim type
                if claim_type == 'broker':
                    self.write({
                        'broker_claim_id': claim.id,
                        'broker_claim_created': True,
                    })
                else:  # ambassador
                    self.write({
                        'ambassador_claim_id': claim.id,
                        'ambassador_claim_created': True,
                    })

                # Create one claim per agent for their own extra commission
                BrokerClaim = self.env['broker.claim']
                for member in agent_members:
                    if not member.partner_id or member.commission <= 0:
                        continue
                    already_claimed = BrokerClaim.search_count([
                        ('sale_proposal_id', '=', self.id),
                        ('broker_company', '=', member.partner_id.id),
                        ('parent_claim_id', '=', claim.id),
                    ])
                    if already_claimed:
                        continue
                    BrokerClaim.create({
                        'broker_company': member.partner_id.id,
                        'claim_type': 'agent',
                        'parent_claim_id': claim.id,
                        'unit_id': self.unit_id.id,
                        'sale_proposal_id': self.id,
                        'unit_sold_price': self.price_after_discount,
                        'commission': member.commission,
                        'collection_percentage': current_collection,
                    })

    def _check_and_create_non_sales_claims(self):
        """
        Create one claim per employee assigned to a commission category, applying
        once the company-wide collection threshold is met. Runs on every contract
        regardless of referral type.
        """
        self.ensure_one()

        if not self._is_commission_eligible():
            return

        ICP = self.env['ir.config_parameter'].sudo()
        base_rate = float(ICP.get_param(
            'arkzayed_18_realestate_development.non_sales_commission_percentage', 0.0) or 0.0)
        if base_rate <= 0:
            return

        required_collection = float(ICP.get_param(
            'arkzayed_18_realestate_development.non_sales_commission_collection_percentage', 0.0) or 0.0)
        current_collection = self._get_installment_collection_percentage()
        if current_collection < required_collection:
            return

        BrokerClaim = self.env['broker.claim']
        categories = self.env['commission.category'].search([('employee_ids', '!=', False)])
        for category in categories:
            category_percentage = base_rate * category.percentage / 100.0
            if category_percentage <= 0:
                continue
            # The category's share of the base rate is split equally among its employees
            commission_percentage = category_percentage / len(category.employee_ids)
            for employee in category.employee_ids:
                partner = employee.work_contact_id
                if not partner:
                    continue
                already_claimed = BrokerClaim.search_count([
                    ('sale_proposal_id', '=', self.id),
                    ('broker_company', '=', partner.id),
                    ('claim_type', '=', 'employee'),
                ])
                if already_claimed:
                    continue
                BrokerClaim.create({
                    'broker_company': partner.id,
                    'employee_id': employee.id,
                    'claim_type': 'employee',
                    'unit_id': self.unit_id.id,
                    'sale_proposal_id': self.id,
                    'unit_sold_price': self.price_after_discount,
                    'commission': commission_percentage,
                    'collection_percentage': current_collection,
                    'with_withholding_tax': False,
                })

    def action_view_broker_claim(self):
        """Smart button to view broker claim"""
        self.ensure_one()

        if not self.broker_claim_id:
            raise UserError(_("No broker claim has been created yet."))

        return {
            'name': _('Broker Claim'),
            'type': 'ir.actions.act_window',
            'res_model': 'broker.claim',
            'view_mode': 'form',
            'res_id': self.broker_claim_id.id,
            'target': 'current',
        }

    def action_view_ambassador_claim(self):
        """Smart button to view ambassador claim"""
        self.ensure_one()

        if not self.ambassador_claim_id:
            raise UserError(_("No ambassador claim has been created yet."))

        return {
            'name': _('Ambassador Claim'),
            'type': 'ir.actions.act_window',
            'res_model': 'broker.claim',
            'view_mode': 'form',
            'res_id': self.ambassador_claim_id.id,
            'target': 'current',
        }

    @api.onchange('user_id', 'commission_ids')
    def _onchange_user_commission_check(self):
        """Ensure commission lines are populated when user changes"""
        if self.user_id and not self.commission_ids:
            self._build_commission_hierarchy()

    @api.onchange('user_id')
    def _onchange_user_id_commission(self):
        """Update commission lines when salesperson changes"""
        if self.user_id and not self.commission_ids:
            # Auto-populate commission hierarchy
            self._build_commission_hierarchy()

    # _build_commission_hierarchy: this copy was always shadowed by
    # sale_proposal_crm_ext.py's (imported after this file - Odoo's MRO means the
    # later-imported one wins), so it never ran. Removed; see sale_proposal_crm_ext.py for
    # the one that was actually active, now moved to isky_18_realestate_developer_commission.

    def action_view_non_sales_claims(self):
        """Smart button to view non-sales employee claims"""
        self.ensure_one()
        return {
            'name': _('Non Sales Claims'),
            'type': 'ir.actions.act_window',
            'res_model': 'broker.claim',
            'view_mode': 'list,form',
            'domain': [('sale_proposal_id', '=', self.id), ('claim_type', '=', 'employee')],
            'context': {'default_sale_proposal_id': self.id, 'default_claim_type': 'employee'},
        }

    def _auto_create_commission_achievements(self):
        """
        Automatically create commission achievements for each user in commission lines
        based on their individual commission plan and collection threshold.

        :return: list of (user name, reason) for commission lines that were skipped
        """
        self.ensure_one()
        skipped = []

        if not self._is_commission_eligible():
            return [(_('All'), _('Contract status "%s" does not generate commission') % dict(
                self._fields['state']._description_selection(self.env)).get(self.state, self.state))]

        # Contracts created before the hierarchy existed have an empty commission tab
        if not self.commission_ids and self.user_id:
            self._build_commission_hierarchy()
        if not self.commission_ids:
            return [(_('All'), _('No salesperson / commission lines on the contract'))]

        collection_percentage = self._get_installment_collection_percentage()
        if collection_percentage <= 0:
            return [(_('All'), _('Nothing collected yet from unit installments'))]

        contract_date = self.contract_issue_date or fields.Date.today()
        achievement_obj = self.env['realestate.commission.achievement']

        # Determine broker and ambassador flags
        has_broker = (self.referred_by == 'broker' and bool(self.referred_by_partner_id))
        has_ambassador = (self.referred_by == 'ambassador' and bool(self.referred_by_partner_id))

        for commission_line in self.commission_ids:
            employee = commission_line.employee_id
            if not employee:
                continue

            # Check if achievement already exists
            if achievement_obj.search_count([
                ('sale_proposal_id', '=', self.id),
                ('user_id', '=', employee.id),
            ]):
                continue

            # Find this user's commission plan with matching broker/ambassador flags
            user_commission_plan = self.env['sale.commission.plan'].search([
                ('state', 'in', ['approved', 'done']),
                ('type', '=', 'achieve'),
                ('realestate_commission', '=', True),
                ('with_broker', '=', has_broker),
                ('with_ambassador', '=', has_ambassador),
                ('date_from', '<=', contract_date),
                ('date_to', '>=', contract_date),
                ('user_ids.user_id', '=', employee.id)
            ], limit=1)

            if not user_commission_plan:
                skipped.append((employee.name, _(
                    'No approved real estate "achieve" plan (With Broker=%s, With Ambassador=%s) covering %s') % (
                    has_broker, has_ambassador, contract_date)))
                continue

            # Collection threshold is reached when collected % >= plan collection %
            user_collection_threshold = user_commission_plan.collection or 0.0
            if round(collection_percentage, 2) < round(user_collection_threshold, 2):
                skipped.append((employee.name, _('Collection %.2f%% is below plan %s threshold %.2f%%') % (
                    collection_percentage, user_commission_plan.name, user_collection_threshold)))
                continue

            # Find applicable target period
            applicable_target = None
            for target in user_commission_plan.target_ids:
                if target.date_from <= contract_date <= target.date_to:
                    if self.price_after_discount >= target.amount:
                        applicable_target = target
                        break

            if not applicable_target:
                skipped.append((employee.name, _('No target period of plan %s matches %s / unit price') % (
                    user_commission_plan.name, contract_date)))
                continue

            commission_per_million = user_commission_plan.commission_amount or 0.0
            if commission_per_million <= 0:
                skipped.append((employee.name, _('Plan %s has no commission amount') % user_commission_plan.name))
                continue

            # Calculate commission amount
            millions = self.price_after_discount / 1000000.0
            total_commission = millions * commission_per_million * (commission_line.commission / 100.0)

            achievement_obj.create({
                'sale_proposal_id': self.id,
                'opportunity_id': self.sale_contract_reservation_id.opportunity_id.id if self.sale_contract_reservation_id and self.sale_contract_reservation_id.opportunity_id else False,
                'user_id': employee.id,
                'job_level_id': employee.job_level_id.id if employee.job_level_id else False,
                'job_position_id': employee.employee_id.job_id.id if employee.employee_id else False,
                'sales_volume': self.price_after_discount,
                'commission_percentage': commission_per_million,
                'commission_amount': total_commission,
                'commission_plan_id': user_commission_plan.id,
                'commission_target_id': applicable_target.id,
                'is_tcr_sales_person': commission_line.jop_position == 'Sales Person',
            })

        return skipped

    def action_generate_commissions(self):
        """Generate missing sales commissions and broker/ambassador claims, logging skip reasons"""
        for rec in self:
            skipped = rec._auto_create_commission_achievements()
            if rec.referred_by == 'broker':
                rec._check_and_create_broker_claim()
            elif rec.referred_by == 'ambassador':
                rec._check_and_create_ambassador_claim()
            rec._check_and_create_non_sales_claims()

            lines = [_('<b>Commission generation</b> - collection %.2f%%, %s achievement(s)') % (
                rec._get_installment_collection_percentage(), len(rec.commission_achievement_ids))]
            if rec.referred_by in ('broker', 'ambassador'):
                claim = rec.broker_claim_id if rec.referred_by == 'broker' else rec.ambassador_claim_id
                if claim:
                    lines.append(_('Claim: %s') % claim.name)
                    if claim.agent_claim_ids:
                        lines.append(_('Agent claims: %s') % ', '.join(claim.agent_claim_ids.mapped('name')))
                elif rec.referred_by == 'broker' and not rec.broker_contract_id:
                    lines.append(_('Broker claim skipped: no broker contract valid for %s') % html_escape(rec.referred_by_partner_id.name))
                else:
                    lines.append(_('Claim not created: collection threshold not reached or no valid contract line'))
            lines += ['%s: %s' % (html_escape(name), html_escape(reason)) for name, reason in skipped]
            rec.message_post(body=markupsafe.Markup('<br/>'.join(lines)))
        return True

    @api.depends(
        'installment_ids.paid',
        'installment_ids.amount',
        'maintenance_installment_ids.paid',
        'maintenance_installment_ids.amount',
        'price_after_discount',
        'state'
    )
    def _compute_collection_amounts(self):
        """Compute collection amounts and auto-trigger commission creation"""
        for rec in self:
            # Calculate total collected (includes maintenance for display)
            total_collected = 0.0

            for installment in rec.installment_ids:
                for alloc in installment.allocation_ids:
                    if alloc._is_collected():
                        total_collected += alloc.allocated_amount

            for maintenance in rec.maintenance_installment_ids:
                for alloc in maintenance.allocation_ids:
                    if alloc._is_collected():
                        total_collected += alloc.allocated_amount

            rec.total_collected_amount = total_collected

            # Calculate collection percentage
            if rec.price_after_discount > 0:
                rec.collection_percentage = (total_collected / rec.price_after_discount) * 100
            else:
                rec.collection_percentage = 0.0

            # Auto-trigger commission creation once signed by client
            if rec._is_commission_eligible() and total_collected > 0:
                rec._auto_create_commission_achievements()

            # Auto-trigger broker claim when collection threshold met
            if rec.referred_by == 'broker':
                rec._check_and_create_broker_claim()

            # Auto-trigger ambassador claim when collection threshold met
            if rec.referred_by == 'ambassador':
                rec._check_and_create_ambassador_claim()

            # Auto-trigger non-sales employee claims when collection threshold met
            rec._check_and_create_non_sales_claims()

    def action_view_commission_achievements(self):
        """Smart button to view commission achievements"""
        self.ensure_one()
        return {
            'name': _('Commission Achievements'),
            'type': 'ir.actions.act_window',
            'res_model': 'realestate.commission.achievement',
            'view_mode': 'list,form',
            'domain': [('sale_proposal_id', '=', self.id)],
            'context': {
                'default_sale_proposal_id': self.id,
            }
        }

    def action_terminate_contract(self):
        self.ensure_one()
        if self.state != 'signed_client':
            raise ValidationError(_("Only contracts in 'Signed by Client' state can be terminated."))
        terminate_reason = self.env['block.reason'].search([('blocked_from_termination', '=', True)], limit=1)
        if not terminate_reason:
            raise ValidationError(
                _("No block reason is configured for 'Blocked from Termination'. Please configure one in Block Reasons."))
        self.write({
            'state': 'terminated',
            'termination_date': fields.Date.today(),
            'terminated_by': self.env.user.id,
        })
        if self.unit_id:
            self.unit_id.write({
                'unit_status': 'blocked',
                'reason_id': terminate_reason.id,
            })

    def _get_check_deposit_wallet_lines(self):

        self.ensure_one()

        def _build_lines(installments, base_amount):
            result = []
            for inst in installments:
                percentage = round((inst.total_amount / base_amount) * 100, 2) if base_amount else 0.0
                vals = {
                    'name': inst.name or '',
                    'percentage': percentage,
                    'amount': inst.total_amount,
                    'date': inst.date,
                }
                # cheque_no / bank_name / has_cheque always present, so the Excel writer
                # needs no cheque module.
                vals.update(self._line_cheque_info(inst))
                result.append(vals)
            return result

        sorted_installments = self.installment_ids.sorted(
            key=lambda r: (r.date is False, r.date or date.max))
        sorted_maintenance = self.maintenance_installment_ids.sorted(
            key=lambda r: (r.date is False, r.date or date.max))

        lines_data = (
            _build_lines(sorted_installments, self.price_after_discount) +
            _build_lines(sorted_maintenance, self.maintenance_price)
        )

        for index, line in enumerate(lines_data, start=1):
            line['serial'] = index

        return lines_data

    def action_generate_excel_report(self):
        self.ensure_one()

        if not self.installment_ids and not self.maintenance_installment_ids:
            raise UserError(_("No installments or maintenance installments to export."))

        if not self.customer_id:
            raise UserError(_("Customer is missing."))

        if not self.unit_id:
            raise UserError(_("Unit is missing."))

        lines_data = self._get_check_deposit_wallet_lines()

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Cheques deposit wallet')

        FONT = 'Arial'

        # ================= FORMATS =================
        title_fmt = workbook.add_format({
            'font_name': FONT, 'bold': True, 'font_size': 32,
            'align': 'right', 'valign': 'vcenter'
        })

        center_title_fmt = workbook.add_format({
            'font_name': FONT, 'bold': True, 'font_size': 14,
            'align': 'center', 'underline': True
        })

        label_fmt = workbook.add_format({
            'font_name': FONT, 'bold': True, 'font_size': 11,
            'align': 'center', 'valign': 'vcenter'
        })

        multi_line_label_fmt = workbook.add_format({
            'font_name': FONT, 'bold': True, 'font_size': 11,
            'align': 'center', 'valign': 'vcenter',
            'text_wrap': True
        })

        value_fmt = workbook.add_format({
            'font_name': FONT, 'font_size': 11,
            'align': 'center', 'valign': 'vcenter'
        })

        header_fmt = workbook.add_format({
            'font_name': FONT, 'bold': True, 'font_size': 11,
            'align': 'center', 'valign': 'vcenter',
            'border': 1
        })

        cell_fmt = workbook.add_format({
            'font_name': FONT, 'font_size': 10,
            'align': 'center', 'valign': 'vcenter',
            'border': 1
        })

        amount_fmt = workbook.add_format({
            'font_name': FONT, 'font_size': 10,
            'align': 'center', 'valign': 'vcenter',
            'border': 1,
            'num_format': '#,##0.00'
        })

        amount_fmt_header = workbook.add_format({
            'font_name': FONT, 'font_size': 10,
            'align': 'center', 'valign': 'vcenter',
            'num_format': '#,##0.00'
        })

        date_fmt = workbook.add_format({
            'font_name': FONT, 'font_size': 10,
            'align': 'center', 'valign': 'vcenter',
            'border': 1,
            'num_format': 'dd/mmm/yy'
        })

        percent_fmt = workbook.add_format({
            'font_name': FONT, 'font_size': 10,
            'align': 'center', 'valign': 'vcenter',
            'border': 1,
            'num_format': '0.00"%"'
        })

        # Grey-background variants used for payment-plan lines with no cheque linked
        GREY = '#D9D9D9'
        cell_fmt_grey = workbook.add_format({
            'font_name': FONT, 'font_size': 10,
            'align': 'center', 'valign': 'vcenter',
            'border': 1, 'bg_color': GREY
        })
        amount_fmt_grey = workbook.add_format({
            'font_name': FONT, 'font_size': 10,
            'align': 'center', 'valign': 'vcenter',
            'border': 1, 'bg_color': GREY,
            'num_format': '#,##0.00'
        })
        date_fmt_grey = workbook.add_format({
            'font_name': FONT, 'font_size': 10,
            'align': 'center', 'valign': 'vcenter',
            'border': 1, 'bg_color': GREY,
            'num_format': 'dd/mmm/yy'
        })
        percent_fmt_grey = workbook.add_format({
            'font_name': FONT, 'font_size': 10,
            'align': 'center', 'valign': 'vcenter',
            'border': 1, 'bg_color': GREY,
            'num_format': '0.00"%"'
        })

        # ================= PAGE SETUP =================
        worksheet.set_paper(9)
        worksheet.set_portrait()
        worksheet.fit_to_pages(1, 1)
        worksheet.set_margins(0.5, 0.5, 0.6, 0.6)
        worksheet.hide_gridlines(2)
        worksheet.set_zoom(100)
        worksheet.set_default_row(16)

        # ================= COLUMNS =================
        worksheet.set_column('A:A', 3)
        worksheet.set_column('B:B', 4)   # S
        worksheet.set_column('C:C', 28)  # Payment/Installment Name
        worksheet.set_column('D:D', 18)  # CHK Number
        worksheet.set_column('E:E', 14)  # Installment %
        worksheet.set_column('F:F', 20)  # Unit Installment
        worksheet.set_column('G:G', 18)  # Bank Name
        worksheet.set_column('H:H', 20)  # Date of Installment

        # ================= ROW HEIGHTS =================
        worksheet.set_row(0, 38)
        worksheet.set_row(1, 22)
        worksheet.set_row(2, 30)
        worksheet.set_row(3, 30)
        worksheet.set_row(4, 30)
        worksheet.set_row(5, 30)

        # ================= HEADER =================
        worksheet.merge_range('B1:H1', 'The arkzayed', title_fmt)
        worksheet.merge_range('D2:F2', 'Cheques deposit wallet', center_title_fmt)

        worksheet.write('C3', 'Client Name :', label_fmt)
        worksheet.merge_range('D3:F3', self.customer_id.name or '', value_fmt)

        worksheet.write('G3', 'Date :', label_fmt)
        worksheet.write('H3', fields.Date.today().strftime('%d/%b/%y'), value_fmt)

        worksheet.write('C4', 'Client ID Number :', label_fmt)
        worksheet.merge_range('D4:F4', self.customer_id.national_id or '', value_fmt)

        worksheet.write('G4', 'Unit Code :', label_fmt)
        worksheet.write('H4', self.unit_id.system_code or '', value_fmt)

        worksheet.write('C5', 'Sold Price :', label_fmt)
        worksheet.merge_range('D5:F5', self.price_after_discount, amount_fmt_header)

        worksheet.write('G5', 'Maintenance Fees :', label_fmt)
        worksheet.write('H5', self.maintenance_price, amount_fmt_header)

        total_amount = sum(line['amount'] for line in lines_data)
        total_lines = len(lines_data)

        worksheet.write('C6', 'Total Cheque\nAmount Received', multi_line_label_fmt)
        worksheet.merge_range('D6:F6', total_amount, amount_fmt_header)

        worksheet.write('G6', 'Total Installments :', label_fmt)
        worksheet.write('H6', total_lines, value_fmt)

        # ================= TABLE HEADER =================
        table_header_row = 7
        headers = ['S', 'Payment/Installment Name', 'CHK Number', 'Installment %',
                   'Unit Installment', 'Bank Name', 'Date of Installment']

        for col, title in enumerate(headers):
            worksheet.write(table_header_row, col + 1, title, header_fmt)

        worksheet.autofilter(f'B{table_header_row + 1}:H{table_header_row + 1}')
        worksheet.repeat_rows(table_header_row, table_header_row)

        # ================= TABLE DATA =================
        row = table_header_row + 1

        for line in lines_data:
            grey = not line['has_cheque']
            c_fmt = cell_fmt_grey if grey else cell_fmt
            a_fmt = amount_fmt_grey if grey else amount_fmt
            d_fmt = date_fmt_grey if grey else date_fmt
            p_fmt = percent_fmt_grey if grey else percent_fmt

            worksheet.write(row, 1, line['serial'], c_fmt)
            worksheet.write(row, 2, line['name'], c_fmt)
            worksheet.write_string(row, 3, line['cheque_no'] or '', c_fmt)
            worksheet.write(row, 4, line['percentage'], p_fmt)
            worksheet.write(row, 5, line['amount'], a_fmt)
            worksheet.write(row, 6, line['bank_name'] or '', c_fmt)
            if line['date']:
                worksheet.write_datetime(row, 7, fields.Date.to_date(line['date']), d_fmt)
            else:
                worksheet.write(row, 7, '', d_fmt)

            row += 1

        signature_row = row + 1
        worksheet.write(signature_row, 7, 'Client Signature', label_fmt)

        worksheet.print_area(f'A1:H{signature_row + 2}')

        workbook.close()
        output.seek(0)

        attachment = self.env['ir.attachment'].create({
            'name': f'Cheque_Report_{self.name}.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new'
        }

    def action_print_check_deposit_wallet_pdf(self):
        self.ensure_one()

        if not self.installment_ids and not self.maintenance_installment_ids:
            raise UserError(_("No installments or maintenance installments to export."))

        if not self.customer_id:
            raise UserError(_("Customer is missing."))

        if not self.unit_id:
            raise UserError(_("Unit is missing."))

        return self.env.ref(
            'arkzayed_18_realestate_development.check_deposit_wallet_report'
        ).report_action(self)

    def action_print_unit_plan_report(self):
        self.ensure_one()
        if not self.unit_id:
            raise ValidationError(_("You should choose unit first."))
        if not self.unit_id.unit_plan:
            raise ValidationError(_("Unit plan for this unit is not found."))
        if self.unit_id.unit_type in ["office", "retail", "medical", "residential"]:
            return self.env.ref('arkzayed_18_realestate_development.action_print_plan_in_contract').report_action(self,)

    def action_get_installment_report(self):
        self.ensure_one()
        if self.env.context.get('is_pdf'):
            if not self.unit_id:
                raise ValidationError(_("You should choose unit first."))

            if not self.installment_template_id and not self.maintenance_template_id:
                raise ValidationError(_("Please select an installment or maintenance template in the contract first."))

            if not self.installment_ids and not self.maintenance_installment_ids:
                raise ValidationError(_("No installments or maintenance installments to export."))

            data = {
                'print_from_model': self._name,
                'print_from_id': self.id,
                'unit_id': self.unit_id.id
            }
            return self.env.ref('arkzayed_18_realestate_development.unit_payment_plan_report').report_action(
                self.unit_id, data=data)

        else:
            if not self.maintenance_installment_ids or not self.installment_ids:
                raise ValidationError(_("No installment lines are linked to this contract."))
            return {
                'type': 'ir.actions.act_url',
                'url': f"/payment-plan/excel/report/{self.id}?model={self._name}",
                'target': 'new',
            }
        


    def action_export_handover_excel(self):
        active_ids = ','.join(str(x) for x in self.ids)
        return {
            'type': 'ir.actions.act_url',
            'url': f'/handover/report/xlsx?active_ids={active_ids}',
            'target': 'self',
        }

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
        for proposal in self:
            if proposal.installment_ids:
                sorted_lines = proposal.installment_ids.sorted(key=lambda l: l.date)
                counter = 1
                for line in sorted_lines:
                    line.serial = counter
                    counter += 1

            if proposal.maintenance_installment_ids:
                sorted_maint_lines = proposal.maintenance_installment_ids.sorted(key=lambda l: l.date)
                maint_counter = 1
                for maint_line in sorted_maint_lines:
                    maint_line.serial = maint_counter
                    maint_counter += 1