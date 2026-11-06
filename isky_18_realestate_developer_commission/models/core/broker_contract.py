from odoo import models, fields, _, api


class BrokerContract(models.Model):
    _name = "broker.contract"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    name = fields.Char(string='Contract Reference', required=True, copy=False, readonly=True, index=True,
                       default='New')
    broker_company = fields.Many2one('res.partner', string='Partner', domain=['|', ('is_broker', '=', True), ('is_ambassador', '=', True)], tracking=True)
    collection = fields.Integer('Collection %', tracking=True)
    contract_issue_date = fields.Date('Contract Issue Date', tracking=True)
    contract_start_date = fields.Date('Contract Start Date', tracking=True)
    contract_end_date = fields.Date('Contract End Date', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    line_ids = fields.One2many(comodel_name='broker.contract.line', inverse_name='broker_contract_id', tracking=True)
    broker_type = fields.Selection([
        ('open_race', 'Open Race'),
        ('assign_to_sales', 'Assign to Sales')
    ], string='Broker Type', tracking=True)
    broker_team_id = fields.Many2one(
        'broker.team',
        compute='_compute_broker_team_id',
        store=True,
        string='Broker Team',
    )
    broker_line_ids = fields.One2many(
        related='broker_team_id.line_ids',
        readonly=False,
        string='Broker Team Members',
    )
    broker_company_ref = fields.Char(related='broker_company.ref', string="Broker Company Reference")

    @api.depends('broker_company')
    def _compute_broker_team_id(self):
        for rec in self:
            if not rec.broker_company:
                rec.broker_team_id = False
                continue
            team = self.env['broker.team'].search(
                [('broker_id', '=', rec.broker_company.id)], limit=1
            )
            if not team:
                team = self.env['broker.team'].create({'broker_id': rec.broker_company.id})
            rec.broker_team_id = team

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('broker.contract') or _('New')
        return super().create(vals)


class BrokerContractLine(models.Model):
    _name = "broker.contract.line"

    start_date = fields.Date('Start Date', tracking=True)
    end_date = fields.Date('End Date', tracking=True)
    commission = fields.Float('Commission', tracking=True, default=3.0)
    broker_contract_id = fields.Many2one(comodel_name='broker.contract')
