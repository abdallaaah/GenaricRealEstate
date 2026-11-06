from odoo import api, fields, models, _

class MaintenanceConfig(models.Model):
    _name = 'maintenance.config'
    _description = 'Maintenance Configuration'

    maintenance_default = fields.Boolean(
        string='Maintenance Checked by Default',
        default=True
    )
    maintenance_price_method_default = fields.Selection([
        ('fixed_amount', 'Fixed Amount'),
        ('percentage', 'Percentage From Unit Price'),
        ('discount', 'Percentage After Discount')
    ], string='Maintenance Price Method Default', default='percentage')
    
    maintenance_percentage_default = fields.Float(
        string='Maintenance Percentage Default (%)',
        default=8.0
    )

    maintenance_amount_default = fields.Float(
        string='Maintenance Fixed Amount Default',
        default=0.0
    )

    @api.model
    def get_config(self):
        """The lazy singleton. Read and created with sudo() deliberately.

        12.2: this is called from sale_reservation._default_maintenance() while an ordinary
        user creates a reservation. Bootstrapping a missing configuration row is a system
        action, not a user action - requiring the user to hold configuration-write rights
        would mean every salesperson needs them just to open a reservation, which would make
        the configuration ACL meaningless. Only the default row is created here; nothing
        user-supplied is written.
        """
        config = self.sudo().search([], limit=1)
        if not config:
            config = self.sudo().create({})
        return config

    @api.model
    def action_open_config(self):
        config = self.get_config()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Maintenance Configuration',
            'res_model': 'maintenance.config',
            'view_mode': 'form',
            'res_id': config.id,
            'target': 'current',
        }
