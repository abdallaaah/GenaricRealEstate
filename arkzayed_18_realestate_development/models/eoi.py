from odoo import models, fields, api, _, Command
from odoo.exceptions import ValidationError
from odoo.tools import float_compare

from .selections import unit_type_selection, residential_type_selection, referred_by_selection, public_area_selection, \
    retail_type_selection, entertainment_type_selection, industrial_type_selection, finishing_type_selection, \
    payment_methods_selection, split_with_selection

unit_type_selection = unit_type_selection.copy()
referred_by_selection = referred_by_selection.copy()

unit_type_selection.remove(('gate', 'Gate'))
referred_by_selection.remove(('management', 'Management'))

class Eoi(models.Model):
    """EOi model is related to Sales"""
    _name = "eoi.eoi"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('EOI Reference', copy=False, readonly=True, index=True,
                       default=lambda self: _('New'))
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
    is_paid = fields.Boolean(deafult=False)
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

    # fields for cheque
    cheque_manage_ids = fields.One2many('cheque.manage', 'eoi_id', string='Cheque')
    cheque_count = fields.Integer(compute='_compute_cheque_count', string='Cheque Count')

    # fields for reservations
    reservation_ids = fields.One2many('real.estate.sale.reservation', 'eoi_id', string='Reservations')
    reservation_count = fields.Integer(compute='_compute_reservation_count', string='Reservation Count')

    user_id = fields.Many2one(
        'res.users',
        string='Salesperson',
        default=lambda self: self.env.user,
        tracking=True,
        domain=[
            '|', '|', '|',
            ('job_level_id.is_sales_person', '=', True),
            ('job_level_id.is_directory', '=', True),
            ('job_level_id.is_sales_manager', '=', True),
            ('job_level_id.is_sales_sector_manager', '=', True)
        ]    )

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
        domain=[
            '|', '|', '|',
            ('job_level_id.is_sales_person', '=', True),
            ('job_level_id.is_directory', '=', True),
            ('job_level_id.is_sales_manager', '=', True),
            ('job_level_id.is_sales_sector_manager', '=', True)
        ]    )

    # Commission lines - using the same commission.commission model
    commission_ids = fields.One2many(
        'realestate.commission',
        'eoi_id',
        string='Commission',
        compute='compute_person_hierarchy',
        store=True,
        readonly=False
    )
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

    @api.depends('user_id', 'sales_ids', 'split_deal')
    def compute_person_hierarchy(self):
        """
        Compute commission hierarchy for EOI based on user_id and sales_ids
        Similar to CRM Lead hierarchy
        """
        # Job positions list (3 levels: Sales Person, Sales Manager, Director)
        job_positions = ['Sales Person', 'Sales Manager', 'Team Leader', 'Director']
        job_position_order = {pos: index for index, pos in enumerate(job_positions)}

        for rec in self:
            # Skip if no user assigned
            if not rec.user_id:
                rec.commission_ids = [Command.clear()]
                continue

            # Get team for the main user
            team_member = self.env['crm.team.member'].search([('user_id', '=', rec.user_id.id)], limit=1)

            if not team_member or not team_member.crm_team_id:
                # If user has no team, skip commission calculation
                rec.commission_ids = [Command.clear()]
                continue

            team_id = team_member.crm_team_id

            # Clear existing commission lines
            rec.commission_ids = [Command.clear()]
            unique_lines = {}  # Changed to dict to store user_id: job_position

            # Build team hierarchy for main user (3 levels)
            team_users = [
                rec.user_id,  # Sales Person
                team_id.user_id,  # Sales Manager (team leader)
                team_id.director_id  # Director
            ]

            # Add main user's team hierarchy
            for i in range(len(team_users)):
                if team_users[i]:  # Only add if user exists
                    user_id = team_users[i].id
                    # Keep the highest position if user appears multiple times
                    if user_id not in unique_lines or job_position_order[job_positions[i]] < job_position_order[
                        unique_lines[user_id]]:
                        unique_lines[user_id] = job_positions[i]

            # If split deal, add hierarchies for additional sales people
            if rec.split_deal and rec.sales_ids:
                for person in rec.sales_ids:
                    # Get team for each additional sales person
                    person_team_member = self.env['crm.team.member'].search(
                        [('user_id', '=', person.id)], limit=1
                    )

                    if person_team_member and person_team_member.crm_team_id:
                        person_team_id = person_team_member.crm_team_id

                        # Build hierarchy for this person
                        person_team_users = [
                            person,  # Sales Person
                            person_team_id.user_id,  # Sales Manager
                            person_team_id.director_id  # Director
                        ]

                        # Add to unique lines
                        for i in range(len(person_team_users)):
                            if person_team_users[i]:  # Only add if user exists
                                user_id = person_team_users[i].id
                                # Keep the highest position if user appears multiple times
                                if user_id not in unique_lines or job_position_order[job_positions[i]] < \
                                        job_position_order[unique_lines[user_id]]:
                                    unique_lines[user_id] = job_positions[i]

            # Sort lines by job position hierarchy
            sorted_lines = sorted(unique_lines.items(), key=lambda x: job_position_order[x[1]])

            # Create commission lines
            lines = [Command.create({
                'eoi_id': rec.id,
                'employee_id': user_id,
                'jop_position': job_position,
                'commission': 100.0  # Default commission percentage
            }) for user_id, job_position in sorted_lines]

            rec.commission_ids = lines

    @api.onchange('sales_ids')
    def _onchange_sales_ids(self):
        """Trigger recomputation when sales_ids changes in the UI"""
        self.compute_person_hierarchy()

    def write(self, vals):
        """Override write to recompute commission when sales_ids changes"""
        res = super(Eoi, self).write(vals)
        # Force recompute if sales_ids changed
        if 'sales_ids' in vals:
            self.compute_person_hierarchy()
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

        if self.cheque_manage_ids:
            for cheque in self.cheque_manage_ids:
                if cheque.state not in ['draft', 'return_to_client']:
                    cheque.sale_reservation_id = reservation.id

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

    def _compute_cheque_count(self):
        for record in self:
            record.cheque_count = len(record.cheque_manage_ids)

    def create_cheque_payment(self):
        self.ensure_one()
        cheque_payment_id = self.env['cheque.manage'].create({
            'payer': self.customer_id.id,
            'amount': self.reservation_amount,
            'eoi_id': self.id,
            'journal_id': self.env['account.journal'].search([], limit=1).id,
            'cheq_type': 'incoming',
            'from_eoi': True,
        })
        return {
            'name': _('Cheque Payment'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'cheque.manage',
            'res_id': cheque_payment_id.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def check_cheque_payment(self):
        for rec in self:
            if not self.cheque_manage_ids:
                raise ValidationError("EOI Cheque Payment is Not Complete")
            else:
                if rec.cheque_manage_ids[0].amount != self.reservation_amount:
                    raise ValidationError("The Cheque Payment Of This EOI Not Equal The Reservation Amount")

                if rec.payment_methods != 'cheque':
                    raise ValidationError("Please use 'Check Payment' button for cash or bank payments")

                # Check if the cheque payment is not in draft or returned state
                # Assuming the cheque state is stored in a field called 'state' in account.payment
                if rec.cheque_manage_ids[0].state not in ['draft', 'return_to_client']:
                    rec.status = "paid"
                else:
                    raise ValidationError("EOI Cheque Payment is not in a valid state")

    def action_show_cheques(self):
        cheques = self.env['cheque.manage'].search([('eoi_id', '=', self.id)])
        if cheques:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'cheque.manage',
                'name': _("Cheques"),
                'target': 'current',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('eoi_id', '=', self.id)],
                'context': {
                    'default_cheq_type': 'incoming',
                    'default_eoi_id': self.id,
                    'default_amount': self.reservation_amount,
                    'default_payer': self.customer_id.id
                }
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'cheque.manage',
                'name': _("Cheques"),
                'target': 'current',
                'views': [(False, 'form'), (False, 'list')],
                'context': {
                    'default_cheq_type': 'incoming',
                    'default_eoi_id': self.id,
                    'default_amount': self.reservation_amount,
                    'default_payer': self.customer_id.id
                }
            }

    def accept_eoi(self):
        self.status = 'accepted'

    def reject_eoi(self):
        cheques = self.env['cheque.manage'].search([('eoi_id', '=', self.id), ('state', 'in', ['collect', 'register'])])
        if cheques:
            for cheque in cheques:
                cheque.action_return()
                if cheque.state == 'return_to_client':
                    cheque.action_return_to_client()
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
