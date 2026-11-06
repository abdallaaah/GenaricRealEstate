from odoo import models, fields


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

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Archive location name must be unique!'),
        ('code_unique', 'unique(code)', 'Archive location code must be unique!')
    ]
