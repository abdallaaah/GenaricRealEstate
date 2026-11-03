from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import html2plaintext

PHONE_FIELDS = ['phone', 'phone1', 'phone2', 'phone3', 'phone4']

APPROVAL_FIELDS = [
    ('eoi_status_for_manager', 'eoi', 'manager'),
    ('eoi_status_for_financial', 'eoi', 'financial'),
    ('eoi_status_for_sales', 'eoi', 'sales'),
    ('eoi_status_for_operations', 'eoi', 'operations'),
    ('reservation_status_for_manager', 'reservation', 'manager'),
    ('reservation_status_for_financial', 'reservation', 'financial'),
    ('reservation_status_for_sales', 'reservation', 'sales'),
    ('reservation_status_for_operations', 'reservation', 'operations'),
    ('contract_status_for_manager', 'contract', 'manager'),
    ('contract_status_for_financial', 'contract', 'financial'),
    ('contract_status_for_sales', 'contract', 'sales'),
    ('contract_status_for_operations', 'contract', 'operations'),
]

APPROVAL_STATUS_SELECTION = [('approved', "Approved"), ('rejected', "Rejected"), ('pending', "Pending")]

UNIT_TYPE_SELECTION = [
    ('apartment', "Apartment"), ('villa', "Villa"), ('duplex', "Duplex"), ('penthouse', "Penthouse"),
    ('studio', "Studio"), ('townhouse', "Town House"), ('twin_house', "Twin House"), ('chalet', "Chalet"),
    ('cabin', "Cabin"), ('loft', "Loft"), ('office_space', "Office Space"), ('retail', "Retail"),
    ('clinic', "Clinic"), ('land', "Land"), ('warehouse', "Warehouse"), ('factory', "Factory"),
    ('parking', "Parking"), ('other', "Other"),
]


