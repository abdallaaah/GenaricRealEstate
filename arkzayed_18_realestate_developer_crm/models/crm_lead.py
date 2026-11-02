import re
from email.policy import default
from datetime import timedelta

from odoo import models, fields, api, _, Command
from odoo.exceptions import ValidationError, UserError, AccessError
import datetime
from bs4 import BeautifulSoup
from markupsafe import Markup
import warnings
from odoo.addons.arkzayed_18_realestate_development.models.selections import  unit_type_selection,residential_type_selection
from odoo.tools import format_datetime

ALL_PHONE_FIELDS = ['phone', 'mobile', 'phone1', 'phone2', 'phone3', 'phone4']


class CrmLead(models.Model):
    _inherit = 'crm.lead'
    _rec_name = 'opportunity_sequence'

    #this is a pretty silly way but simple enough to count leads in ninja dashboard

    ninja_count = fields.Integer(default=1, readonly=1, string="Group Count")
    name = fields.Char(
        'Opportunity', index='trigram', required=False,
        compute='_compute_name', readonly=False, store=True, tracking=True)

    lead_sequence = fields.Char(index='trigram', readonly=True, default=lambda self: _('New'), copy=False)
    opportunity_sequence = fields.Char(index='trigram', readonly=True, default=lambda self: _('New'))
    lead_stage_id = fields.Many2one('lead.stage')
    first_assignment_date = fields.Datetime(compute='_compute_first_assignment_date', store=True)

    interested_in = fields.Selection([
        ('buy', 'Buy'),
        ('rent', 'Rent'),
        ('sell', 'Sell')
    ], default='buy')
    buying_type = fields.Selection([
        ('primary', 'Primary'),
        ('resale', 'Resale')
    ],default='primary')
    buying_purpose = fields.Selection([
        ('for_invest', 'For Invest'),
        ('for_home', 'For Home')
    ])

    developer_id = fields.Many2one('res.partner', )
    project_id = fields.Many2one('developer.project', tracking=True)

    place_preferences = fields.Selection([
        ('compound', 'Compound'),
        ('any', 'Any'),
    ])

    number_of_bedrooms = fields.Integer()
    number_of_bathrooms = fields.Integer()
    building_area = fields.Integer()
    garden_area = fields.Integer()
    land_area = fields.Integer()

    min_area = fields.Float()
    max_area = fields.Float()
    min_price = fields.Integer(string='Min Budget', tracking=True)
    max_price = fields.Integer(string='Max Budget', tracking=True)
    # unit_id = fields.Many2one(comodel_name="broker.unit")
    unit_id = fields.Many2one('real.estate.unit', string='Unit', tracking=True)
    unit_type = fields.Selection(selection=unit_type_selection, string='Unit Type')
    unit_number = fields.Char()
    finish_type = fields.Selection([
        ('finished', 'Finished'),
        ('semi_finished', 'Semi-Finished'),
        ('core_shell', 'Core and Shell')
    ])
    ready_to_move = fields.Boolean()
    reason_to_cancel = fields.Text()
    reasons = fields.Selection([
        ('not_interested', 'Not Interested'),
        ('low_budget', 'Low Budget'),
        ('out_of_district', 'Out of District')
    ])
    last_updated_date = fields.Datetime(string='Last Updated Date',default=fields.Datetime.now())

    residential_type = fields.Selection(selection=residential_type_selection, string='Residential Type')
    apartment_type_id = fields.Many2one('residential.sub.type', string='Chalet Type',
                                        domain=[('type', '=', 'apartment')])
    villa_type_id = fields.Many2one('residential.sub.type', string='Villa Type',
                                    domain=[('type', '=', 'villa')])
    loft_type_id = fields.Many2one('residential.sub.type', string='Loft Type',
                                   domain=[('type', '=', 'loft')])

    def update_lost_reason(self):
        Reason = self.env['crm.lost.reason']
        Lead = self.env['crm.lead']

        not_interested_reason = Reason.search([('name', '=', 'Not Interested')], limit=1)
        low_budget_reason = Reason.search([('name', '=', 'Low Budget')], limit=1)
        out_of_district_reason = Reason.search([('name', '=', 'Out of District')], limit=1)

        if not not_interested_reason:
            not_interested_reason = Reason.create({'name': 'Not Interested'})
        if not low_budget_reason:
            low_budget_reason = Reason.create({'name': 'Low Budget'})
        if not out_of_district_reason:
            out_of_district_reason = Reason.create({'name': 'Out of District'})

        mapping = {
            'not_interested': not_interested_reason.id,
            'low_budget': low_budget_reason.id,
            'out_of_district': out_of_district_reason.id,
        }

        lead_ids = Lead.search([('reasons', '!=', False), ('lost_reason_id', '=', False)])
        if len(lead_ids) > 1000:
            lead_ids = lead_ids[:1000]
        print(f"Updating {len(lead_ids)} leads...")
        for lead in lead_ids:
            new_reason_id = mapping.get(lead.reasons)
            if new_reason_id:
                lead.write({'lost_reason_id': new_reason_id})
                print(f"Updated lost reason for lead {lead.id} to {new_reason_id}")

    is_eoi = fields.Boolean(string="Is EOI Stage", related="stage_id.is_eoi")
    is_reserved = fields.Boolean(string="Is Reserved Stage", related="stage_id.is_reserved")
    is_contract = fields.Boolean(string="Is Contract Stage", related="stage_id.is_contract")
    is_cancel = fields.Boolean(string="Is Cancel Stage", related="stage_id.is_cancel")
    is_collected = fields.Boolean(string="Is Collected Stage", related="stage_id.is_collected")
    is_confirmed_contract = fields.Boolean(string="Is Confirmed Contract Stage", related="stage_id.is_confirmed_contract")
    is_request_to_cancel = fields.Boolean(string="Is Request to Cancel Stage", related="stage_id.is_request_to_cancel")

    reserved_date = fields.Date()
    contracted_date = fields.Date()
    cancellation_date = fields.Date()
    opp_cancellation_date = fields.Datetime(string='Cancellation Date',compute='cal_cancellation_date', store=True)


    # delivery_date = fields.Date()
    down_payment = fields.Float()
    reservation_price = fields.Float(tracking=True)
    contract_price = fields.Float(tracking=True)

    # payment_plan = fields.Integer()

    split_deal = fields.Boolean()
    split_with = fields.Selection([
        ('Outside_broker', 'Outside Broker'),
        ('ambassador', 'Ambassador'),
        ('non_sales', 'Non Sales'),
        ('customer', 'Customer'),
        ('referral', 'Referral'),
        ('sales', 'Sales'),
        ('other', 'Other'),
    ])
    partner_ids = fields.Many2many('res.partner', 'partner_id_rel_contact', 'partner_id', 'contact_id', )
    employee_ids = fields.Many2many('hr.employee', 'employee_id_rel', 'employee_id', 'referral_id', string="Referral")
    broker_ids = fields.Many2many('res.partner', 'partner_id_rel_broker_id', 'partner_id', 'broker_id',
                                  string="Outside Broker", domain="[('is_broker','=',True)]")
    ambassador_ids = fields.Many2many('res.partner', 'partner_id_rel_ambassador_id', 'partner_id', 'ambassador_id',
                                      string="Ambassador", domain="[('is_ambassador','=',True)]")
    non_sales_ids = fields.Many2many('res.users', 'res_user_id_rel_non_sales_id', 'res_user_id', 'non_sales_id')
    sales_ids = fields.Many2many('res.users', 'res_user_id_rel_sales_id', 'res_user_id', 'sales_id')
    other = fields.Char()
    ambassador_id = fields.Many2one('res.partner', string="Ambassador", domain="[('is_ambassador','=',True)]")
    partner_id = fields.Many2one('res.partner', )
    employee_id = fields.Many2one('hr.employee', )
    broker_id = fields.Many2one('res.partner', )
    non_sales_id = fields.Many2one('res.users', )
    sales_id = fields.Many2one('res.users', )
    team_leader = fields.Many2one('res.users', related="team_id.user_id")
    director = fields.Many2one('res.users', related="team_id.director_id")
    sales_manager = fields.Many2one('res.users', related="team_id.sales_manager_id")
    assigned_by_id = fields.Many2one('res.users', string='Assigned By',
                                     readonly=True, tracking=True,
                                     help="User who last assigned this lead")

    cancellation_approver = fields.Many2one('res.partner', readonly=True)

    is_converted = fields.Boolean()

    ################ approvals for manager, financial, sales and operations #####################################
    ## EOI
    eoi_status_for_manager = fields.Selection([
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending')
    ], default='pending', string='EOI Status For Manager', tracking=True)
    eoi_status_for_financial = fields.Selection([
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending')
    ], default='pending', string='EOI Status For Financial', tracking=True)
    eoi_status_for_sales = fields.Selection([
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending')
    ], default='pending', string='EOI Status For Sales', tracking=True)
    eoi_status_for_operations = fields.Selection([
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending')
    ], default='pending', string='EOI Status For Operations', tracking=True)
    eoi_rejection_reason_for_manager = fields.Text()
    eoi_rejection_reason_for_financial = fields.Text()
    eoi_rejection_reason_for_sales = fields.Text()
    eoi_rejection_reason_for_operations = fields.Text()

    ## Reservation
    reservation_status_for_manager = fields.Selection([
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending')
    ], default='pending', string='Reservation Status For Manager', tracking=True)
    reservation_status_for_financial = fields.Selection([
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending')
    ], default='pending', string='Reservation Status For Financial', tracking=True)
    reservation_status_for_sales = fields.Selection([
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending')
    ], default='pending', string='Reservation Status For Sales', tracking=True)
    reservation_status_for_operations = fields.Selection([
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending')
    ], default='pending', string='Reservation Status For Operations', tracking=True)
    reservation_rejection_reason_for_manager = fields.Text()
    reservation_rejection_reason_for_financial = fields.Text()
    reservation_rejection_reason_for_sales = fields.Text()
    reservation_rejection_reason_for_operations = fields.Text()

    ## Contract
    contract_status_for_manager = fields.Selection([
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending')
    ], default='pending', string='Contract Status For Manager', tracking=True)
    contract_status_for_financial = fields.Selection([
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending')
    ], default='pending', string='Contract Status For Financial', tracking=True)
    contract_status_for_sales = fields.Selection([
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending')
    ], default='pending', string='Contract Status For Sales', tracking=True)
    contract_status_for_operations = fields.Selection([
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending')
    ], default='pending', string='Contract Status For Operations', tracking=True)
    contract_rejection_reason_for_manager = fields.Text()
    contract_rejection_reason_for_financial = fields.Text()
    contract_rejection_reason_for_sales = fields.Text()
    contract_rejection_reason_for_operations = fields.Text()
    ########################################### END approvals #########################################################

    is_lead_cancelled = fields.Boolean()
    communication_channel = fields.Char(tracking=True)
    priority = fields.Selection(
        selection=[('', ''), ('0', 'Very Low'), ('1', 'Not Interested'), ('2', 'Hesitate'), ('3', 'Hot')],
        string='Rating', tracking=True, default='')

    channel = fields.Char()
    follow_up_date = fields.Date(tracking=True)

    has_auth_approval = fields.Boolean(default=False)
    is_sales_manager = fields.Boolean(compute='_compute_is_sales_manager')
    phone1 = fields.Char('Extra Phone 2')
    phone2 = fields.Char('International Phone')
    phone3 = fields.Char('Extra International Phone')
    phone4 = fields.Char('Extra International Phone 2')
    furniture_type = fields.Selection([('furnished', 'Furnished'), ('not_furnished', 'Not Furnished')])
    project_governorate = fields.Many2one(related='project_id.governorate_id')
    project_city = fields.Many2one(related='project_id.city_id')
    neighborhood_id = fields.Many2one('neighborhood.neighborhood', related='project_id.neighborhood_id',
                                      string='Neighborhood')
    mobile = fields.Char('Extra Phone', compute='_compute_mobile', readonly=False, store=True, tracking=True,
                         required=False)
    phone = fields.Char(
        'Phone', tracking=50,
        compute='_compute_phone', inverse='_inverse_phone', readonly=False, store=True, )
    country_id = fields.Many2one(
        'res.country', string='Country',
        compute='_compute_partner_address_values', readonly=False, store=True, )
    dest_country_id = fields.Many2one('res.country', string="Country")
    governorate_id = fields.Many2one('res.country.state', string="Governorate",
                                     domain="[('country_id', '=', dest_country_id)]")
    dest_city_id = fields.Many2one('res.country.city', string="District", required=False)
    sales_volume = fields.Integer(tracking=True)
    eoi_amount = fields.Float()
    campaign_id = fields.Many2one(ondelete='set null', tracking=True)
    source_id = fields.Many2one(ondelete='restrict', tracking=True, required=True)
    medium_id = fields.Many2one(ondelete='restrict', string='Sub Source', required=True)
    expect_closing_date = fields.Selection([('1m', '1 Month'), ('2m', '2 Months'), ('3m', '3 Months')])
    duplicate_number = fields.Boolean(default=False)
    eoi_attachment = fields.Binary()
    eoi_attachment_filename = fields.Char()
    reservation_attachment = fields.Binary()
    reservation_attachment_filename = fields.Char()
    contract_attachment = fields.Binary()
    contract_attachment_filename = fields.Char()
    campaign_form_name = fields.Char()
    media_buyer = fields.Char()

    first = fields.Boolean('New', related="lead_stage_id.first")
    call_later = fields.Boolean('Call Later', related="lead_stage_id.call_later")
    no_answer = fields.Boolean('No Answer', related="lead_stage_id.no_answer")
    qualified = fields.Boolean('Qualified', related="lead_stage_id.qualified")
    unqualified = fields.Boolean('Unqualified', related="lead_stage_id.unqualified")
    qualified_limited_budget = fields.Boolean('Qualified (Limited Budget)', related="lead_stage_id.qualified_limited_budget")
    follow_up = fields.Boolean('Follow Up', related="lead_stage_id.follow_up")
    locked = fields.Boolean()
    is_conflict_unit = fields.Boolean()
    conflict_opp = fields.Many2one('crm.lead', string='Parent Conflict Opportunity')
    conflict_opp_ids = fields.Many2many('crm.lead', 'opp_rel_conflict_id', 'opp_id', 'conflict_id',
                                        string='Conflict Opportunities')
    commission_ids = fields.One2many('commission.commission', 'opportunity_id', compute='compute_person_hierarchy',
                                     store=True, readonly=False)
    gender = fields.Selection([('male', 'Male'), ('female', 'Female')])
    marital_status = fields.Selection([('single', 'Single'),
                                       ('married', 'Married'),
                                       ('divorced', 'Divorced'),
                                       ('widowed', 'Widowed')])

    num_of_childrens = fields.Integer(string='Number Of Children')

    is_qualified = fields.Boolean(compute='check_qualified_stage')
    is_unqualified = fields.Boolean(related='lead_stage_id.unqualified', readonly=True)
    is_locked = fields.Boolean(related='lead_stage_id.locked', readonly=True)
    is_follow_up = fields.Boolean(related='lead_stage_id.follow_up', readonly=True)
    qualified_comment = fields.Text()
    user_id = fields.Many2one(
        'res.users', string='Salesperson', default=lambda self: self.env.user,
        check_company=True, index=True, tracking=True, required=1, domain="[]")

    date_deadline = fields.Datetime(string='Expected Closing')

    # round_number = fields.Char()
    # round_date = fields.Datetime()
    last_message = fields.Char(compute='_compute_last_message', store=True, string="Last Activity")
    last_message_date = fields.Char(compute='_compute_last_message', store=True)
    last_message_datetime = fields.Datetime(compute='_compute_last_message', store=True, string="Last Activity Date")

    lead_country = fields.Char(string="Lead Country", compute="_compute_lead_country", store=True)

    no_answer_count = fields.Integer(string='No Answer Count', default=0)
    unqualified_count = fields.Integer(string='Unqualified Count', default=0)
    is_fresh = fields.Boolean(string='Fresh Lead', default=True)
    duplicate_tcr_number = fields.Integer(compute='_compute_duplicate_count')
    conflict_tcr_number = fields.Integer(compute='_compute_conflict_count')
    meeting_counter = fields.Integer(compute='_compute_meeting_count', store=True)
    reassigned = fields.Boolean()

    # Fields to track previous values
    previous_opp_stage_id = fields.Many2one('crm.stage', string='Previous Stage', readonly=True)
    previous_stage_id = fields.Many2one('lead.stage', string='Previous Stage', readonly=True)
    previous_user_id = fields.Many2one('res.users', string='Previous Salesperson', readonly=True)
    previous_sales_manager_id = fields.Many2one('res.users', string='Previous Sales Manager', readonly=True)
    previous_director_id = fields.Many2one('res.users', string='Previous Director', readonly=True)
    warning = fields.Char()
    duplicate_portal = fields.Boolean()
    record_creation = fields.Boolean()

    # Add fields to track previous unit status and the date of change
    can_edit_stage_history = fields.Boolean(compute='_compute_can_edit_stage_history')
    previous_stage = fields.Char(string='Previous Stage')
    stage_change_date = fields.Datetime(string='Stage Change Date')

    # seller_sales_person = fields.Many2one('res.users', related="unit_id.seller_sales_person")
    # seller_team_leader = fields.Many2one('res.users', related="unit_id.seller_team_leader")
    # seller_sales_manager = fields.Many2one('res.users', related="unit_id.seller_sales_manager")
    # seller_sales_director = fields.Many2one('res.users', related="unit_id.seller_sales_director")
    # seller_purpose_sale_price = fields.Float(related="unit_id.seller_purpose_sale_price")
    # seller_purpose_rent_price = fields.Float(related="unit_id.seller_purpose_rent_price")
    # seller_client_name = fields.Char(related="unit_id.seller_client_id.name")
    # seller_client_phone = fields.Char(related="unit_id.seller_client_phone")
    # seller_client_extra_phone = fields.Char(related="unit_id.seller_client_extra_phone")

    job_title = fields.Char(related="user_id.job_title")
    team_leader_title = fields.Char(related="team_leader.job_title")
    sales_manager_title = fields.Char(related="sales_manager.job_title")
    sales_director_title = fields.Char(related="director.job_title")
    reopen_reason = fields.Char()
    collected_date = fields.Date()
    confirmed_date = fields.Date()
    achievement_date = fields.Date(string='Achievement Date')

    is_personal_lead = fields.Boolean(string='Personal Lead', default=False)

    reservation_ids = fields.One2many(
        'real.estate.sale.reservation',
        'opportunity_id',
        string='Reservations'
    )

    reservation_count = fields.Integer(
        string='Reservation Count',
        compute='_compute_reservation_count'
    )

    contract_ids = fields.One2many(
        'sale.proposal',
        'opportunity_id',
        string='Contracts'
    )

    contract_count = fields.Integer(
        string='Contract Count',
        compute='_compute_contract_count'
    )

    unit_hold_expiry_date = fields.Datetime(string="Hold Expiry Date", tracking=True, compute="_compute_unit_hold_expiry")
    unit_hold_start_date = fields.Datetime(string="Hold Start Date", tracking=True, readonly=True)

    @api.depends('unit_hold_start_date')
    def _compute_unit_hold_expiry(self):
        # Fetch the current duration from settings
        duration = int(self.env['ir.config_parameter'].sudo().get_param('crm.crm_unit_hold_duration', default=24))
        for lead in self:
            if lead.unit_hold_start_date:
                lead.unit_hold_expiry_date = lead.unit_hold_start_date + timedelta(hours=duration)
            else:
                lead.unit_hold_expiry_date = False

    @api.depends('reservation_ids')
    def _compute_reservation_count(self):
        for lead in self:
            lead.reservation_count = len(lead.reservation_ids)

    @api.depends('contract_ids')
    def _compute_contract_count(self):
        for lead in self:
            lead.contract_count = len(lead.contract_ids)

    @api.depends('is_cancel')
    def cal_cancellation_date(self):
        for rec in self:
            if rec.is_cancel:
                rec.opp_cancellation_date = rec.env.cr.now()
            else:
                rec.opp_cancellation_date = False

    @api.depends("phone")
    def _compute_lead_country(self):
        for lead in self:
            lead.lead_country = False
            if lead.phone:
                phone_code = self._extract_phone_code(lead.phone)
                if phone_code:
                    country = self.env["res.country"].search([("phone_code", "=", phone_code)], limit=1)
                    lead.lead_country = country.name if country else False

    def _extract_phone_code(self, phone):
        """Extracts the country code from a phone number."""
        match = re.match(r"^\+(\d+)", phone)
        return int(match.group(1)) if match else None

    @api.depends('lead_stage_id')
    def check_qualified_stage(self):
        for rec in self:
            if rec.lead_stage_id.qualified:
                rec.is_qualified = True
            else:
                rec.is_qualified = False

    hoppies = fields.Char()

    @api.depends('user_id')
    def _compute_first_assignment_date(self):
        for lead in self:
            if not lead.first_assignment_date and lead.user_id:
                lead.first_assignment_date = self.env.cr.now()

    # @api.constrains('sales_volume', 'type')
    # def _check_sales_volume(self):
    #     for record in self:
    #         if record.type == 'opportunity' and record.sales_volume <= 0:
    #             raise ValidationError("The Sales Volume must be greater than zero.")

    def action_match_lead_specification_with_units(self):
        Units = self.env['broker.unit']
        domain = self._build_domain()
        unit_ids = Units.search(domain)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Units',
            'res_model': 'broker.unit',
            'view_mode': 'list,form',
            'domain': [('id', 'in', unit_ids.ids)]
        }

    def _build_domain(self):
        domain = []
        self._add_price_domain(domain)
        self._add_destination_domain(domain)
        return domain

    def _add_destination_domain(self, domain):
        if self.dest_country_id:
            domain.append(('country_id', '=', self.dest_country_id.id))
        if self.governorate_id:
            domain.append(('governorate_id', '=', self.governorate_id.id))
        if self.dest_city_id:
            domain.append(('city_id', '=', self.dest_city_id.id))
        if self.neighborhood_id:
            domain.append(('neighborhood_id', '=', self.neighborhood_id.id))

    def _add_price_domain(self, domain):
        if self.min_price:
            if self.interested_in == 'buy':
                domain.append(('sale_price', '>=', self.min_price))
            else:
                domain.append(('rent_price', '>=', self.min_price))
        if self.max_price:
            if self.interested_in == 'buy':
                domain.append(('sale_price', '<=', self.max_price))
            else:
                domain.append(('rent_price', '<=', self.max_price))

    def action_set_lost(self, **additional_values):
        """ Lost semantic: probability = 0 or active = False """
        if self.type == 'lead':
            additional_values['lead_stage_id'] = self.env.ref('arkzayed_18_realestate_developer_crm.stage_unqualified').id
        if self.type == 'opportunity':
            additional_values['stage_id'] = self.env.ref('arkzayed_18_realestate_developer_crm.stage_lead6').id
        if additional_values:
            self.write(dict(additional_values))
        return True

    def toggle_active(self):
        """ Override toggle_active method to set state to 'new' when lead is restored """
        # Get the current active state before toggling
        was_archived = not self.active

        # Call super first to toggle the active state
        result = super(CrmLead, self).toggle_active()

        # If this was an archived lead being restored (activated)
        if self.type == 'lead' and was_archived and self.active:
            self.write({'lead_stage_id': self.env.ref('arkzayed_18_realestate_developer_crm.stage_new').id})

        return result

    @api.model
    def _get_allowed_step_back_groups(self):
        """Groups allowed to move qualified leads back to previous stages"""
        return [
            'arkzayed_18_realestate_developer_crm.sales_manager_group',  # Sales Manager
            'lead_admin_group',  # Lead Admin
            'operation_manager_group',  # Sales Sector Manager team
            'sales_team.group_sale_salesman_all_leads'  # Team Leader
        ]

    def _check_qualified_step_back_rights(self, new_stage):
        """
        Check if the user has rights to move a qualified lead back to a previous stage
        Returns True if the user has the right, raises AccessError otherwise
        """
        # If user is admin (has access rights management), allow all operations
        if self.env.user.has_group('base.group_system'):
            return True

        for group in self._get_allowed_step_back_groups():
            if self.env.user.has_group(group):
                return True

        raise AccessError(_(
            "Only Sales Managers, Lead Admins and Operations team members can move qualified leads back to previous stages."
        ))

    def _get_next_sales_team(self):
        """
        Get the next seles team based on sorted team_id ids
        if the current team_id was the last one, it will return the first team in the list
        """
        teams = self.env['crm.team'].sudo().search(['|', ('company_id', '=', self.env.company.id), ('company_id', '=', False)], order='id asc')
        if not teams:
            raise UserError("you need to select the team that the auto assignment start from")

        current_index = next((index for (index, d) in enumerate(teams) if d.is_current_team == True), -1)
        if current_index == -1:
            raise UserError("you need to select the team that the auto assignment start from")
        next_index = (current_index + 1) % len(teams)
        next_team = teams[next_index]
        current_team = teams[current_index]
        current_team.is_current_team = False
        next_team.is_current_team = True


        return current_team


    def handle_inactivity(self):
        """
        This method runs hourly and reassigns leads inactive for 48+ hours.
        """
        now = fields.Datetime.now()
        limit_48h_ago = now - timedelta(hours=48)

        leads = self.search([('type', '=', 'lead'),
                             ('is_qualified', '=', False),
                             ('is_unqualified', '=', False),
                             ('is_locked', '=', False),
                             ('is_follow_up', '=', False),
                             ('is_personal_lead', '=', False),
                             ('last_updated_date', '<=', limit_48h_ago),
                             ])
        for lead in leads:

            # Get the next team and next user

            next_team = lead._get_next_sales_team()
            next_user = next_team._get_next_sales_person() if next_team else False

            if next_user:
                # Update lead assignment
                lead.write({
                    'team_id': next_team.id,
                    'user_id': next_user.id,
                })

                # Post a chatter message

                lead.message_post(
                    body=(
                        f"Lead reassigned after 48h inactivity. "
                        f"New Team: {next_team.name}, New Salesperson: {next_user.name}"
                    ),
                    subtype_xmlid='mail.mt_comment'
                )


    def write(self, vals):
        # Check if user belongs to any of the restricted groups (before any other logic)
        self._check_restricted_fields(vals)

        # update last_updated_date if description is changed , or user_id is changed
        if 'description' in vals or 'user_id' in vals:
            vals['last_updated_date'] = fields.Datetime.now()

        # Add check for qualified leads being moved back
        if 'lead_stage_id' in vals:
            new_stage_id = vals['lead_stage_id']
            new_stage = self.env['lead.stage'].browse(new_stage_id)

            for record in self:
                # If moving from qualified stage to non-qualified stage
                if record.qualified and not new_stage.qualified:
                    record._check_qualified_step_back_rights(new_stage)

        # Add counter logic for No Answer and Unqualified stages
        if 'lead_stage_id' in vals:
            for record in self:
                # Only proceed if the stage is actually changing
                if vals.get('lead_stage_id') and vals.get('lead_stage_id') != record.lead_stage_id.id:
                    new_stage = self.env['lead.stage'].browse(vals['lead_stage_id'])

                    # If moving to No Answer stage
                    if new_stage.no_answer:
                        vals['no_answer_count'] = record.no_answer_count + 1

                    # If moving to Unqualified stage
                    if new_stage.unqualified:
                        vals['unqualified_count'] = record.unqualified_count + 1

        # Handle achievement_date when reservation_date or contracted_date is set
        if 'reserved_date' in vals or 'contracted_date' in vals:
            for record in self:
                # Only set achievement_date if it's not already set (first achievement wins)
                if not record.achievement_date:
                    achievement_date = None

                    # Priority 1: If reserved_date is being set and has a value
                    if 'reserved_date' in vals and vals['reserved_date']:
                        achievement_date = vals['reserved_date']

                    # Priority 2: If contracted_date is being set and has a value (and no reserved_date)
                    elif 'contracted_date' in vals and vals['contracted_date'] and not record.reserved_date:
                        achievement_date = vals['contracted_date']

                    # Set the achievement_date if we determined one
                    if achievement_date:
                        vals['achievement_date'] = achievement_date

        # Stage-related validations and updates
        if 'stage_id' in vals:
            has_finance_group = self.env.user.has_group('arkzayed_18_realestate_developer_crm.finance_group')
            stages_allowed_for_finance = [
                self.env.ref('arkzayed_18_realestate_developer_crm.stage_lead7').id,
                self.env.ref('arkzayed_18_realestate_developer_crm.stage_lead8').id
            ]
            if vals.get('stage_id') in stages_allowed_for_finance and not has_finance_group:
                raise ValidationError("Only finance can move lead to this stage")
            # Track the previous unit status
            self.previous_stage = self.stage_id.name
            # Track the date of the change
            self.stage_change_date = fields.Datetime.now()

            # Handle achievement_date when stage changes
            for record in self:
                # Only set achievement_date if it's not already set
                if not record.achievement_date:
                    stage = self.env['crm.stage'].browse(vals['stage_id'])
                    achievement_date = None

                    # If moving to reservation stage and reserved_date exists
                    if stage.is_reserved and record.reserved_date:
                        achievement_date = record.reserved_date

                    # If moving to contract stage and contracted_date exists (and no reserved_date)
                    elif stage.is_contract and record.contracted_date and not record.reserved_date:
                        achievement_date = record.contracted_date

                    # Set the achievement_date if we determined one
                    if achievement_date:
                        vals['achievement_date'] = achievement_date

            if vals.get('stage_id') and self.unit_id:
                stage = self.env['crm.stage'].browse(vals['stage_id'])
            if vals.get('stage_id') == self.env.ref('arkzayed_18_realestate_developer_crm.stage_lead7').id:
                if not self.collected_date and not vals.get('collected_date'):
                    raise ValidationError("Collected date is required")
                self.get_unit_status()
            if vals.get('stage_id') == self.env.ref('arkzayed_18_realestate_developer_crm.stage_lead8').id:
                if not self.confirmed_date and not vals.get('confirmed_date'):
                    raise ValidationError("Confirmed date is required")
                self.get_unit_status()
            if self.type == 'opportunity' and vals.get('stage_id') < self.stage_id.id and self.is_restricted_user():
                # prevent back to previous state
                raise ValidationError("You cann\'t return back stage")
            if vals.get('stage_id') in [self.env.ref('arkzayed_18_realestate_developer_crm.stage_lead6').id]:
                if self.lost_reason_id and 'lost_reason_id' not in vals:
                    raise ValidationError("Reason to cancel is required")
                self.cancellation_approver = self.env.user.partner_id.id
                self.unit_id.unit_status = 'available'
            if (self.type == 'opportunity' and not self.reopen_reason and 'reopen_reason' not in vals
                    and vals.get('stage_id') in [self.env.ref('arkzayed_18_realestate_developer_crm.stage_lead5').id]):
                if not has_finance_group:
                    raise ValidationError("Only finance can move lead to this stage")
                raise ValidationError("Reopen Reason is required")
            vals['previous_opp_stage_id'] = self.stage_id
        # Lead stage validations
        if 'lead_stage_id' in vals:
            if not self.env.user.has_group('arkzayed_18_realestate_developer_crm.lead_admin_group') and vals.get(
                    'lead_stage_id') == self.env.ref('arkzayed_18_realestate_developer_crm.stage_locked').id:
                raise ValidationError("Only admin can lock lead")
            if vals.get('lead_stage_id') == self.env.ref('arkzayed_18_realestate_developer_crm.stage_qualified').id:
                # \
            #         or vals.get('lead_stage_id') == self.env.ref(
            #     'arkzayed_18_realestate_developer_crm.stage_qualified_limited_budget').id:
                self.validate_qualified_stage_backend(vals)
        # Lock validations for each record
        for record in self:
            user = self.env.user
            if not user.has_group(
                    'arkzayed_18_realestate_developer_crm.operation_manager_group') and not record.duplicate_portal and not record.record_creation:
                if record.lead_stage_id.locked:
                    raise UserError('You cannot edit a locked lead')
                if record.stage_id.is_cancel and 'locked' not in vals:
                    raise UserError('You cannot edit a locked lead')
            if 'lead_stage_id' in vals:
                if vals.get('lead_stage_id') == self.env.ref('arkzayed_18_realestate_developer_crm.stage_unqualified').id:
                    if not record.lost_reason_id and not vals.get('lost_reason_id'):
                        raise ValidationError("Cancel Reason Is Required")
        # self.validate_required_fields(vals)
        res = super(CrmLead, self.sudo()).write(vals)
        # Update unit's customer_id when unit_id or partner_id changes
        if res:
            if 'unit_id' in vals:
                for record in self:
                    if record.unit_id and record.partner_id:
                        record.unit_id.sudo().write({'customer_id': record.partner_id.id})
            elif 'partner_id' in vals:
                for record in self:
                    if record.unit_id:
                        record.unit_id.sudo().write({'customer_id': record.partner_id.id})

        # If salesperson is changed, remove all followers and add only the new salesperson
        if res and vals.get('user_id'):
            for record in self:
                # Get the new salesperson's partner_id
                new_salesperson = self.env['res.users'].browse(vals.get('user_id'))
                # Remove all existing followers
                followers = self.env['mail.followers'].sudo().search([
                    ('res_model', '=', 'crm.lead'),
                    ('res_id', '=', record.id)
                ])
                if followers:
                    followers.sudo().unlink()
                # Add new salesperson as follower
                if new_salesperson and new_salesperson.partner_id:
                    record.message_subscribe([new_salesperson.partner_id.id])
        # Handle opportunity sequence
        if res:
            for record in self:
                if vals.get('type') == 'opportunity':
                    record.opportunity_sequence = self.env['ir.sequence'].next_by_code('crm.opportunity') or _(
                        'New Opportunity')
        return res

    def get_unit_status(self):
        if self.interested_in == 'rent':
            self.unit_id.unit_status = 'rented'
        elif  self.interested_in in ['buy','sell']:
            self.unit_id.unit_status = 'sold'

    def _compute_is_sales_manager(self):
        for rec in self:
            rec.is_sales_manager = rec.user_id.sale_team_id.user_id.id == self.env.user.id

    def lead_cancellation(self):
        self.is_lead_cancelled = True

    @api.onchange('cancellation_approver')
    def check_if_has_cancel_approval(self):
        current_user = self.env.user
        for rec in self:
            if current_user == rec.cancellation_approver.user_id:
                rec.has_auth_approval = True
            else:
                rec.has_auth_approval = False

    @api.model
    def create(self, vals):
        # Set lead_stage_id to first stage
        vals['lead_stage_id'] = self.env['lead.stage'].search([('first', '=', True)], limit=1).id

        # Handle unit number validation and conflict detection
        unit_number_opp_list = [vals.get('unit_number')]
        unit_number_opp_list = list(filter(None, unit_number_opp_list))
        current_sales_person = vals.get('user_id')

        if current_sales_person:
            duplicated_opp = self.env['crm.lead'].search(
                [('unit_number', 'in', unit_number_opp_list), ('user_id', '=', current_sales_person)])
            conflict_opp = self.env['crm.lead'].search_count(
                [('unit_number', 'in', unit_number_opp_list), ('user_id', '!=', current_sales_person)])
            conflict_object = self.env['crm.lead'].search(
                [('unit_number', 'in', unit_number_opp_list), ('user_id', '!=', current_sales_person)])

            if duplicated_opp:
                raise UserError('There is the same Unit Number For the sama Agent')
            elif conflict_opp:
                vals['is_conflict_unit'] = True
                for o in conflict_object:
                    vals['conflict_opp_ids'] = [(4, o.id)]

                conflict_object.update({
                    'is_conflict_unit': True,
                })

        # Format phone number
        if vals.get('phone'):
            vals['phone'] = self._phone_format(
                number=vals.get('phone'),
                country=vals.get('country_id'),
                force_format='INTERNATIONAL',
                raise_exception=True
            )

        # Handle duplicate detection
        from_portal = 0
        if vals.get('duplicate_portal'):
            # the duplicate_portal is true if already duplicate from portal creation validation
            from_portal = 1
        vals, warn_user = self._handle_number_duplication(vals, None, from_portal)

        # Set lead or opportunity sequence
        if vals.get('type') == 'lead' and vals.get('lead_sequence', _("New")) == _("New"):
            vals['lead_sequence'] = self.env['ir.sequence'].next_by_code('crm.lead') or _('New Lead')
        elif vals.get('type') == 'opportunity' and vals.get('opportunity_sequence', _("New")) == _("New"):
            vals['opportunity_sequence'] = self.env['ir.sequence'].next_by_code('crm.opportunity') or _(
                'New Opportunity')

        # if lead was assigned to a sales person then set last_updated_date to now
        if not vals.get('user_id') or vals.get('user_id'):
            # check if is_personal_lead is true , if it is then prevent the auto assignement
            if not vals.get('is_personal_lead'):
                # Get the next team and next user
                next_team = self._get_next_sales_team()
                next_user = next_team._get_next_sales_person() if next_team else self.env.user
                vals['user_id'] = next_user.id
                vals['team_id'] = next_team.id
                vals['last_updated_date'] = fields.Datetime.now()

        # Create the record
        res = super().create(vals)

        # Update unit's customer_id if both unit_id and partner_id are set
        if res.unit_id and res.partner_id:
            print(vals.get('lead_sequence'))
            if vals.get('type') == 'opportunity':
                res.unit_id.sudo().write({'customer_id': res.partner_id.id})

        # Show warning notification if needed
        if warn_user:
            self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification', {
                'type': 'danger',
                'title': _("Warning"),
                'message': _("You submitted a duplicate lead, please contact Operations Team!"),
            })
            internal_message = []
            old_user_id_obj = self.env['res.users'].browse(current_sales_person)
            internal_message.append(f'This lead is duplicated and coming from ({old_user_id_obj.name})'
                                    f' and has assigned to the duplicate tracker user')
            message = '\n'.join(internal_message)
            res.message_post(body=f'{message}')

        return res

    def reassign_leads(self, user_id):
        self = self.sudo()
        if not self:
            raise UserError('Please Select a Lead')
        if not user_id:
            raise UserError('Please Select a User')
        if self.has_reassign_auth or self.team_id.user_id.id == self.env.user.id:
            for rec in self:
                rec.user_id = user_id
        else:
            raise UserError('You are not allowed to reassign leads')

    def state_to_unqualified_state(self):
        self.ensure_one()
        if self.lost_reason_id:
            self.lead_stage_id = self.env.ref('arkzayed_18_realestate_developer_crm.stage_unqualified').id
            return True

        # If reason is not provided, open a wizard to collect it
        return {
            'name': 'Unqualify Lead',
            'type': 'ir.actions.act_window',
            'res_model': 'crm.lead.unqualified.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lead_id': self.id,
            }
        }

    def action_call_later(self):
        call_activity_object = self.env['mail.activity.type'].search([('name', '=', 'Call')])
        self.call_later = True
        return {
            'type': 'ir.actions.act_window',
            'name': 'Schedule Activity',
            'res_model': 'mail.activity',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_id': self.id,
                'default_res_model': self._name,
                'default_activity_type_id': call_activity_object.id,
                'from_crm_call_later': True
            },
        }

    def action_no_answer(self):
        for rec in self:
            rec.lead_stage_id = self.env.ref('arkzayed_18_realestate_developer_crm.stage_no_answer').id
            rec.last_updated_date = fields.Datetime.now()

    def action_qualified_lead(self):
        self.ensure_one()

        # Check if all required fields are filled
        required_fields_filled = all([
            self.qualified_comment,
            self.priority,
            self.unit_type,
            self.finish_type,
            self.min_area > 0,
            self.max_area > 0,
            self.min_price > 0,
            self.max_price > 0
        ])

        # If all required fields are filled, directly qualify the lead
        if required_fields_filled:
            self.write({
                'lead_stage_id': self.env.ref('arkzayed_18_realestate_developer_crm.stage_qualified').id
            })
            return True

        # Otherwise, open the wizard to collect missing information
        return {
            'name': 'Qualify Lead',
            'type': 'ir.actions.act_window',
            'res_model': 'qualified.stage.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lead_id': self.id,
                'default_priority': self.priority or '',
                'default_unit_type': self.unit_type or False,
                'default_finish_type': self.finish_type or False,
                'default_min_area': self.min_area or 0.0,
                'default_max_area': self.max_area or 0.0,
                'default_min_price': self.min_price or 0.0,
                'default_max_price': self.max_price or 0.0,
                'default_qualified_comment': self.qualified_comment or '',
            }
        }

    def action_qualified_limited_budget_lead(self):
        self.ensure_one()

        # Check if all required fields are filled
        required_fields_filled = all([
            self.qualified_comment,
            self.priority,
            self.unit_type,
            self.finish_type,
            self.min_area > 0,
            self.max_area > 0,
            self.min_price > 0,
            self.max_price > 0
        ])

        # If all required fields are filled, directly qualify the lead
        if required_fields_filled:
            self.write({
                'lead_stage_id': self.env.ref('arkzayed_18_realestate_developer_crm.stage_qualified_limited_budget').id
            })
            return True

        # Otherwise, open the wizard to collect missing information
        return {
            'name': 'Qualify (Limited Budget) Lead',
            'type': 'ir.actions.act_window',
            'res_model': 'qualified.stage.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lead_id': self.id,
                'default_priority': self.priority or '',
                'default_unit_type': self.unit_type or False,
                'default_finish_type': self.finish_type or False,
                'default_min_area': self.min_area or 0.0,
                'default_max_area': self.max_area or 0.0,
                'default_min_price': self.min_price or 0.0,
                'default_max_price': self.max_price or 0.0,
                'default_qualified_comment': self.qualified_comment or '',
                'limited_budget': True
            }
        }

    def action_follow_up_lead(self):
        for rec in self:
            rec.lead_stage_id = self.env.ref('arkzayed_18_realestate_developer_crm.stage_follow_up').id

    def action_unlock_lead(self):
        for rec in self:
            rec.lead_stage_id = self.env.ref('arkzayed_18_realestate_developer_crm.stage_new').id
            rec.locked = False
            rec.last_updated_date = fields.Datetime.now()


    def action_lock_lead(self):
        for rec in self:
            rec.lead_stage_id = self.env.ref('arkzayed_18_realestate_developer_crm.stage_locked').id
            rec.locked = True


    @api.constrains('mobile', 'phone', 'phone1', 'phone2', 'phone3', 'phone4')
    def _constraint_on_phones(self):
        for rec in self:
            if not (rec.mobile or rec.phone or rec.phone1 or rec.phone2 or rec.phone3 or rec.phone4):
                raise ValidationError("At least one phone number must be filled in.")

            for phone in [rec.mobile, rec.phone, rec.phone1, rec.phone2, rec.phone3, rec.phone4]:
                rec._phone_format(number=phone, country=rec.country_id, force_format='INTERNATIONAL',
                                  raise_exception=True)

    @api.onchange('project_id')
    def _onchange_project(self):
        if self.project_id:
            self.developer_id = self.project_id.developer_id.id
            self.dest_country_id = self.project_id.country_id.id
            self.dest_city_id = self.project_id.city_id.id
            self.governorate_id = self.project_id.governorate_id.id

    @api.depends('lead_sequence', 'opportunity_sequence')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.lead_sequence if rec.type == 'lead' else rec.opportunity_sequence

    @api.onchange('reservation_price', 'contract_price')
    def _onchange_sales_volume(self):
        for rec in self:
            if rec.contract_price == 0:
                rec.sales_volume = rec.reservation_price
            else:
                rec.sales_volume = rec.contract_price

    @api.depends('phone2', 'phone3', 'phone4', 'phone', 'mobile', 'phone1')
    def _compute_potential_lead_duplicates(self):
        """ Override potential lead duplicates computation to be more efficient
        with high lead volume.
        Criterions:
          * email domain exact match;
          * phone_sanitized exact match;
          * same commercial entity;
        """
        SEARCH_RESULT_LIMIT = 21

        def return_if_relevant(model_name, domain):
            """ Returns the recordset obtained by performing a search on the provided
            model with the provided domain if the cardinality of that recordset is
            below a given threshold (i.e: `SEARCH_RESULT_LIMIT`). Otherwise, returns
            an empty recordset of the provided model as it indicates search term
            was not relevant.
            Note: The function will use the administrator privileges to guarantee
            that a maximum amount of leads will be included in the search results
            and transcend multi-company record rules. It also includes archived
            records. Idea is that counter indicates duplicates are present and
            the lead could be escalated to managers.
            """
            model = self.env[model_name].sudo().with_context(active_test=False)
            res = model.search(domain, limit=SEARCH_RESULT_LIMIT)
            return res if len(res) < SEARCH_RESULT_LIMIT else model

        for lead in self:
            duplicate_lead_ids = self.env['crm.lead']

            if lead.email_from:
                res = self.env['crm.lead'].sudo().search([('email_from', '=', lead.email_from)])
                if len(res) != 1:
                    duplicate_lead_ids |= res

            # matching the local phones
            if lead.phone:
                res = self.env['crm.lead'].sudo().search(
                    ['|', '|', ('phone', '=', lead.phone), ('mobile', '=', lead.phone), ('phone1', '=', lead.phone)])
                if len(res) != 1:
                    duplicate_lead_ids |= res
            if lead.mobile:
                res = self.env['crm.lead'].sudo().search(
                    ['|', '|', ('phone', '=', lead.mobile), ('mobile', '=', lead.mobile), ('phone1', '=', lead.mobile)])
                if len(res) != 1:
                    duplicate_lead_ids |= res
            if lead.phone1:
                res = self.env['crm.lead'].sudo().search(
                    ['|', '|', ('phone', '=', lead.phone1), ('mobile', '=', lead.phone1), ('phone1', '=', lead.phone1)])
                if len(res) != 1:
                    duplicate_lead_ids |= res

            # matching the international phones
            if lead.phone2:
                # Normalize and sanitize phone2
                sanitized_phone2 = lead.phone2.strip().replace(' ', '').replace('-', '')
                if sanitized_phone2.startswith('+'):
                    # Include both with and without the `+` in search
                    res = self.env['crm.lead'].sudo().search(
                        ['|', '|',
                         ('phone2', 'in', [sanitized_phone2, sanitized_phone2.lstrip('+')]),
                         ('phone3', 'in', [sanitized_phone2, sanitized_phone2.lstrip('+')]),
                         ('phone4', 'in', [sanitized_phone2, sanitized_phone2.lstrip('+')])])
                else:
                    res = self.env['crm.lead'].sudo().search(
                        ['|', '|',
                         ('phone2', '=', sanitized_phone2),
                         ('phone3', '=', sanitized_phone2),
                         ('phone4', '=', sanitized_phone2)])
                if len(res) != 1:
                    duplicate_lead_ids |= res

            if lead.phone3:
                # Normalize and sanitize phone3
                sanitized_phone3 = lead.phone3.strip().replace(' ', '').replace('-', '')
                if sanitized_phone3.startswith('+'):
                    res = self.env['crm.lead'].sudo().search(
                        ['|', '|',
                         ('phone2', 'in', [sanitized_phone3, sanitized_phone3.lstrip('+')]),
                         ('phone3', 'in', [sanitized_phone3, sanitized_phone3.lstrip('+')]),
                         ('phone4', 'in', [sanitized_phone3, sanitized_phone3.lstrip('+')])])
                else:
                    res = self.env['crm.lead'].sudo().search(
                        ['|', '|',
                         ('phone2', '=', sanitized_phone3),
                         ('phone3', '=', sanitized_phone3),
                         ('phone4', '=', sanitized_phone3)])
                if len(res) != 1:
                    duplicate_lead_ids |= res

            if lead.phone4:
                # Normalize and sanitize phone4
                sanitized_phone4 = lead.phone4.strip().replace(' ', '').replace('-', '')
                if sanitized_phone4.startswith('+'):
                    res = self.env['crm.lead'].sudo().search(
                        ['|', '|',
                         ('phone2', 'in', [sanitized_phone4, sanitized_phone4.lstrip('+')]),
                         ('phone3', 'in', [sanitized_phone4, sanitized_phone4.lstrip('+')]),
                         ('phone4', 'in', [sanitized_phone4, sanitized_phone4.lstrip('+')])])
                else:
                    res = self.env['crm.lead'].sudo().search(
                        ['|', '|',
                         ('phone2', '=', sanitized_phone4),
                         ('phone3', '=', sanitized_phone4),
                         ('phone4', '=', sanitized_phone4)])
                if len(res) != 1:
                    duplicate_lead_ids |= res

            lead.duplicate_lead_ids = duplicate_lead_ids + lead
            if duplicate_lead_ids:
                lead.duplicate_lead_count = len(duplicate_lead_ids)
            else:
                lead.duplicate_lead_count = 0

    def handle_approval(self):
        pass

    @api.constrains('lead_stage_id', 'min_area', 'max_area', 'min_price', 'max_price')
    def _check_values_when_qualified(self):
        for record in self:
            message = ''
            if record.qualified:
                if record.min_area <= 0:
                    message += 'Minimum area must be greater than zero when qualified.\n'
                if record.max_area <= 0:
                    message += 'Maximum area must be greater than zero when qualified.\n'
                if record.min_price <= 0:
                    message += 'Minimum price must be greater than zero when qualified.\n'
                if record.max_price <= 0:
                    message += 'Maximum price must be greater than zero when qualified.\n'
                if message:
                    raise ValidationError(message)

    def update_lead_info_portal(self, values):
        self.browse().check_access('write')
        for lead in self:
            lead_values = {
                'interested_in': values.get('interested_in') if values.get('interested_in') else False,
                'buying_type': values.get('buying_type') if values.get('buying_type') else False,
                # 'project_id': values.get('project_id') if values.get('project_id') else False,
                # 'developer_id': values.get('developer_id') if values.get('developer_id') else False,
                # 'dest_country_id': values.get('dest_country_id') if values.get('dest_country_id') else False,
                # 'governorate_id': values.get('governorate_id') if values.get('governorate_id') else False,
                # 'dest_city_id': values.get('dest_city_id') if values.get('dest_city_id') else False,
                'user_id': values.get('user_id') if values.get('user_id') else False,
                'follow_up_date': values.get('follow_up_date') if values.get('follow_up_date') else False,
                'sales_volume': values.get('sales_volume') if values.get('sales_volume') else False,
                'priority': values.get('priority') if values.get('priority') else False,
                'tag_ids': values.get('tag_ids') if values.get('tag_ids') else False,
            }
            lead_values = {k: v for k, v in lead_values.items() if v not in ['', False]}
            lead.write(lead_values)

    def update_lead_marketing_portal(self, values):
        self.browse().check_access('write')
        for lead in self:
            lead_values = {
                'campaign_id': values.get('campaign_id') if values.get('campaign_id') else False,
                # 'source_id': values.get('source_id') if values.get('source_id') else False,
                # 'medium_id': values.get('medium_id') if values.get('medium_id') else False,
                'date_deadline': values.get('date_deadline') if values.get('date_deadline') else False,
                'campaign_form_name': values.get('campaign_form_name') if values.get('campaign_form_name') else False,
                'media_buyer': values.get('media_buyer') if values.get('media_buyer') else False,
            }
            lead_values = {k: v for k, v in lead_values.items() if v not in ['', False, None]}
            lead.write(lead_values)

    def update_opp_marketing_portal(self, values):
        self.browse().check_access('write')
        for lead in self:
            lead_values = {
                'campaign_id': values.get('campaign_id') if values.get('campaign_id') else False,
                # 'source_id': values.get('source_id') if values.get('source_id') else False,
                # 'medium_id': values.get('medium_id') if values.get('medium_id') else False,
                'channel': values.get('channel') if values.get('channel') else False,
                'referred': values.get('referred') if values.get('referred') else False,
                'campaign_form_name': values.get('campaign_form_name') if values.get('campaign_form_name') else False,
                'media_buyer': values.get('media_buyer') if values.get('media_buyer') else False,
            }
            lead_values = {k: v for k, v in lead_values.items() if v not in ['', False]}
            lead.write(lead_values)

    def update_lead_preference_portal(self, values):
        self.browse().check_access('write')
        for lead in self:
            lead_values = {
                'place_preferences': values.get('place_preferences'),
                'furniture_type': values.get('furniture_type'),
                'ready_to_move': values.get('ready_to_move')
            }
            lead.write(lead_values)

    def update_unit_details(self, values):
        self.browse().check_access('write')
        for lead in self:
            unit_details = {
                'unit_type': values.get('unit_type') if values.get('unit_type') else False,
                'finish_type': values.get('finish_type') if values.get('finish_type') else False,
                'number_of_bedrooms': values.get('number_of_bedrooms') if values.get('number_of_bedrooms') else False,
                'number_of_bathrooms': values.get('number_of_bathrooms') if values.get(
                    'number_of_bathrooms') else False,
                'building_area': values.get('building_area') if values.get('building_area') else False,
                'garden_area': values.get('garden_area') if values.get('garden_area') else False,
                'land_area': values.get('land_area') if values.get('land_area') else False,
            }
            unit_details = {k: v for k, v in unit_details.items() if v not in [False, '']}
            lead.write(unit_details)

    def update_area_pricing(self, values):
        # self.browse().check_access('write')
        for lead in self:
            lead_values = {
                'min_price': values.get('min_price'),
                'max_price': values.get('max_price'),
                'min_area': values.get('min_area'),
                'max_area': values.get('max_area'),
            }
            lead.write(lead_values)

    def update_qualified_fields(self, values):
        for lead in self:
            lead_values = {
                'min_price': values.get('min_price'),
                'max_price': values.get('max_price'),
                'min_area': values.get('min_area'),
                'max_area': values.get('max_area'),
                'priority': values.get('priority'),
                'unit_type': values.get('unit_type'),
                'finish_type': values.get('finish_type'),
                'qualified_comment': values.get('qualified_comment'),
                'lead_stage_id': values.get('lead_stage_id'),
            }
            lead.write(lead_values)

    def update_lead_contact_portal(self, values):
        self.browse().check_access('write')
        for lead in self:
            lead_values = {
                # 'contact_name': values.get('contact_name'),
                # 'phone': values.get('phone'),
                'mobile': values.get('mobile'),
                'email_from': values.get('email_from'),
                'email_cc': values.get('email_cc'),
                'function': values.get('job_position'),
            }
            lead.write(lead_values)

    def update_payment_info_portal(self, values):
        """Update payment-related information for the opportunity"""
        self.browse().check_access('write')
        for opp in self:
            payment_values = {
                # 'payment_plan': values.get('payment_plan') if values.get('payment_plan') else False,
                # 'delivery_date': values.get('delivery_date') if values.get('delivery_date') else False,
                'reserved_date': values.get('reserved_date') if values.get('reserved_date') else False,
                'contracted_date': values.get('contracted_date') if values.get('contracted_date') else False,
                'down_payment': values.get('down_payment') if values.get('down_payment') else False,
                'eoi_amount': values.get('eoi_amount') if values.get('down_payment') else False,
                'reservation_price': values.get('reservation_price') if values.get('reservation_price') else False,
                'contract_price': values.get('contract_price') if values.get('contract_price') else False,
                'sales_volume': values.get('sales_volume') if values.get('sales_volume') else False,
            }
            payment_values = {k: v for k, v in payment_values.items() if v not in ["", False]}
            opp.write(payment_values)

    def update_extra_info_portal(self, values):
        """Update extra information for the opportunity"""
        self.browse().check_access('write')
        for lead in self:
            extra_values = {
                'date_open': values.get('date_open'),
                'unit_number': values.get('unit_number'),
            }
            lead.write(extra_values)

    def update_analysis(self, values):
        self.browse().check_access('write')
        for lead in self:
            analysis_values = {
                'date_closed': values.get('date_closed'),
                # 'unit_number': values.get('day_open'),
                # 'unit_number': values.get('day_close'),
            }
            lead.write(analysis_values)

    def update_phone_numbers(self, values):
        self.browse().check_access('write')
        for opp in self:
            phone_values = {
                'phone1': values.get('phone1') if values.get('phone1') else False,
                'phone2': values.get('phone2') if values.get('phone2') else False,
                'phone3': values.get('phone3') if values.get('phone3') else False,
                'phone4': values.get('phone4') if values.get('phone4') else False,
            }
            phone_values = {k: v for k, v in phone_values.items() if v not in ['', False]}
            opp.write(phone_values)

    def update_unqualified_reason(self, values):
        self.browse().check_access('write')
        lost_reason_id = values.get('lost_reason_id')
        if lost_reason_id:
            unqualified_values = {
                'lost_reason_id': int(lost_reason_id),
                'lead_stage_id': self.env.ref('arkzayed_18_realestate_developer_crm.stage_unqualified').id
            }
            self.write(unqualified_values)


    def update_unqualified_reason_opp(self, values):
        self.browse().check_access('write')
        lost_reason_id = values.get('lost_reason_id')
        if lost_reason_id:
            unqualified_values = {
                'lost_reason_id': int(lost_reason_id),
                'stage_id': self.env.ref('arkzayed_18_realestate_developer_crm.stage_lead6').id
            }
            self.write(unqualified_values)

    def update_qualified_comment(self, values):
        self.browse().check_access('write')
        qualified_values = {
            'qualified_comment': values.get('qualified_comment'),
        }
        self.write(qualified_values)

    def update_lead_call_later_portal(self, values):
        """Update Call Later for the Lead"""
        self.browse().check_access('write')
        for lead in self:
            call_later_values = {
                'activity_type_id': values.get('activity_type_id'),
                'activity_date_deadline': values.get('activity_date_deadline'),
                'lead_stage_id': self.env.ref('arkzayed_18_realestate_developer_crm.stage_call_later').id
            }
            user_activity = lead.sudo().activity_ids.filtered(lambda activity: activity.user_id == self.env.user)[:1]
            if values['activity_date_deadline']:
                if user_activity:
                    user_activity.sudo().write({
                        'activity_type_id': values.get('activity_type_id'),
                        'date_deadline': values.get('activity_date_deadline'),
                        'time_deadline': values.get('activity_time_deadline'),
                        'time_type': values.get('time_type'),
                        'summary': values.get('activity_summary'),
                    })
                else:
                    self.env['mail.activity'].sudo().create({
                        'res_model_id': self.env.ref('crm.model_crm_lead').id,
                        'res_id': lead.id,
                        'user_id': self.env.user.id,
                        'activity_type_id': values.get('activity_type_id'),
                        'date_deadline': values.get('activity_date_deadline'),
                        'time_deadline': values.get('activity_time_deadline'),
                        'time_type': values.get('time_type'),
                    })
            lead.sudo().write(call_later_values)

    def update_lead_activity_portal(self, values):
        """Update Call Later for the Lead"""
        self.browse().check_access('write')
        for lead in self:
            call_later_values = {
                'activity_type_id': values.get('activity_type_id'),
                'activity_date_deadline': values.get('activity_date_deadline'),
            }
            user_activity = lead.sudo().activity_ids.filtered(lambda activity: activity.user_id == self.env.user)[:1]
            if values['activity_date_deadline']:
                if user_activity:
                    user_activity.sudo().write({
                        'activity_type_id': values.get('activity_type_id'),
                        'date_deadline': values.get('activity_date_deadline'),
                        'time_deadline': values.get('activity_time_deadline'),
                        'time_type': values.get('time_type'),
                        'summary': values.get('activity_summary'),
                    })
                else:
                    self.env['mail.activity'].sudo().create({
                        'res_model_id': self.env.ref('crm.model_crm_lead').id,
                        'res_id': lead.id,
                        'user_id': self.env.user.id,
                        'activity_type_id': values.get('activity_type_id'),
                        'date_deadline': values.get('activity_date_deadline'),
                        'time_deadline': values.get('activity_time_deadline'),
                        'time_type': values.get('time_type'),
                    })
            lead.sudo().write(call_later_values)

    @property
    def has_reassign_auth(self):
        if self.env.user.has_group('sales_team.group_sale_salesman_all_leads') \
                or self.env.user.has_group('arkzayed_18_realestate_developer_crm.sales_manager_group') \
                or self.env.user.has_group('arkzayed_18_realestate_developer_crm.director_manager_group') \
                or self.env.user.has_group('arkzayed_18_realestate_developer_crm.operation_manager_group'):
            return True
        else:
            return False

    @api.depends('user_id', 'sales_ids', 'split_deal')
    def compute_person_hierarchy(self):
        """Compute commission hierarchy for sales opportunities."""
        for rec in self:
            if rec.type != 'opportunity':
                rec.commission_ids = []
                continue
            hierarchy_lines = self._get_hierarchy_lines(rec)
            rec.commission_ids = self._create_commission_commands(rec, hierarchy_lines)

    def _get_hierarchy_lines(self, record):
        """Get unique hierarchy lines for team members."""
        unique_users = set(self._get_team_users(record.user_id))
        if record.split_deal and record.sales_ids:
            for user in record.sales_ids:
                unique_users.update(self._get_team_users(user._origin))

        return filter(None, unique_users)

    def _get_team_users(self, user):
        """Get team users for a given user based on job level."""
        result = set()
        if user.job_level_id.is_sales_person:
            team = self.env['crm.team.member'].search([('user_id', '=', user.id)], limit=1).crm_team_id
            result.update([user, team.user_id, team.director_id, team.sales_manager_id])
        # elif user.job_level_id.is_team_leader:
        #     team = self.env['crm.team'].search([('user_id', '=', user.id)], limit=1)
        #     result.update([user, team.director_id, team.sales_manager_id])
        elif user.job_level_id.is_sales_manager:
            team = self.env['crm.team'].search([('sales_manager_id', '=', user.id)], limit=1)
            result.update([user, team.director_id])
        elif user.job_level_id.is_directory:
            result.add(user)
        return filter(None, result)

    def _create_commission_commands(self, record, hierarchy_lines):
        """Create commission commands for the given hierarchy lines."""
        unlink_cmds = [Command.unlink(line.id) for line in record.commission_ids]

        create_cmds = [
            Command.create({
                'opportunity_id': record.id,
                'employee_id': user.id,
            })
            for user in hierarchy_lines
        ]
        return unlink_cmds + create_cmds

    def update_split_deal(self, **vals):
        self.browse().check_access('write')
        for opp in self:
            split_deal_vals = {
                'split_deal': vals.get('split_deal'),
                'partner_ids': [(6, 0, vals.get('partner_ids'))] if vals.get('partner_ids') else None,
                'employee_ids': [(6, 0, vals.get('employee_ids'))] if vals.get('employee_ids') else None,
                'broker_ids': [(6, 0, vals.get('broker_ids'))] if vals.get('broker_ids') else None,
                'ambassador_ids': [(6, 0, vals.get('ambassador_ids'))] if vals.get('ambassador_ids') else None,
                'non_sales_ids': [(6, 0, vals.get('sales_ids'))] if vals.get('sales_ids') else None,
                'sales_ids': [(6, 0, vals.get('sales_ids'))] if vals.get('sales_ids') else None,
                'other': vals.get('other') if vals.get('other') else None,
            }
            split_deal_vals = {k: v for k, v in split_deal_vals.items() if v not in ('', None, [])}
            opp.write(split_deal_vals)

    def portal_lead_converted_to_opportunity(self, vals):
        comment = vals.get('comment')
        super().sudo().partner_interested(comment)
        stage_id = vals.get('stageId')
        buying_type = vals.get('buyingType')
        file_data = vals.get('file')
        attachment_field_name = self._get_attachment_field_name(stage_id)
        customer_data = vals.get('customerData')
        lead_values = {
            'is_converted': True,
            'stage_id': vals.get('stageId') if vals.get('stageId') else False,
            'buying_type': vals.get('buyingType') if vals.get('buyingType') else False,
            'eoi_amount': vals.get('eoiAmount') if vals.get('eoiAmount') else False,
            'reservation_price': vals.get('reservationPrice') if vals.get('reservationPrice') else False,
            'reserved_date': vals.get('reservedDate') if vals.get('reservedDate') else False,
            'contract_price': vals.get('contractPrice') if vals.get('contractPrice') else False,
            'contracted_date': vals.get('contractedDate') if vals.get('contractedDate') else False,
            'unit_number': vals.get('unitnumber') if vals.get('unitnumber') else False,
            'achievement_date': vals.get('reservedDate') if vals.get('reservedDate') else vals.get('contractedDate') if vals.get('contractedDate') else False,
        }
        lead_values = {k: v for k, v in lead_values.items() if v not in ["", False, None]}

        # Handle customer creation/assignment
        if customer_data['type'] == 'new':
            # Create new customer
            partner = self.env['res.partner'].sudo().create({
                'name': customer_data['name'],
                'email': customer_data['email'],
                'phone': customer_data['phone'],
                'customer_rank': 1,  # Mark as customer
                'is_customer': True
            })
            self.partner_id = partner.id
        else:
            # Assign existing customer
            self.partner_id = customer_data['id']

        # Handle attachment
        if file_data and attachment_field_name:
            self._save_attachment(file_data, attachment_field_name)

        # Update lead/opportunity
        self.write(lead_values)

    def _save_attachment(self, file_data, attachment_field_name):
        file_name = file_data.get('name')
        file_content = file_data.get('content')
        self.write({
            attachment_field_name: file_content,
            f"{attachment_field_name}_filename": file_name
        })

    def _get_attachment_field_name(self, stage_id):
        if self.env.ref('crm.stage_lead1').id == stage_id:
            return 'eoi_attachment'
        elif self.env.ref('crm.stage_lead2').id == stage_id:
            return 'reservation_attachment'
        elif self.env.ref('crm.stage_lead3').id == stage_id:
            return 'contract_attachment'

    def _handle_number_duplication(self, vals, warn_user=None, from_portal=None):
        numbers_list = []
        current_user_id = vals.get('user_id')
        user_obj = self.env['res.users'].browse(current_user_id)
        if current_user_id:
            for phone_field in ALL_PHONE_FIELDS:
                if vals.get(phone_field):
                    numbers_list.append(vals[phone_field])
            if numbers_list:
                domain = [
                    '&',
                    ('user_id', '!=', current_user_id),
                    '&',
                    ('locked', '=', False),
                    '|', '|', '|', '|', '|',
                    ('phone', 'in', numbers_list),
                    ('mobile', 'in', numbers_list),
                    ('phone1', 'in', numbers_list),
                    ('phone2', 'in', numbers_list),
                    ('phone3', 'in', numbers_list),
                    ('phone4', 'in', numbers_list),
                ]
                # self.env.cr.commit()
                duplicate_lead_ids = self.env['crm.lead'].with_context(
                    active_test=False,
                    prefetch_fields=False
                ).sudo().search(domain, order='id DESC')
                duplicity_user_obj = self.env['hr.employee'].sudo().search([('is_duplicity_tracker', '=', True)], limit=1)
                if duplicate_lead_ids and from_portal == 0 or from_portal == 1:
                    warn_user = 1
                    vals.update({
                        'lead_stage_id': self.env.ref('arkzayed_18_realestate_developer_crm.stage_locked').id,
                        'duplicate_number':True,
                        'locked': True,
                        'user_id': duplicity_user_obj.user_id.id if duplicity_user_obj else self.env.user.id,
                        'record_creation': True,
                    })
        return vals, warn_user


    def _clean_phone_number(self, number):
        """Standardize phone number format"""
        if not number:
            return False
        # Remove all non-digit characters
        cleaned = re.sub(r'\s+', '', str(number))
        # Add country-specific normalization if needed
        return cleaned

    def warn_user(self):
        return {
            'warning': {
                'title': 'Warning',
                'message': 'contact operation'
            }
        }

    # def validate_required_fields(self, vals):
    #     if vals.get('stage_id'):
    #         if vals.get('stage_id') == self.env.ref('crm.stage_lead1').id and not vals.get(
    #                 'eoi_attachment') and not self.eoi_attachment:
    #             raise UserError("EOI attachment is required.")
    #
    #         if vals.get('stage_id') == self.env.ref('crm.stage_lead2').id:
    #             reservation_state_required_fields = ['reservation_attachment', 'reservation_price', 'reserved_date']
    #             empty_fields = [field for field in reservation_state_required_fields if
    #                             not vals.get(field) and not getattr(self, field, None)]
    #             if empty_fields:
    #                 raise UserError(
    #                     f"{', '.join(empty_fields).replace('_', ' ').upper()} Fields is required to Reservation state")
    #         if vals.get('stage_id') == self.env.ref('crm.stage_lead3').id:
    #             contract_stage_required_fields = ['contract_attachment', 'contracted_date', 'contract_price']
    #             print(vals.get('buying_type'))
    #
    #             if vals.get('buying_type') and vals.get('buying_type') == 'primary' :
    #                 contract_stage_required_fields.append('unit_number')
    #             elif vals.get('buying_type') == None and self.buying_type == 'primary':
    #                 contract_stage_required_fields.append('unit_number')
    #
    #             empty_fields = [field for field in contract_stage_required_fields if
    #                             not vals.get(field) and not getattr(self, field, None)]
    #             if empty_fields:
    #                 raise UserError(
    #                     f"{', '.join(empty_fields).replace('_', ' ').upper()} Fields is required to Contract state")

    def update_call_later(self, vals):
        if vals.get('follow_up_date'):
            date_object = datetime.datetime.strptime(vals.get('follow_up_date'), '%m/%d/%Y').date()
            self.write({'follow_up_date': date_object})

    def validate_qualified_stage(self):
        message = ''
        if not self.priority \
                or not self.unit_type:
            message += 'Priority and Unit Type are required.\n'
        if not self.min_area \
                or not self.max_area \
                or not self.min_price \
                or not self.max_price:
            message += "Minimum and Maximum of (Area and Price) are required when qualified.\n"
        if not self.qualified_comment:
            message += "Qualified Comment is required when qualified.\n"
        return {
            'error': message
        }

    def validate_unqualified_stage(self):
        message = ''
        if not self.lost_reason_id:
            message += "Cancel Reason is required.\n"
        return {
            'error': message
        }

    def validate_qualified_stage_backend(self, vals):
        for opp in self:
            message = ''
            required_fields = [
                ('priority', 'Priority'),
                ('unit_type', 'Unit Type'),
                ('min_area', 'Minimum Area'),
                ('max_area', 'Maximum Area'),
                ('min_price', 'Minimum Price'),
                ('max_price', 'Maximum Price'),
                ('qualified_comment', 'Qualified Comment'),
            ]
            for field, field_name in required_fields:
                if not vals.get(field) and not getattr(opp, field, None):
                    message += f"{field_name} is required.\n"
            if message:
                raise UserError(message)

    def update_contact_info(self, vals):
        for opp in self:
            contact_info = {
                'partner_name': vals.get('partner_name') if vals.get('partner_name') else False,
                'website': vals.get('website') if vals.get('website') else False,
                # 'contact_name': vals.get('contact_name') if vals.get('contact_name') else False,
                'mobile': vals.get('mobile') if vals.get('mobile') else False,
            }
            contact_info = {k: v for k, v in contact_info.items() if v not in [False, '']}
            opp.write(contact_info)

    def update_sales_info(self, vals):
        for opp in self:
            sales_info = {
                'user_id': vals.get('user_id') if vals.get('user_id') else False,
                'priority': str(vals.get('priority')) if vals.get('priority') else None,
                'tag_ids': [(6, 0, vals.get('tag_ids'))] if vals.get('tag_ids') else False,
            }
            sales_info = {k: v for k, v in sales_info.items() if v not in [False, '']}
            opp.write(sales_info)

    def update_tracking_info(self, vals):
        for opp in self:
            tracking_info = {
                'company_id': vals.get('company_id') if vals.get('company_id') else False,
                'day_open': vals.get('day_open') if vals.get('company_id') else False,
                'day_close': vals.get('day_close') if vals.get('day_close') else False,
            }
            tracking_info = {k: v for k, v in tracking_info.items() if v not in ['', False]}
            opp.write(tracking_info)

    def update_address_info(self, vals):
        for opp in self:
            address_info = {
                'street': vals.get('street') if vals.get('street') else False,
                'street2': vals.get('street2') if vals.get('street2') else False,
                'city': vals.get('city') if vals.get('city') else False,
                'state_id': vals.get('state_id') if vals.get('state_id') else False,
                'country_id': vals.get('country_id') if vals.get('country_id') else False,
            }
            address_info = {k: v for k, v in address_info.items() if v not in ['', False]}
            # self.update_contact_details_from_portal(address_info)
            opp.write(address_info)

    def action_resequence(self):
        result = self.env['crm.lead'].sudo().search([])
        for record in sorted(result, key=lambda e: e['id']):
            record.lead_sequence = self.env['ir.sequence'].next_by_code('crm.lead')
            if record.type == 'opportunity':
                record.opportunity_sequence = self.env['ir.sequence'].next_by_code('crm.opportunity')

    @api.constrains('eoi_status_for_manager')
    def _check_eoi_manager_approval(self):
        for rec in self:
            if rec.eoi_status_for_manager and self.type == 'opportunity':
                if not self.env.user.has_group('arkzayed_18_realestate_developer_crm.approval_manager_group'):
                    raise UserError('You are not allowed to approve - only Manager can approve')

    @api.constrains('eoi_status_for_financial')
    def _check_eoi_financial_approval(self):
        for rec in self:
            if rec.eoi_status_for_financial and self.type == 'opportunity':
                if not self.env.user.has_group('arkzayed_18_realestate_developer_crm.financial_manager_group'):
                    raise UserError('You are not allowed to approve - only Financial Manager can approve')

    @api.constrains('eoi_status_for_operations')
    def _check_eoi_operations_approval(self):
        for rec in self:
            if rec.eoi_status_for_operations and self.type == 'opportunity':
                if not (self.env.user.has_group('arkzayed_18_realestate_developer_crm.operation_manager_group') ):
                        # or
                        # self.env.user.has_group('arkzayed_18_realestate_developer_crm.operation_executive_group')):
                    raise UserError('You are not allowed to approve - only Sales Sector Manager can approve')

    @api.constrains('reservation_status_for_manager')
    def _check_reservation_manager_approval(self):
        for rec in self:
            if rec.reservation_status_for_manager and self.type == 'opportunity':
                if not self.env.user.has_group('arkzayed_18_realestate_developer_crm.approval_manager_group'):
                    raise UserError('You are not allowed to approve - only Manager can approve')

    @api.constrains('reservation_status_for_financial')
    def _check_reservation_financial_approval(self):
        for rec in self:
            if rec.reservation_status_for_financial and self.type == 'opportunity':
                if not self.env.user.has_group('arkzayed_18_realestate_developer_crm.financial_manager_group'):
                    raise UserError('You are not allowed to approve - only Financial Manager can approve')

    @api.constrains('reservation_status_for_operations')
    def _check_reservation_operations_approval(self):
        for rec in self:
            if rec.reservation_status_for_operations and self.type == 'opportunity':
                if not (self.env.user.has_group('arkzayed_18_realestate_developer_crm.operation_manager_group') ):
                        # or
                        # self.env.user.has_group('arkzayed_18_realestate_developer_crm.operation_executive_group')):
                    raise UserError('You are not allowed to approve - only Sales Sector Manager can approve')

    @api.constrains('contract_status_for_manager')
    def _check_contract_manager_approval(self):
        for rec in self:
            if rec.contract_status_for_manager and self.type == 'opportunity':
                if not self.env.user.has_group('arkzayed_18_realestate_developer_crm.approval_manager_group'):
                    raise UserError('You are not allowed to approve - only Manager can approve')

    @api.constrains('contract_status_for_financial')
    def _check_contract_financial_approval(self):
        for rec in self:
            if rec.contract_status_for_financial and self.type == 'opportunity':
                if not self.env.user.has_group('arkzayed_18_realestate_developer_crm.financial_manager_group'):
                    raise UserError('You are not allowed to approve - only Financial Manager can approve')

    @api.constrains('contract_status_for_operations')
    def _check_contract_operations_approval(self):
        for rec in self:
            if rec.contract_status_for_operations and self.type == 'opportunity':
                if not (self.env.user.has_group('arkzayed_18_realestate_developer_crm.operation_manager_group')):
                        # or
                        # self.env.user.has_group('arkzayed_18_realestate_developer_crm.operation_executive_group')):
                    raise UserError('You are not allowed to approve - only Sales Sector Manager can approve')

    @api.depends('message_ids')
    def _compute_last_message(self):
        for rec in self:
            if rec.message_ids:
                message = rec.message_ids.sorted(lambda l: l.date, reverse=True)[:1]
                if message.subtype_id.name == 'Discussions':
                    html_text = message.body
                    rec.last_message = BeautifulSoup(html_text, "html.parser").get_text()
                    rec.last_message_date = message.date
                    rec.last_message_datetime = message.date

                else:
                    rec.last_message = 'No Messages'
                    rec.last_message_date = ''
                    rec.last_message_datetime = ''
            else:
                rec.last_message = 'No Messages'
                rec.last_message_date = ''
                rec.last_message_datetime = ''

    def action_conflict_tcr(self):
        conflict_leads = self.env['crm.lead'].search([
            # ('project_id', '=', self.project_id.id),
            # ('developer_id', '=', self.developer_id.id),
            ('type', '=', 'opportunity'),
            ('unit_number', '=', self.unit_number),
        ])
        return {
            'type': 'ir.actions.act_window',
            'name': 'Conflicts TCRs',
            'res_model': 'crm.lead',
            'view_mode': 'list,form',
            'domain': [('id', 'in', conflict_leads.ids)],
            'target': 'current',
        }

    @api.depends('project_id', 'developer_id', 'type', 'unit_number')
    def _compute_conflict_count(self):
        conflict_leads = self.env['crm.lead'].search([
            # ('project_id', '=', self.project_id.id),
            # ('developer_id', '=', self.developer_id.id),
            ('type', '=', 'opportunity'),
            ('unit_number', '=', self.unit_number),
        ])
        if conflict_leads:
            self.conflict_tcr_number = len(conflict_leads)
        else:
            self.conflict_tcr_number = 0

    def action_duplicate_tcr(self):
        duplicate_leads = self.env['crm.lead'].search([
            # ('project_id', '=', self.project_id.id),
            # ('developer_id', '=', self.developer_id.id),
            ('type', '=', 'opportunity'),
            ('unit_number', '=', self.unit_number),
            ('user_id', '=', self.user_id.id),
        ])
        return {
            'type': 'ir.actions.act_window',
            'name': 'Conflicts TCRs',
            'res_model': 'crm.lead',
            'view_mode': 'list,form',
            'domain': [('id', 'in', duplicate_leads.ids)],
            'target': 'current',
        }

    def _compute_duplicate_count(self):
        duplicate_leads = self.env['crm.lead'].search([
            # ('project_id', '=', self.project_id.id),
            # ('developer_id', '=', self.developer_id.id),
            ('type', '=', 'opportunity'),
            ('unit_number', '=', self.unit_number),
            ('user_id', '=', self.user_id.id),
        ])
        if duplicate_leads:
            self.duplicate_tcr_number = len(duplicate_leads)
        else:
            self.duplicate_tcr_number = 0


    @api.depends('activity_ids')
    def _compute_meeting_count(self):
        for record in self:
            meeting_activity_type = self.env.ref('mail.mail_activity_data_meeting', raise_if_not_found=False)
            if meeting_activity_type:
                for activity in record.activity_ids:
                    if activity.activity_type_id == meeting_activity_type and not activity.counted:
                        record.meeting_counter += 1
                        activity.counted = True
                        activity.activity_type_id.keep_done = True
            else:
                record.meeting_counter = 0

    def _check_restricted_fields(self, vals):
        if self.is_restricted_user():
            # Define restricted fields
            restricted_fields = ['developer_id', 'project_id', 'dest_country_id', 'governorate_id',
                                 'source_id', 'medium_id', 'phone', 'contact_name']

            # Check if any of the restricted fields are being changed
            restricted_fields_being_changed = set(restricted_fields).intersection(vals.keys())

            if restricted_fields_being_changed:
                # For each record, check if the CURRENT source_id and medium_id are 'Personal'
                # Don't consider the new values that might be in vals

                # Get the IDs of the 'Personal' values
                personal_source = self.env['utm.source'].sudo().search([('name', '=', 'Personal')], limit=1)
                personal_medium = self.env['utm.medium'].sudo().search([('name', '=', 'Personal Data')], limit=1)
                for record in self:
                    # Check only current values - not the new values that might be in vals
                    current_source_id = record.source_id.id
                    current_medium_id = record.medium_id.id

                    # Allow editing only if source and medium are both 'Personal'
                    if not (current_source_id == personal_source.id and current_medium_id == personal_medium.id):
                        raise UserError(_(
                            "You are not allowed to modify these fields. These fields are only editable when the source is 'Personal' "
                            "and the sub source is 'Personal Data'."
                        ))

    def is_restricted_user(self):
        user = self.env.user
        return not (user.has_group('arkzayed_18_realestate_developer_crm.lead_admin_group') or
                                  user.has_group('arkzayed_18_realestate_developer_crm.operation_manager_group') )
        # or
        #                           user.has_group('arkzayed_18_realestate_developer_crm.operation_executive_group'))

    ## validate portal leads

    def validate_locked_and_treated_security(self, locked=None):
        user = self.env.user
        if locked and locked is not None and not user.has_group('arkzayed_18_realestate_developer_crm.lead_admin_group'):
            return {'error': 'Only admin allowed to lock lead'}

        if not user.has_group('arkzayed_18_realestate_developer_crm.operation_manager_group') and self.lead_stage_id.locked:
            return {'error': 'You cannot edit a locked lead'}

    def validate_all_constraints_for_portal(self):
        for record in self:
            message = ''
            # all constraints

            # 2
            if not (record.mobile or record.phone or record.phone1 or record.phone2 or record.phone3 or record.phone4):
                message += 'At least one phone number must be filled in.\n'
            for phone in [record.mobile, record.phone, record.phone1, record.phone2, record.phone3, record.phone4]:
                record._phone_format(number=phone, country=record.country_id, force_format='INTERNATIONAL',
                                  raise_exception=True)

            # 3
            if record.qualified:
                if record.min_area <= 0:
                    message += 'Minimum area must be greater than zero when qualified.\n'
                if record.max_area <= 0:
                    message += 'Maximum area must be greater than zero when qualified.\n'
                if record.min_price <= 0:
                    message += 'Minimum price must be greater than zero when qualified.\n'
                if record.max_price <= 0:
                    message += 'Maximum price must be greater than zero when qualified.\n'

            # 4
            if record.eoi_status_for_manager and self.type == 'opportunity':
                if not self.env.user.has_group('arkzayed_18_realestate_developer_crm.approval_manager_group'):
                    message += 'You are not allowed to approve - only Manager can approve\n'

            # 5
            if record.eoi_status_for_financial and self.type == 'opportunity':
                if not self.env.user.has_group('arkzayed_18_realestate_developer_crm.financial_manager_group'):
                    message += 'You are not allowed to approve - only Financial Manager can approve\n'

            #6
            if record.eoi_status_for_operations and self.type == 'opportunity':
                if not (self.env.user.has_group('arkzayed_18_realestate_developer_crm.operation_manager_group') ):
                        # or
                        # self.env.user.has_group('arkzayed_18_realestate_developer_crm.operation_executive_group')):
                    message += 'You are not allowed to approve - only Sales Sector Manager can approve\n'

            # 7
            if record.reservation_status_for_manager and self.type == 'opportunity':
                if not self.env.user.has_group('arkzayed_18_realestate_developer_crm.approval_manager_group'):
                    raise UserError('You are not allowed to approve - only Manager can approve')

            # 8
            if record.reservation_status_for_financial and self.type == 'opportunity':
                if not self.env.user.has_group('arkzayed_18_realestate_developer_crm.financial_manager_group'):
                    message += 'You are not allowed to approve - only Financial Manager can approve\n'

            # 9
            if record.reservation_status_for_operations and self.type == 'opportunity':
                if not (self.env.user.has_group('arkzayed_18_realestate_developer_crm.operation_manager_group') ):
                        # or
                        # self.env.user.has_group('arkzayed_18_realestate_developer_crm.operation_executive_group')):
                    message += 'You are not allowed to approve - only Sales Sector Manager can approve\n'

            # 10
            if record.contract_status_for_manager and self.type == 'opportunity':
                if not self.env.user.has_group('arkzayed_18_realestate_developer_crm.approval_manager_group'):
                    message += 'You are not allowed to approve - only Manager can approve\n'

            # 11
            if record.contract_status_for_financial and self.type == 'opportunity':
                if not self.env.user.has_group('arkzayed_18_realestate_developer_crm.financial_manager_group'):
                    message += 'You are not allowed to approve - only Financial Manager can approve\n'

            # 12
            if record.contract_status_for_operations and self.type == 'opportunity':
                if not (self.env.user.has_group('arkzayed_18_realestate_developer_crm.operation_manager_group')):
                        # or
                        # self.env.user.has_group('arkzayed_18_realestate_developer_crm.operation_executive_group')):
                    message += 'You are not allowed to approve - only Sales Sector Manager can approve\n'

            if message:
                return {'errors': message}

    ## validate portal opportunities

    def validate_stage_return_back(self, stage_id):
        if self.type == 'opportunity' and stage_id < self.stage_id.id and self.is_restricted_user():
            return {'error': "You cann\'t return back stage"}

    def validate_stage_cancel_reason(self, stage_id):
        if (self.type == 'opportunity' and not self.lost_reason_id
                and stage_id in [self.env.ref('arkzayed_18_realestate_developer_crm.stage_lead5').id, self.env.ref('arkzayed_18_realestate_developer_crm.stage_lead6').id]):
            return {'error': "Reason to cancel is required"}

    def validate_required_fields_portal(self, stage_id):
        if stage_id:
            if stage_id == self.env.ref('crm.stage_lead1').id and not self.eoi_attachment:
                return {'error': "EOI attachment is required."}

            if stage_id == self.env.ref('crm.stage_lead2').id:
                reservation_state_required_fields = ['reservation_attachment', 'reservation_price', 'reserved_date']
                empty_fields = [field for field in reservation_state_required_fields if not getattr(self, field, None)]
                if empty_fields:
                    return {'error': f"{', '.join(empty_fields).replace('_', ' ').upper()} Fields is required to Reservation state"}

            if stage_id == self.env.ref('crm.stage_lead3').id:
                contract_stage_required_fields = ['contract_attachment', 'contracted_date', 'contract_price']
                if self.buying_type and self.buying_type == 'primary':
                    contract_stage_required_fields.append('unit_number')
                empty_fields = [field for field in contract_stage_required_fields if not getattr(self, field, None)]
                if empty_fields:
                    return {'error': f"{', '.join(empty_fields).replace('_', ' ').upper()} Fields is required to Contract state"}

    def validate_is_duplicate_lead_or_not_on_creation(self, vals):
        numbers_list = []
        current_user_id = vals.get('user_id')

        for phone_field in ALL_PHONE_FIELDS:
            if vals.get(phone_field):
                numbers_list.append(vals[phone_field])
        formatted_numbers = []
        for phone in numbers_list:
            try:
                formatted = self._phone_format(
                    number=phone,
                    country=vals.get('country_id'),
                    force_format='INTERNATIONAL',
                    raise_exception=True
                )
                formatted_numbers.append(formatted)
            except Exception as e:
                # Handle formatting errors if needed
                continue

        # Combine original and formatted numbers
        all_numbers = list(set(numbers_list + formatted_numbers))  # Remove duplicates

        if numbers_list:
            domain = [
                '&',
                ('user_id', '!=', current_user_id),
                '&',
                ('locked', '=', False),
                '|', '|', '|', '|', '|',
                ('phone', 'in', formatted_numbers),
                ('mobile', 'in', formatted_numbers),
                ('phone1', 'in', formatted_numbers),
                ('phone2', 'in', formatted_numbers),
                ('phone3', 'in', formatted_numbers),
                ('phone4', 'in', formatted_numbers),
            ]
            duplicate_lead_ids = self.env['crm.lead'].with_context(active_test=False).sudo().search(domain)
        if duplicate_lead_ids:
            return {'error': 'this is a duplicate lead, please contact your operation'}

    def _create_customer(self):
        res = super(CrmLead, self)._create_customer()
        if res and res.is_customer == False:
            res.write({'is_customer': True})
        return res

    def _compute_can_edit_stage_history(self):
        for rec in self:
            rec.can_edit_stage_history = self.env.user.has_group('arkzayed_18_realestate_developer_crm.lead_admin_group')

    def _new_meeting_vals(self):
        current_user = self.env.user
        partners = []

        if current_user:
            partners.append(current_user.partner_id.id)
        if self.partner_id:
            partners.append(self.partner_id.id)

        return {
            # In Odoo, many2many fields use Command.set() or [(6, 0, ids)] to write values
            'partner_ids': [Command.set(partners)],
            'user_id': current_user.id if current_user else False,
            'name': self.opportunity_sequence,
            # Linking the meeting back to the opportunity via standard Odoo calendar fields
            'opportunity_id': self.id,
        }

    def action_create_new_meeting(self):
        self.ensure_one()

        # 1. Get the pre-configured values
        meeting_vals = self._new_meeting_vals()

        # 2. Create the calendar.event record
        new_meeting = self.env['calendar.event'].create(meeting_vals)

        # 3. Return an action dictionary that opens the created record in a form view
        return {
            'type': 'ir.actions.act_window',
            'name': 'Meeting',
            'res_model': 'calendar.event',
            'view_mode': 'form',
            'res_id': new_meeting.id,
            'target': 'current',  # Use 'new' if you want it to open in a popup modal instead
            'context': self.env.context,
        }

    def _reservation_values(self):
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
            'customer_id': self.partner_id.id,
            'reservation_amount': self.reservation_price,
            'currency_id': self.currency_id.id,
            'opportunity_id': self.id,
            'unit_id': self.unit_id.id,
            'user_id': self.user_id.id if self.user_id else False,
            'split_deal': self.split_deal,
            'commission_ids': commission_lines,
            'referred_by': self.referred_by if self.referred_by else False,
            'referred_by_partner_id': self.broker_id.id if self.broker_id else False,
        }


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

        return reservation_vals

    def action_create_reservation(self):
        """Create a sale reservation from the accepted EOI"""
        self.ensure_one()

        reservation_vals = self._reservation_values()

        # Create the reservation
        reservation = self.env['real.estate.sale.reservation'].create(reservation_vals)

        # Open the created reservation form view
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'real.estate.sale.reservation',
            'name': _("Sale Reservation"),
            'view_mode': 'form',
            'res_id': reservation.id,
            'target': 'current',
        }

    def action_view_reservations(self):
        """ Opens a list/form view of reservations linked to this opportunity """
        self.ensure_one()
        action = {
            'name': _('Reservations'),
            'type': 'ir.actions.act_window',
            'res_model': 'real.estate.sale.reservation',
            'context': {'default_opportunity_id': self.id},
            'view_mode': 'list,form',
            'domain': [('opportunity_id', '=', self.id)],
        }

        return action


    def _get_contract_vals(self):

        contract_vals = {
            'customer_id': self.partner_id.id,
            'state': 'draft',
            'opportunity_id': self.id,
            'unit_id': self.unit_id.id,
            # UNIT INFO
            'contracted_selling_price': self.contract_price,
            # EOI
            'reservation_payment': self.reservation_price,
            'split_deal': self.split_deal,
            'user_id': self.user_id.id if self.user_id else False,
            'referred_by': self.referred_by if self.referred_by else False,
            'referred_by_partner_id': self.broker_id.id if self.broker_id else False,
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

        return contract_vals

    def action_create_contract(self):
        """Modified to transfer installment lines to contract"""

        contract_vals = self._get_contract_vals()

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

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.proposal',
            'name': _("Contracts"),
            'target': 'current',
            'context': {'default_opportunity_id': self.id},
            'res_id': contract_id.id,
            'view_mode': 'form',
            'domain': [('opportunity_id', '=', self.id)]
        }

    def action_show_contract(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.proposal',
            'name': _("Contracts"),
            'target': 'current',
            'context': {'default_opportunity_id': self.id},
            'view_mode': 'list,form',
            'domain': [('opportunity_id', '=', self.id)]
        }

    def action_hold_unit(self):
        self.ensure_one()

        is_enabled = self.env['ir.config_parameter'].sudo().get_param('crm.enable_crm_unit_hold')
        if not is_enabled:
            raise UserError(_("The Unit Hold feature is currently disabled in the CRM settings."))

        if not self.unit_id:
            raise UserError(_("Please select a unit to hold."))

        if self.unit_id.unit_status not in ['available', 'available_for_sale']:
            raise UserError(_("This unit is currently not available to be held."))

        self.unit_hold_start_date = fields.Datetime.now()
        self.unit_id.unit_status = 'blocked'

        formatted_date = format_datetime(self.env, self.unit_hold_start_date)

        self.message_post(body=Markup(_(
            "Unit <b>%s</b> has been placed on hold on <b>%s</b>."
        )) % (self.unit_id.name, formatted_date))

    @api.model
    def _cron_release_held_units(self):
        # 1. Safety check: ensure the feature is enabled in settings
        is_enabled = self.env['ir.config_parameter'].sudo().get_param('crm.enable_crm_unit_hold')
        if not is_enabled:
            return

        duration_hours = int(self.env['ir.config_parameter'].sudo().get_param('crm.crm_unit_hold_duration', default=24))

        # Calculate the cutoff date (Current Time - Duration)
        # Any hold that started BEFORE this cutoff date has exceeded the allowed time.
        cutoff_date = fields.Datetime.now() - timedelta(hours=duration_hours)

        domain = [
            '&', '&',
            ('unit_hold_start_date', '<=', cutoff_date),
            ('unit_id', '!=', False),
            ('unit_id.unit_status', '=', 'blocked')
        ]

        expired_holds = self.search(domain)

        if expired_holds:
            # Release the units
            expired_holds.mapped('unit_id').write({'unit_status': 'available'})

            for lead in expired_holds:
                lead.message_post(
                    body=_("Hold period of %s hours exceeded. Unit is automatically released to Available status.",
                           duration_hours)
                )

            # Clear the start date so it isn't processed again
            expired_holds.write({'unit_hold_start_date': False})