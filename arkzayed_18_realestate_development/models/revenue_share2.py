from odoo import api, fields, models


class RevenueShare(models.Model):
    _name = 'revenue.share2'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'customer_id'

    customer_id = fields.Many2one(comodel_name="res.partner")
    rental_fee = fields.Float()
    revenue_share = fields.Float(string="Revenue Share %",)
    sales = fields.Float()
    revenue_share_amount = fields.Float(
        string="Revenue Share Amount",
        compute="_compute_revenue_share_amount",
        store=True)
    tax_id = fields.Many2one(comodel_name="account.tax")
    currency_id = fields.Many2one(comodel_name="res.currency")
    date = fields.Date(string="Date", required=True)

    invoice_ids = fields.One2many('account.move', 'revenue_share_id', string="Invoices")
    invoice_count = fields.Integer(string="Invoice Count", compute="_compute_invoice_count")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)


    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for record in self:
            record.invoice_count = len(record.invoice_ids)

    def action_create_invoice(self):
        for record in self:
            invoice_vals = {
                'move_type': 'out_invoice',
                'partner_id': record.customer_id.id,
                'invoice_date': record.date,
                'currency_id': record.currency_id.id,
                'invoice_line_ids': [
                    (0, 0, {
                        'name': 'Revenue Share',
                        'quantity': 1,
                        'price_unit': record.revenue_share_amount,
                        'tax_ids': [(6, 0, [record.tax_id.id])] if record.tax_id else False,
                    })
                ],
                'revenue_share_id': record.id,  # Link the invoice to the record
            }
            invoice = self.env['account.move'].create(invoice_vals)
            return {
                'name': 'Invoice',
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': invoice.id,
            }

    def action_view_invoices(self):
        return {
            'name': 'Invoices',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('revenue_share_id', 'in', self.ids)],
            'context': {'create': False},
        }
