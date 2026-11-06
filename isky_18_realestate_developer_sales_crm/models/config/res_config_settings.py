from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # R4 (Financials): the precision the split sum-to-100 rule uses.
    split_percentage_precision = fields.Integer(
        related='company_id.split_percentage_precision', readonly=False,
        string='Split Percentage Decimals')

    # ----------------------------------------------------------------------------------
    # S7: approval settings. Three entries in the sense section 11 means - one switch, one
    # block for the contract chain, one block for reservation and discount.
    # ----------------------------------------------------------------------------------
    approval_enabled = fields.Boolean(
        related='company_id.approval_enabled', readonly=False,
        string='Require Approvals')

    finance_approver_group_ids = fields.Many2many(
        related='company_id.finance_approver_group_ids', readonly=False,
        string='Finance Approvers')
    finance_two_approver_group_ids = fields.Many2many(
        related='company_id.finance_two_approver_group_ids', readonly=False,
        string='Second Finance Approvers')
    manager_approver_group_ids = fields.Many2many(
        related='company_id.manager_approver_group_ids', readonly=False,
        string='Manager Approvers')
    operation_manager_approver_group_ids = fields.Many2many(
        related='company_id.operation_manager_approver_group_ids', readonly=False,
        string='Sales Sector Manager Approvers')

    confirm_reservation_group_ids = fields.Many2many(
        related='company_id.confirm_reservation_group_ids', readonly=False,
        string='Can Confirm Reservations')
    show_discount_group_ids = fields.Many2many(
        related='company_id.show_discount_group_ids', readonly=False,
        string='Can See Discount Percentage')
    edit_discount_group_ids = fields.Many2many(
        related='company_id.edit_discount_group_ids', readonly=False,
        string='Can Edit Discount Percentage')
    manual_paid_group_ids = fields.Many2many(
        related='company_id.manual_paid_group_ids', readonly=False,
        string='Can Tick Installments as Paid')

    @api.onchange('finance_approver_group_ids', 'finance_two_approver_group_ids',
                  'manager_approver_group_ids', 'operation_manager_approver_group_ids',
                  'confirm_reservation_group_ids', 'show_discount_group_ids',
                  'edit_discount_group_ids', 'manual_paid_group_ids')
    def _onchange_warn_memberless_approver_groups(self):
        """Spec section 4: a group with no members may be saved, but the save warns. Odoo has
        no non-blocking warning on write(), so the warning is raised here - the form shows it
        and the user can still save - and res.company.write() also logs it server-side."""
        empty = []
        for field in ('finance_approver_group_ids', 'finance_two_approver_group_ids',
                      'manager_approver_group_ids', 'operation_manager_approver_group_ids',
                      'confirm_reservation_group_ids', 'show_discount_group_ids',
                      'edit_discount_group_ids', 'manual_paid_group_ids'):
            for group in self[field]:
                if not group.users:
                    empty.append(group.display_name)
        if empty:
            return {'warning': {
                'title': _("Approver group has no members"),
                'message': _(
                    "These approver groups have no users assigned yet, so nobody can approve "
                    "the stages that use them:\n\n%(groups)s\n\n"
                    "You can still save - assign users before the stage is reached.",
                    groups='\n'.join('  - %s' % g for g in dict.fromkeys(empty))),
            }}

    # Phase 3 step 5: the installments default, surfaced in the Sales Setup block.
    installments_enabled = fields.Boolean(
        related='company_id.installments_enabled',
        readonly=False,
        string='Use Installments')

    residential_default_years = fields.Integer(
        string='Residential Units Default Years',
        config_parameter='arkzayed_18_realestate_development.residential_default_years',
        default=8
    )
    non_residential_default_years = fields.Integer(
        string="Non-Residential Units Default Years",
        config_parameter='arkzayed.non_residential_default_years',
        default=7
    )

    # Collection Entry Settings
    collection_debit_account_id = fields.Many2one(
        'account.account',
        string='Collection Debit Account (Expense)',
        config_parameter='arkzayed_18_realestate_development.collection_debit_account_id',
        domain=[('deprecated', '=', False)],
        help="Debit account for collection expense entries"
    )
    collection_credit_gis_account_id = fields.Many2one(
        'account.account',
        string='Collection Credit Account - GIS',
        config_parameter='arkzayed_18_realestate_development.collection_credit_gis_account_id',
        domain=[('deprecated', '=', False)],
        help="Credit account for GIS in collection entries"
    )
    collection_gis_percentage = fields.Float(
        string='GIS Percentage (%)',
        config_parameter='arkzayed_18_realestate_development.collection_gis_percentage',
        help="Percentage of amount to credit to GIS account"
    )
    collection_credit_oaya_account_id = fields.Many2one(
        'account.account',
        string='Collection Credit Account - OAYA',
        config_parameter='arkzayed_18_realestate_development.collection_credit_oaya_account_id',
        domain=[('deprecated', '=', False)],
        help="Credit account for OAYA in collection entries"
    )
    collection_oaya_percentage = fields.Float(
        string='OAYA Percentage (%)',
        config_parameter='arkzayed_18_realestate_development.collection_oaya_percentage',
        help="Percentage of amount to credit to OAYA account"
    )
    collection_journal_id = fields.Many2one(
        'account.journal',
        string='Collection Journal',
        config_parameter='arkzayed_18_realestate_development.collection_journal_id',
        domain=[('type', '=', 'general')],
        help="Journal for collection entries"
    )

    non_sales_commission_percentage = fields.Float(
        string='Non-Sales Commission %',
        config_parameter='arkzayed_18_realestate_development.non_sales_commission_percentage',
        default=0.5,
        help="Base commission percentage shared among non-sales employees. Each employee's "
             "commission category determines what share of this rate they receive."
    )
    non_sales_commission_collection_percentage = fields.Float(
        string='Non-Sales Commission Collection Threshold %',
        config_parameter='arkzayed_18_realestate_development.non_sales_commission_collection_percentage',
        help="Minimum collection percentage required on a contract before non-sales "
             "commission claims are generated for it."
    )

    apply_cents_in_last_line = fields.Boolean(string='Apply Cents in Last Line',
        config_parameter='arkzayed_18_realestate_development.apply_cents_in_last_line')
    apply_to_nearer_ten = fields.Boolean(
        string='Apply to Nearer Ten',
        config_parameter='arkzayed_18_realestate_development.apply_to_nearer_ten'
    )
    installment_price_tolerance = fields.Float(
        string='Installment Price Tolerance',
        config_parameter='arkzayed_18_realestate_development.installment_price_tolerance',
        default=50.0,
        help="When generating installment or maintenance lines, the last line always absorbs "
             "any rounding difference so the lines total exactly the Final Price / Maintenance "
             "Amount. If that difference is larger than this tolerance, generation is refused "
             "instead, since that signals a calculation error rather than normal rounding."
    )

    enable_reservation_expiry_cron = fields.Boolean(
        string="Check Reservation Expiry",
        help="Enable automatic checking and expiring of sale reservations.",
        config_parameter = 'arkzayed_18_realestate_development.enable_reservation_expiry_cron'
    )

    onhold_reservation_expiration_hours = fields.Integer('Allowed Onhold/Initial Reservations Hours',config_parameter='arkzayed_18_realestate_development.onhold_reservation_expiration_hours',default=1)
    unpaid_reservation_expiration_hours = fields.Integer('Allowed Unpaid Reservations Hours',config_parameter='arkzayed_18_realestate_development.unpaid_reservation_expiration_hours', default=1)

    @api.constrains('onhold_reservation_expiration_hours', 'unpaid_reservation_expiration_hours')
    def _check_reservation_expiration_fields(self):
        for rec in self:
            if rec.onhold_reservation_expiration_hours <= 0:
                raise UserError(_('Allowed Onhold/Initial Reservations Hours must be greater than 0'))
            if rec.unpaid_reservation_expiration_hours <= 0:
                raise UserError(_('Allowed Unpaid Reservations Hours must be greater than 0'))

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        cron = self.env.ref(
            'arkzayed_18_realestate_development.ir_cron_check_reservation_expiry_date',
            raise_if_not_found=False
        )
        res.update(
            enable_reservation_expiry_cron=cron.active if cron else False
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()

        cron = self.env.ref(
            'arkzayed_18_realestate_development.ir_cron_check_reservation_expiry_date',
            raise_if_not_found=False
        )
        if cron:
            vals = {'active': self.enable_reservation_expiry_cron}
            # If the setting is checked, reset the nextcall to 10 minutes from now
            if self.enable_reservation_expiry_cron:
                vals['nextcall'] = fields.Datetime.now() + timedelta(minutes=10)

            cron.sudo().write(vals)