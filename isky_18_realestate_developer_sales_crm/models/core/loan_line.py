import calendar
import datetime
from datetime import date, datetime, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, AccessError
from odoo.tools.translate import _
from stdnum.exceptions import ValidationError


class LoanLine(models.Model):
    _name = "loan.line"
    _description = "Loan Line"
    _order = "serial"

    name = fields.Char("Name")
    date = fields.Date("Date")
    serial = fields.Integer("#")
    amount = fields.Float("Payment", digits=(16, 4))
    paid = fields.Boolean("Paid")
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)

    reservation_id = fields.Many2one("real.estate.lease.reservation", "", ondelete="cascade", readonly=True)
    installment_contract_id = fields.Many2one("real.estate.lease.contract", "", ondelete="cascade", readonly=True)
    maintenance_contract_id = fields.Many2one("real.estate.lease.contract", "", ondelete="cascade", readonly=True)
    parking_fees_contract_id = fields.Many2one("real.estate.lease.contract", "", ondelete="cascade", readonly=True)
    installments_parking_contract_id = fields.Many2one("sale.contract", "", ondelete="cascade", readonly=True)
    installments_parking_sale_proposal_id = fields.Many2one("sale.proposal", "", ondelete="cascade", readonly=True)

    partner_id = fields.Many2one('res.partner', string="Partner")
    project_id = fields.Many2one('realestate.project', string="Project")
    unit_id = fields.Many2one('real.estate.unit', string="Unit")
    user_id = fields.Many2one('res.users', string="User")

    journal_id = fields.Many2one('account.journal')
    invoice_id = fields.Many2one("account.move", string="Invoice", )
    invoice_revenue1_id = fields.Many2one("account.move", string="Invoice Rev1")
    invoice_revenue2_id = fields.Many2one("account.move", string="Invoice Rev2")
    payment_state = fields.Selection(related="invoice_id.payment_state", readonly=True)
    invoice_state = fields.Selection(related="invoice_id.state", readonly=True)
    amount_residual = fields.Monetary(related="invoice_id.amount_residual", readonly=True)
    currency_id = fields.Many2one(related="invoice_id.currency_id", readonly=True)
    invoice_revenue1_state = fields.Selection(related="invoice_revenue1_id.state", readonly=True)
    invoice_revenue2_state = fields.Selection(related="invoice_revenue2_id.state", readonly=True)


    invoice_revenue1_type = fields.Selection(related='invoice_revenue1_id.revenue_share_type')
    invoice_revenue2_type = fields.Selection(related='invoice_revenue2_id.revenue_share_type')
    tax_ids = fields.Many2many("account.tax", string="Tax")
    vat_id = fields.Many2one("account.tax", string="Vat")
    total_amount = fields.Float("Total Amount", compute='calculate_total_amount', digits=(16, 4))
    sales_amount = fields.Float(readonly=False)
    # difference = fields.Float(compute='_compute_the_diff')

    type = fields.Selection([
        ('installment', 'Installment'),
        ('service_charge', 'Service Charge'),
        ('parking_fees', 'Parking Fees'),
        ('marketing_fees', 'Marketing Fees'),
        ('share_revenue', 'Revenue Share'),
    ])


    @api.depends('vat_id', 'amount')
    def calculate_total_amount(self):
        for rec in self:
            rec.total_amount = (rec.vat_id.amount / 100) * rec.amount + rec.amount

    def make_invoice(self):
        move_obj = self.env['account.move']
        journal_pool = self.env["account.journal"]

        if not move_obj.check_access_rights('create', False):
            try:
                self.check_access_rights('write')
                self.check_access_rule('write')
            except AccessError:
                raise UserError("You do not have access to create or edit invoices")

        for rec in self:
            installment_invoice = self._context.get('installment_invoice')
            maintenance_invoice = self._context.get('maintenance_invoice')
            service_charge_invoice = self._context.get('service_charge_invoice')
            parking_rental_fees_invoices = self._context.get('parking_invoice')
            parking_installment_invoices = self._context.get('parking_installment_invoice')
            proposal_maintenance_invoice = self._context.get('proposal_maintenance_invoice')  # here
            parking_lease_proposal_invoice = self._context.get('parking_lease_proposal_invoice')
            marketing_invoice = self._context.get('marketing_invoice')
            revenue_share_1_invoice = self._context.get('proposal_revenue_share1_invoice')
            revenue_share_2_invoice = self._context.get('proposal_revenue_share2_invoice')

            analytic_distribution = {}
            user_project_id = self.env.user.realestate_project_ids[0] if self.env.user.realestate_project_ids else None

            if user_project_id:
                analytic_distribution[user_project_id.analytic_account_id.id] = 100


            journal = journal_pool.search([("type", "=", "sale")], limit=1)
            inv_dict = {
                "move_type": "out_invoice",
                "journal_id": journal.id,
                "line_id": rec.id,
                "invoice_date_due": rec.date,
                "invoice_user_id": self.env.user.id,
                "company_id": self.env.company.id,
                "invoice_line_ids": [],
            }

            line_vals = {
                "name": rec.name,
                "quantity": 1,
                "price_unit": rec.amount,
                'analytic_distribution': analytic_distribution,
            }
            if revenue_share_1_invoice:
                line_vals.update({'price_unit': rec.difference, "name": (rec.name + " - Revenue Share 1")})
                inv_dict.update({'revenue_share_type': 'rev1'})
            if revenue_share_2_invoice:
                line_vals.update(
                    {'price_unit': rec.revenue_share_2_amount_line, "name": (rec.name + " - Revenue Share 2")})
                inv_dict.update({'revenue_share_type': 'rev2'})

            if rec.vat_id:
                line_vals.update({"tax_ids": [(6, 0, [rec.vat_id.id])]})

            inv_dict["invoice_line_ids"] = [
                (
                    0,
                    None,
                    line_vals
                )
            ]

            invoice = move_obj.create(inv_dict)
            if revenue_share_1_invoice:
                rec.invoice_revenue1_id = invoice.id
            elif revenue_share_2_invoice:
                rec.invoice_revenue2_id = invoice.id
            else:
                rec.invoice_id = invoice.id

    def view_invoice(self):
        invoice_share1_type = self._context.get('revenue_share1_type')
        invoice_share2_type = self._context.get('revenue_share2_type')
        if invoice_share1_type:
            move = self.env["account.move"].sudo().search(
                [("line_id", "=", self.id), ('revenue_share_type', '=', 'rev1')])
        if invoice_share2_type:
            move = self.env["account.move"].sudo().search(
                [("line_id", "=", self.id), ('revenue_share_type', '=', 'rev2')])
        if not invoice_share1_type and not invoice_share2_type:
            move = self.env["account.move"].sudo().search(
                [("line_id", "=", self.id), ('revenue_share_type', '!=', 'rev1'), ('revenue_share_type', '!=', 'rev2')])

        return {
            "name": _("Invoice"),
            "view_type": "form",
            "res_id": move.id,
            "view_mode": "form",
            "res_model": "account.move",
            "type": "ir.actions.act_window",
            "target": "current",
        }

    # @api.depends('revenue_share_1_amount_line', 'total_amount')
    # def _compute_the_diff(self):
    #     for rec in self:
    #         if rec.revenue_share_1_amount_line and rec.total_amount > 0:
    #             difference = rec.revenue_share_1_amount_line - rec.total_amount
    #             rec.difference = difference if difference > 0 else 0
    #         else:
    #             rec.difference = 0

    def make_auto_invoice(self):
        today = fields.Date.today()
        invoices = self.env['loan.line'].search([('date', '<=', today), ('state', '=', 'contract_approved')])
        for invoice in invoices:
            invoice.with_context({'proposal_maintenance_invoice': 1}).make_invoice()

    def send_multiple_installments_rent(self):
        pass
        # ir_model_data = self.env["ir.model.data"]
        # template_id = ir_model_data.get_object_reference(
        #     "real_estate_bits", "email_template_installment_notification_rent"
        # )[1]
        # template_res = self.env["mail.template"]
        # template = template_res.browse(template_id)
        # template.send_mail(self.id, force_send=True)