class CrmLead(models.Model):
    _inherit = 'crm.lead'
    _rec_name = 'opportunity_sequence'

    # Identification
    lead_sequence = fields.Char(readonly=True, copy=False)
    opportunity_sequence = fields.Char(readonly=True, copy=False)
    lead_stage_id = fields.Many2one('lead.stage', tracking=True)
    first = fields.Boolean(related='lead_stage_id.first')
    call_later = fields.Boolean(related='lead_stage_id.call_later')
    no_answer = fields.Boolean(related='lead_stage_id.no_answer')
    is_qualified = fields.Boolean(related='lead_stage_id.qualified', string="Qualified")
    unqualified = fields.Boolean(related='lead_stage_id.unqualified')
    qualified_limited_budget = fields.Boolean(related='lead_stage_id.qualified_limited_budget')
    follow_up = fields.Boolean(related='lead_stage_id.follow_up')
    locked = fields.Boolean(related='lead_stage_id.locked')

    is_eoi = fields.Boolean(related='stage_id.is_eoi')
    is_reserved = fields.Boolean(related='stage_id.is_reserved')
    is_contract = fields.Boolean(related='stage_id.is_contract')
    is_cancel = fields.Boolean(related='stage_id.is_cancel')
    is_collected = fields.Boolean(related='stage_id.is_collected')
    is_confirmed_contract = fields.Boolean(related='stage_id.is_confirmed_contract')
    is_request_to_cancel = fields.Boolean(related='stage_id.is_request_to_cancel')

    # Classification
    interested_in = fields.Selection([('buy', "Buy"), ('rent', "Rent"), ('sell', "Sell")])
    buying_type = fields.Selection([('primary', "Primary"), ('resale', "Resale")], tracking=True)
    buying_purpose = fields.Selection([('for_invest', "For Invest"), ('for_home', "For Home")])
    place_preferences = fields.Selection([('compound', "Compound"), ('any', "Any")])
    furniture_type = fields.Selection([('furnished', "Furnished"), ('not_furnished', "Not Furnished")])
    ready_to_move = fields.Boolean()

    # Not required=True at the field level: crm.lead is shared with core CRM and any other
    # installed app, which may create leads with none of these broker-specific fields set
    # (confirmed by a real install failure against stock CRM/website_crm_partner_assign demo
    # data). Required-ness for an actual broker deal is enforced at the right stage instead,
    # the same way eoi/reservation/contract attachments already are (validate_required_fields).
    developer_id = fields.Many2one('res.partner')
    project_id = fields.Many2one('developer.project', tracking=True)
    unit_id = fields.Many2one('broker.unit')
    unit_type = fields.Selection(UNIT_TYPE_SELECTION)
    unit_number = fields.Char()
    finish_type = fields.Selection([
        ('finished', "Finished"), ('semi_finished', "Semi-Finished"), ('core_shell', "Core and Shell"),
    ])
    number_of_bedrooms = fields.Integer()
    number_of_bathrooms = fields.Integer()
    min_area = fields.Float()
    max_area = fields.Float()
    min_price = fields.Monetary(string="Min Budget", currency_field='company_currency', tracking=True)
    max_price = fields.Monetary(string="Max Budget", currency_field='company_currency', tracking=True)
    qualified_comment = fields.Text()

    dest_country_id = fields.Many2one('res.country', string="Destination Country")
    governorate_id = fields.Many2one(
        'res.country.state', domain="[('country_id', '=', dest_country_id)]")
    dest_city_id = fields.Many2one('res.country.city', string="District")
    neighborhood_id = fields.Many2one('neighborhood.neighborhood', related='project_id.neighborhood_id')

    # Deal data
    reserved_date = fields.Date()
    contracted_date = fields.Date()
    collected_date = fields.Date()
    confirmed_date = fields.Date()
    achievement_date = fields.Date()
    reservation_price = fields.Monetary(currency_field='company_currency', tracking=True)
    contract_price = fields.Monetary(currency_field='company_currency', tracking=True)
    sales_volume = fields.Monetary(currency_field='company_currency', tracking=True)
    eoi_attachment = fields.Binary()
    reservation_attachment = fields.Binary()
    contract_attachment = fields.Binary()
    lost_reason_id = fields.Many2one('crm.lost.reason')
    reopen_reason = fields.Char()
    cancellation_approver = fields.Many2one('res.partner', readonly=True)

    # Split deal / commission hierarchy
    split_deal = fields.Boolean()
    sales_ids = fields.Many2many('res.users', 'crm_lead_sales_rel', 'lead_id', 'user_id', string="Split With")
    broker_ids = fields.Many2many(
        'res.partner', 'crm_lead_broker_rel', 'lead_id', 'partner_id',
        string="Outside Broker", domain="[('is_broker', '=', True)]")
    ambassador_ids = fields.Many2many(
        'res.partner', 'crm_lead_ambassador_rel', 'lead_id', 'partner_id',
        string="Ambassador", domain="[('is_ambassador', '=', True)]")
    commission_ids = fields.One2many(
        'commission.commission', 'opportunity_id', compute='_compute_person_hierarchy', store=True, readonly=False)

    # Approval matrix (phase x role), enforced against isky_20_broker_crm.broker.approval.rule
    eoi_status_for_manager = fields.Selection(APPROVAL_STATUS_SELECTION, default='pending', tracking=True)
    eoi_status_for_financial = fields.Selection(APPROVAL_STATUS_SELECTION, default='pending', tracking=True)
    eoi_status_for_sales = fields.Selection(APPROVAL_STATUS_SELECTION, default='pending', tracking=True)
    eoi_status_for_operations = fields.Selection(APPROVAL_STATUS_SELECTION, default='pending', tracking=True)
    eoi_rejection_reason_for_manager = fields.Text()
    eoi_rejection_reason_for_financial = fields.Text()
    eoi_rejection_reason_for_sales = fields.Text()
    eoi_rejection_reason_for_operations = fields.Text()
    reservation_status_for_manager = fields.Selection(APPROVAL_STATUS_SELECTION, default='pending', tracking=True)
    reservation_status_for_financial = fields.Selection(APPROVAL_STATUS_SELECTION, default='pending', tracking=True)
    reservation_status_for_sales = fields.Selection(APPROVAL_STATUS_SELECTION, default='pending', tracking=True)
    reservation_status_for_operations = fields.Selection(APPROVAL_STATUS_SELECTION, default='pending', tracking=True)
    reservation_rejection_reason_for_manager = fields.Text()
    reservation_rejection_reason_for_financial = fields.Text()
    reservation_rejection_reason_for_sales = fields.Text()
    reservation_rejection_reason_for_operations = fields.Text()
    contract_status_for_manager = fields.Selection(APPROVAL_STATUS_SELECTION, default='pending', tracking=True)
    contract_status_for_financial = fields.Selection(APPROVAL_STATUS_SELECTION, default='pending', tracking=True)
    contract_status_for_sales = fields.Selection(APPROVAL_STATUS_SELECTION, default='pending', tracking=True)
    contract_status_for_operations = fields.Selection(APPROVAL_STATUS_SELECTION, default='pending', tracking=True)
    contract_rejection_reason_for_manager = fields.Text()
    contract_rejection_reason_for_financial = fields.Text()
    contract_rejection_reason_for_sales = fields.Text()
    contract_rejection_reason_for_operations = fields.Text()

    # Extra phone channels (shared convention with res.partner, see isky_20_broker_base)
    phone1 = fields.Char(string="Extra Phone 2")
    phone2 = fields.Char(string="International Phone")
    phone3 = fields.Char(string="Extra International Phone")
    phone4 = fields.Char(string="Extra International Phone 2")

    # Duplicate / conflict detection
    is_conflict_unit = fields.Boolean()
    conflict_opp_ids = fields.Many2many(
        'crm.lead', 'crm_lead_conflict_rel', 'lead_id', 'conflict_lead_id', string="Conflicting Opportunities")
    duplicate_tcr_number = fields.Integer(compute='_compute_tcr_counts')
    conflict_tcr_number = fields.Integer(compute='_compute_tcr_counts')
    no_answer_count = fields.Integer(default=0)
    unqualified_count = fields.Integer(default=0)

    meeting_counter = fields.Integer(compute='_compute_meeting_count', store=True)
    last_message = fields.Char(compute='_compute_last_message', store=True, string="Last Activity")
    record_creation = fields.Boolean()

    # Reassignment audit trail
    previous_user_id = fields.Many2one('res.users', readonly=True)
    assigned_by_id = fields.Many2one('res.users', readonly=True)
    reassigned = fields.Boolean()

    # ---------------------------------------------------------------- computes

    @api.depends('user_id', 'sales_ids', 'split_deal')
    def _compute_person_hierarchy(self):
        for lead in self:
            if lead.type != 'opportunity':
                lead.commission_ids = [Command.clear()]
                continue
            hierarchy_users = self._get_hierarchy_users(lead.user_id)
            if lead.split_deal:
                for user in lead.sales_ids:
                    hierarchy_users |= self._get_hierarchy_users(user)
            lead.commission_ids = [Command.clear()] + [
                Command.create({'opportunity_id': lead.id, 'employee_id': user.id})
                for user in hierarchy_users
            ]

    def _get_hierarchy_users(self, user):
        """Everyone who should get a commission share because of `user`'s position:
        the person themselves, plus whoever they report up to (team leader, sales
        manager, director), based on their job.level role flag.
        """
        Users = self.env['res.users']
        if not user or not user.job_level_id:
            return Users
        if user.job_level_id.is_sales_person:
            team = self.env['crm.team.member'].search([('user_id', '=', user.id)], limit=1).crm_team_id
            result = user | team.user_id | team.director_id | team.sales_manager_id
        elif user.job_level_id.is_team_leader:
            team = self.env['crm.team'].search([('user_id', '=', user.id)], limit=1)
            result = user | team.director_id | team.sales_manager_id
        elif user.job_level_id.is_sales_manager:
            team = self.env['crm.team'].search([('sales_manager_id', '=', user.id)], limit=1)
            result = user | team.director_id
        else:
            result = user
        return result.filtered(lambda u: u)

    @api.depends('project_id', 'developer_id', 'type', 'unit_number', 'user_id')
    def _compute_tcr_counts(self):
        for lead in self:
            if not (lead.project_id and lead.unit_number and lead.type == 'opportunity'):
                lead.duplicate_tcr_number = 0
                lead.conflict_tcr_number = 0
                continue
            same_unit = self.env['crm.lead'].search_count([
                ('id', '!=', lead.id),
                ('project_id', '=', lead.project_id.id),
                ('developer_id', '=', lead.developer_id.id),
                ('type', '=', 'opportunity'),
                ('unit_number', '=', lead.unit_number),
            ])
            same_unit_same_user = self.env['crm.lead'].search_count([
                ('id', '!=', lead.id),
                ('project_id', '=', lead.project_id.id),
                ('developer_id', '=', lead.developer_id.id),
                ('type', '=', 'opportunity'),
                ('unit_number', '=', lead.unit_number),
                ('user_id', '=', lead.user_id.id),
            ])
            lead.duplicate_tcr_number = same_unit_same_user
            lead.conflict_tcr_number = same_unit - same_unit_same_user

    @api.depends('message_ids')
    def _compute_last_message(self):
        for lead in self:
            message = lead.message_ids.filtered(lambda m: m.subtype_id.internal is False)[:1]
            lead.last_message = html2plaintext(message.body) if message else self.env._("No Messages")

    @api.depends('activity_ids')
    def _compute_meeting_count(self):
        meeting_type = self.env.ref('mail.mail_activity_data_meeting', raise_if_not_found=False)
        for lead in self:
            if not meeting_type:
                lead.meeting_counter = 0
                continue
            uncounted = lead.activity_ids.filtered(
                lambda a: a.activity_type_id == meeting_type and not a.counted)
            uncounted.counted = True
            lead.meeting_counter = lead.meeting_counter + len(uncounted)

    # ---------------------------------------------------------------- actions

    def action_duplicate_tcr(self):
        return self._tcr_action(same_user=True)

    def action_conflict_tcr(self):
        return self._tcr_action(same_user=False)

    def _tcr_action(self, same_user):
        self.ensure_one()
        domain = [
            ('id', '!=', self.id),
            ('project_id', '=', self.project_id.id),
            ('developer_id', '=', self.developer_id.id),
            ('type', '=', 'opportunity'),
            ('unit_number', '=', self.unit_number),
        ]
        domain.append(('user_id', '=' if same_user else '!=', self.user_id.id))
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Duplicate TCRs") if same_user else self.env._("Conflicting TCRs"),
            'res_model': 'crm.lead',
            'view_mode': 'list,form',
            'domain': domain,
        }

    def action_no_answer(self):
        stage = self.env.ref('isky_20_broker_crm.lead_stage_no_answer')
        self.write({'lead_stage_id': stage.id})

    def action_follow_up(self):
        stage = self.env.ref('isky_20_broker_crm.lead_stage_follow_up')
        self.write({'lead_stage_id': stage.id})

    def action_lock(self):
        if not self.env.user.has_group('isky_20_broker_crm.group_lead_admin'):
            raise AccessError(self.env._("Only a lead administrator can lock a lead."))
        self.write({'lead_stage_id': self.env.ref('isky_20_broker_crm.lead_stage_locked').id})

    def action_unlock(self):
        if not self.env.user.has_group('isky_20_broker_crm.group_lead_admin'):
            raise AccessError(self.env._("Only a lead administrator can unlock a lead."))
        self.write({'lead_stage_id': self.env.ref('isky_20_broker_crm.lead_stage_new').id})

    def action_qualify(self, limited_budget=False):
        self.ensure_one()
        required = [self.qualified_comment, self.priority, self.unit_type, self.finish_type,
                    self.min_area, self.max_area, self.min_price, self.max_price]
        target_stage = 'isky_20_broker_crm.lead_stage_qualified_limited_budget' if limited_budget \
            else 'isky_20_broker_crm.lead_stage_qualified'
        if all(required):
            self.write({'lead_stage_id': self.env.ref(target_stage).id})
            return True
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Qualify Lead"),
            'res_model': 'qualified.stage.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_lead_id': self.id, 'default_limited_budget': limited_budget},
        }

    def action_unqualify(self):
        self.ensure_one()
        if self.lost_reason_id:
            self.write({'lead_stage_id': self.env.ref('isky_20_broker_crm.lead_stage_unqualified').id})
            return True
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._("Unqualify Lead"),
            'res_model': 'crm.lead.unqualified.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_lead_id': self.id},
        }

    @property
    def has_reassign_auth(self):
        return self.env.user.has_group('sales_team.group_sale_salesman_all_leads') \
            or self.env.user.has_group('sales_team.group_sale_manager') \
            or self.env.user.has_group('isky_20_broker_crm.group_director_manager') \
            or self.env.user.has_group('isky_20_broker_crm.group_operation_manager')

    def is_restricted_user(self):
        return not self.has_reassign_auth

    # ---------------------------------------------------------------- CRUD

    @api.model_create_multi
    def create(self, vals_list):
        LeadStage = self.env['lead.stage']
        first_stage = LeadStage.search([('first', '=', True)], limit=1)
        for vals in vals_list:
            vals.setdefault('lead_stage_id', first_stage.id)
            self._check_unit_number_conflict(vals)
            vals, duplicate = self._handle_number_duplication(vals)
            if vals.get('type') == 'lead':
                vals['lead_sequence'] = self.env['ir.sequence'].next_by_code('isky_20_broker_crm.lead')
            elif vals.get('type') == 'opportunity':
                vals['opportunity_sequence'] = self.env['ir.sequence'].next_by_code('isky_20_broker_crm.opportunity')
            vals['_duplicate_warning'] = duplicate
        duplicate_flags = [vals.pop('_duplicate_warning', False) for vals in vals_list]
        leads = super().create(vals_list)
        for lead, duplicate in zip(leads, duplicate_flags):
            if lead.unit_id and lead.partner_id and lead.type == 'opportunity':
                lead.unit_id.sudo().write({'customer_id': lead.partner_id.id, 'tcr': lead.opportunity_sequence})
            if duplicate:
                self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification', {
                    'type': 'danger',
                    'title': self.env._("Warning"),
                    'message': self.env._("This lead duplicates an existing phone number and has been "
                                           "reassigned to the duplicate tracker."),
                })
                lead.message_post(body=self.env._("This lead was flagged as a duplicate on creation and "
                                                    "reassigned to the duplicate tracker."))
        return leads

    def _check_unit_number_conflict(self, vals):
        unit_number = vals.get('unit_number')
        current_user_id = vals.get('user_id')
        if not (unit_number and current_user_id):
            return
        same_user_same_unit = self.search_count([
            ('unit_number', '=', unit_number), ('user_id', '=', current_user_id)])
        if same_user_same_unit:
            raise UserError(self.env._("There is already an opportunity for this unit number with this salesperson."))
        conflicting = self.search([('unit_number', '=', unit_number), ('user_id', '!=', current_user_id)])
        if conflicting:
            vals['is_conflict_unit'] = True
            vals['conflict_opp_ids'] = [Command.link(lead.id) for lead in conflicting]
            conflicting.write({'is_conflict_unit': True})

    def _handle_number_duplication(self, vals):
        current_user_id = vals.get('user_id')
        if not current_user_id:
            return vals, False
        numbers = [vals[field] for field in PHONE_FIELDS if vals.get(field)]
        if not numbers:
            return vals, False
        domain = [
            ('user_id', '!=', current_user_id),
            ('locked', '=', False),
            '|', '|', '|', '|',
            ('phone', 'in', numbers), ('phone1', 'in', numbers),
            ('phone2', 'in', numbers), ('phone3', 'in', numbers), ('phone4', 'in', numbers),
        ]
        duplicates = self.with_context(active_test=False).sudo().search(domain, limit=1)
        if not duplicates:
            return vals, False
        tracker = self.env['hr.employee'].sudo().search([('is_duplicity_tracker', '=', True)], limit=1)
        vals.update({
            'lead_stage_id': self.env.ref('isky_20_broker_crm.lead_stage_locked').id,
            'user_id': tracker.user_id.id if tracker.user_id else self.env.user.id,
            'record_creation': True,
        })
        return vals, True

    def write(self, vals):
        self._check_restricted_fields(vals)
        self._check_lead_stage_transition(vals)
        self._check_stage_transition(vals)
        self._set_achievement_date(vals)
        self._check_locked(vals)
        self.validate_required_fields(vals)
        result = super().write(vals)
        if result and vals.get('user_id'):
            self._reset_followers_to_salesperson(vals['user_id'])
        return result

    def _check_lead_stage_transition(self, vals):
        if 'lead_stage_id' not in vals:
            return
        new_stage = self.env['lead.stage'].browse(vals['lead_stage_id'])
        for lead in self:
            if lead.is_qualified and not new_stage.qualified and self.is_restricted_user():
                raise AccessError(self.env._(
                    "Only sales managers, lead admins, and operations can move a qualified lead back."))
            if new_stage.locked and not self.env.user.has_group('isky_20_broker_crm.group_lead_admin'):
                raise AccessError(self.env._("Only a lead administrator can lock a lead."))
            if new_stage.no_answer and vals['lead_stage_id'] != lead.lead_stage_id.id:
                vals['no_answer_count'] = lead.no_answer_count + 1
            if new_stage.unqualified:
                if not (lead.lost_reason_id or vals.get('lost_reason_id')):
                    raise ValidationError(self.env._("A lost reason is required to unqualify a lead."))
                if vals['lead_stage_id'] != lead.lead_stage_id.id:
                    vals['unqualified_count'] = lead.unqualified_count + 1

    def _check_stage_transition(self, vals):
        if 'stage_id' not in vals:
            return
        new_stage = self.env['crm.stage'].browse(vals['stage_id'])
        finance_group = 'isky_20_broker_crm.group_finance'
        for lead in self:
            if lead.type != 'opportunity':
                continue
            if new_stage.id == lead.stage_id.id:
                continue
            if new_stage.id < lead.stage_id.id and self.is_restricted_user():
                raise ValidationError(self.env._("You cannot move a deal back to a previous stage."))
            if new_stage.is_collected and not (lead.collected_date or vals.get('collected_date')):
                raise ValidationError(self.env._("A collected date is required."))
            if new_stage.is_confirmed_contract and not (lead.confirmed_date or vals.get('confirmed_date')):
                raise ValidationError(self.env._("A confirmed date is required."))
            if (new_stage.is_collected or new_stage.is_confirmed_contract) \
                    and not self.env.user.has_group(finance_group):
                raise AccessError(self.env._("Only finance can move a deal to this stage."))
            if new_stage.is_cancel:
                if not (lead.lost_reason_id or vals.get('lost_reason_id')):
                    raise ValidationError(self.env._("A lost reason is required to cancel a deal."))
                vals['cancellation_approver'] = self.env.user.partner_id.id
                if lead.unit_id:
                    lead.unit_id.unit_status = 'available'
            if new_stage.id == self.env.ref('isky_20_broker_crm.stage_reopen').id:
                if not self.env.user.has_group(finance_group):
                    raise AccessError(self.env._("Only finance can reopen a deal."))
                if not (lead.reopen_reason or vals.get('reopen_reason')):
                    raise ValidationError(self.env._("A reopen reason is required."))

    def _set_achievement_date(self, vals):
        for lead in self:
            if lead.achievement_date:
                continue
            if vals.get('reserved_date'):
                vals['achievement_date'] = vals['reserved_date']
            elif vals.get('contracted_date') and not lead.reserved_date:
                vals['achievement_date'] = vals['contracted_date']

    def _check_locked(self, vals):
        if self.env.user.has_group('isky_20_broker_crm.group_operation_manager'):
            return
        for lead in self:
            if lead.record_creation:
                continue
            if lead.lead_stage_id.locked or lead.stage_id.is_cancel:
                raise UserError(self.env._("You cannot edit a locked lead."))

    def _check_restricted_fields(self, vals):
        if not self.is_restricted_user():
            return
        restricted = {'developer_id', 'project_id', 'dest_country_id', 'governorate_id',
                       'source_id', 'medium_id', 'phone', 'contact_name'}
        if not restricted.intersection(vals):
            return
        personal_source = self.env.ref('isky_20_broker_crm.utm_source_personal', raise_if_not_found=False)
        for lead in self:
            if not personal_source or lead.source_id == personal_source:
                continue
            raise AccessError(self.env._(
                "Marketing attribution fields can only be edited on personally-sourced leads."))

    def validate_required_fields(self, vals):
        if 'stage_id' not in vals:
            return
        checks = [
            ('isky_20_broker_crm.stage_eoi', ['eoi_attachment']),
            ('isky_20_broker_crm.stage_reservation', ['reservation_attachment', 'reservation_price', 'reserved_date']),
            ('isky_20_broker_crm.stage_contract', ['contract_attachment', 'contracted_date', 'contract_price']),
        ]
        for xmlid, required_fields in checks:
            stage = self.env.ref(xmlid, raise_if_not_found=False)
            if not stage or vals.get('stage_id') != stage.id:
                continue
            for lead in self:
                fields_for_lead = list(required_fields)
                if xmlid.endswith('stage_contract') and (vals.get('buying_type') or lead.buying_type) == 'primary':
                    fields_for_lead.append('unit_number')
                missing = [f for f in fields_for_lead if not vals.get(f) and not lead[f]]
                if missing:
                    raise UserError(self.env._("Missing required fields for this stage: %s", ', '.join(missing)))

    def _reset_followers_to_salesperson(self, user_id):
        new_salesperson = self.env['res.users'].browse(user_id)
        for lead in self:
            lead.message_follower_ids.sudo().unlink()
            if new_salesperson.partner_id:
                lead.message_subscribe([new_salesperson.partner_id.id])

    def toggle_active(self):
        was_archived = not self.active
        result = super().toggle_active()
        if self.type == 'lead' and was_archived and self.active:
            self.lead_stage_id = self.env.ref('isky_20_broker_crm.lead_stage_new').id
        return result

    def _create_customer(self):
        partner = super()._create_customer()
        partner.is_customer = True
        return partner

    @api.constrains(*(field for field, _phase, _role in APPROVAL_FIELDS))
    def _check_approval_rights(self):
        rules_by_key = {
            (rule.phase, rule.role): rule.group_id
            for rule in self.env['broker.approval.rule'].search([])
        }
        for lead in self:
            if lead.type != 'opportunity':
                continue
            for field_name, phase, role in APPROVAL_FIELDS:
                if lead[field_name] == 'pending':
                    continue
                group = rules_by_key.get((phase, role))
                if group and group not in self.env.user.all_group_ids:
                    raise AccessError(self.env._(
                        "You are not allowed to approve this: only %s can.", group.name))

    @api.constrains('phone', 'phone1', 'phone2', 'phone3', 'phone4', 'project_id')
    def _check_at_least_one_phone(self):
        # Scoped to project_id being set, i.e. a lead actually going through this module's
        # pipeline -- not every crm.lead in the database (core CRM demo data and leads from
        # other installed apps have no reason to carry a broker project reference, and must
        # not be blocked by a broker-specific contact-info rule).
        for lead in self:
            if lead.project_id and not any(
                    [lead.phone, lead.phone1, lead.phone2, lead.phone3, lead.phone4]):
                raise ValidationError(self.env._("At least one phone number must be filled in."))
