from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta


class VendorCommitment(models.Model):
    _name = 'vendor.commitment'
    _description = 'Vendor Commitments'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "end_date desc, id desc"

    vendor_id = fields.Many2one('res.partner', string='Vendor Name',domain=[('supplier_rank', '>', 0)],required=True,tracking=True)
    commitment_type = fields.Selection([
        ('permits', 'Permits'),
        ('letter_of_guarantee', 'Letter of Guarantee'),
    ], string='Type', required=True,default="permits",tracking=True)
    start_date = fields.Date(string='Start Date', required=True,tracking=True)
    end_date = fields.Date(string='End Date', required=True,tracking=True)
    building_ids = fields.Many2many('real.estate.building','vendor_commitment_building_rel','commitment_id','building_id',string='Building Names',tracking=True)
    building_names_display = fields.Char(string='Buildings', compute='_compute_building_names_display', store=True)
    permit_name = fields.Char(string='Name', tracking=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency',default=lambda self: self.env.company.currency_id)
    lg_value = fields.Monetary(string='LG Value', currency_field='currency_id',tracking=True)
    check_number = fields.Char(string="Check Number", tracking=True)
    beneficiary_bank_id = fields.Many2one("res.bank", string="Beneficiary Bank", tracking=True)
    issuing_bank_id = fields.Many2one("res.bank", string="Issuing Bank", tracking=True)
    guarantee_checks_percent = fields.Float(string="Guarantee Checks (% of Contract)", tracking=True, digits=(5, 2))

    is_active = fields.Boolean(string="Active", compute="_compute_is_active", store=True)
    description = fields.Text()

    @api.depends('building_ids','building_ids.name')
    def _compute_building_names_display(self):
        for rec in self:
            if rec.building_ids:
                rec.building_names_display = ', '.join(rec.building_ids.mapped('name'))
            else:
                rec.building_names_display = ''

    @api.depends("start_date", "end_date")
    def _compute_is_active(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.end_date:
                rec.is_active = False
                continue
            rec.is_active = (today <= rec.end_date) and (not rec.start_date or rec.start_date <= today)

    def _cron_check_vendor_commitment_notifications(self):
        today = fields.Date.context_today(self)
        alert_date = today + timedelta(days=10)

        records = self.search([
            ("end_date", ">=", today),
            ("end_date", "<=", alert_date),
        ])

        if not records:
            return

        group = self.env.ref(
            "arkzayed_18_realestate_development.group_vendor_commitment_user",
            raise_if_not_found=False
        )
        if not group or not group.users:
            return

        partners = group.users.mapped("partner_id")

        for rec in records:
            days_left = (rec.end_date - today).days

            building_info = rec.building_names_display if rec.commitment_type == 'letter_of_guarantee' else rec.permit_name

            body = (
                "<b>Vendor Commitment Alert</b><br/>"
                f"Vendor: <b>{rec.vendor_id.name}</b><br/>"
                f"{'Building' if rec.commitment_type == 'letter_of_guarantee' else 'Name'}: <b>{building_info or 'N/A'}</b><br/>"
                f"End Date: <b>{rec.end_date}</b><br/>"
                f"Remaining: <b>{days_left}</b> day(s)"
            )

            rec.message_post(
                body=body,
                body_is_html=True,
                subtype_xmlid="mail.mt_note",
                partner_ids=partners.ids,
            )