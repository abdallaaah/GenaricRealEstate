from datetime import timedelta

from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_crm_unit_hold = fields.Boolean(
        string="Enable Unit Hold",
        config_parameter='realestate.enable_unit_hold',
        help="Allow users to temporarily hold units directly from the CRM opportunity."
    )

    crm_unit_hold_duration = fields.Integer(
        string="Unit Hold Duration (Hours)",
        config_parameter='realestate.unit_hold_duration',
        default=24,
        help="Default duration in hours a unit can be held directly from an opportunity."
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        # Ensure the settings checkbox matches the actual state of the cron job
        cron = self.env.ref(
            'arkzayed_18_realestate_developer_crm.ir_cron_release_held_units',
            raise_if_not_found=False
        )
        if cron:
            res.update(enable_crm_unit_hold=cron.active)
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()

        cron = self.env.ref(
            'arkzayed_18_realestate_developer_crm.ir_cron_release_held_units',
            raise_if_not_found=False
        )
        if cron:
            vals = {'active': self.enable_crm_unit_hold}
            # If the setting is checked, reset the nextcall to 10 minutes from now
            if self.enable_crm_unit_hold:
                vals['nextcall'] = fields.Datetime.now() + timedelta(minutes=10)

            cron.sudo().write(vals)