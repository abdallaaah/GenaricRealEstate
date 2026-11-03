from odoo import models, fields, api


class ArchivePlace(models.Model):
    """Model to manage physical storage locations for contracts"""

    _name = "archive.place"
    _description = "Archive Place"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "name"

    name = fields.Char(
        string='Archive Location',
        required=True,
        index=True,
        help="Physical location where the contract is stored (e.g., Cabinet A, Shelf 3, Box 12)"
    )
    code = fields.Char(
        string='Location Code',
        index=True,
        help="Short code for quick reference"
    )
    description = fields.Text(
        string='Description',
        help="Additional details about this archive location"
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help="Uncheck to archive this location"
    )
    contract_count = fields.Integer(
        string='Contract Count',
        compute='_compute_contract_count',
        help="Number of contracts stored in this location",
        store=True
    )
    sale_proposal_ids = fields.One2many(
        'sale.proposal',
        'archive_place_id',
        string='Contracts'
    )

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Archive location name must be unique!'),
        ('code_unique', 'unique(code)', 'Archive location code must be unique!')
    ]

    @api.depends('sale_proposal_ids')
    def _compute_contract_count(self):
        """Count contracts stored in each archive location"""
        for record in self:
            record.contract_count = self.env['sale.proposal'].search_count([
                ('archive_place_id', '=', record.id)
            ])

    def action_view_contracts(self):
        """View all contracts in this archive location"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Contracts in {self.name}',
            'res_model': 'sale.proposal',
            'view_mode': 'list,form',
            'domain': [('archive_place_id', '=', self.id)],
            'context': {
                'default_archive_place_id': self.id,
                'create': False,
            },
        }
