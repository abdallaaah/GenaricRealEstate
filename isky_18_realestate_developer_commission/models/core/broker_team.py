from odoo import models, fields, api

class BrokerTeam(models.Model):
    _name = "broker.team"
    _rec_name = 'broker_name'


    broker_id = fields.Many2one(
        'res.partner', string='Brokers',
        domain=['|', ('is_broker', '=', True), ('is_ambassador', '=', True)],
        tracking=True
    )
    broker_name = fields.Char(
        related='broker_id.name',
        string='Broker Name',
        store=True
    )
    line_ids = fields.One2many(comodel_name='broker.team.member', inverse_name='broker_team_id', tracking=True)


class BrokerTeamMember(models.Model):
    _name = "broker.team.member"
    _rec_name = 'partner_id'

    partner_id = fields.Many2one('res.partner', string='Agent', required=True, domain=[('is_agent', '=', True)])
    commission = fields.Float(
        string='Commission %', default=0.5,
        help='Percentage paid to this agent'
    )
    broker_team_id = fields.Many2one(comodel_name='broker.team')
