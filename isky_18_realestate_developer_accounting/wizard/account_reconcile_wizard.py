from odoo import api, models


class AccountReconcileWizard(models.TransientModel):
    _inherit = 'account.reconcile.wizard'

    @api.depends('company_id')
    def _compute_journal_id(self):
        """Force the write-off move of a vendor-bill reconciliation into the
        journal flagged with ``is_reconcile_journal`` so the move's ``name``
        continues that journal's sequence (e.g. PBNK/2026/00007)."""
        super()._compute_journal_id()
        for wizard in self:
            if any(line.move_id.move_type == 'in_invoice' for line in wizard.move_line_ids):
                reconcile_journal = self.env['account.journal']._get_reconcile_journal(wizard.company_id)
                if reconcile_journal:
                    wizard.journal_id = reconcile_journal
