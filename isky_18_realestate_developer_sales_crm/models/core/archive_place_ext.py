from odoo import models, fields, api


class ArchivePlace(models.Model):
    _inherit = 'archive.place'

    sale_proposal_ids = fields.One2many(
        'sale.proposal',
        'archive_place_id',
        string='Contracts'
    )
    contract_count = fields.Integer(
        string='Contract Count',
        compute='_compute_contract_count',
        help="Number of contracts stored in this location",
        store=True
    )

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
