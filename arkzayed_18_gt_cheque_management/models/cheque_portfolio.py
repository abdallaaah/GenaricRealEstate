from odoo import models, fields, api

class ChequePortfolio(models.Model):
    _name = 'cheque.portfolio'

    name = fields.Char(string="Number")

    bank_id = fields.Many2one('res.bank')

    partner_ids = fields.Many2many('res.partner', compute='_compute_partner_ids', store=True)

    cheque_ids = fields.Many2many(
        'cheque.manage',
        'cheque_portfolio_cheque_manage_rel',
        'cheque_portfolio_id',
        'cheque_manage_id',
    )
    _sql_constraints = [
        ('unique_name', 'UNIQUE(name)', 'Portfolio number is already exists')
    ]

    @api.depends('cheque_ids')
    def _compute_partner_ids(self):
        for rec in self:
            if rec.cheque_ids:
                rec.partner_ids = rec.cheque_ids.mapped('payer').ids
            else:
                rec.partner_ids = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code('cheque.portfolio')
        return super().create(vals_list)

