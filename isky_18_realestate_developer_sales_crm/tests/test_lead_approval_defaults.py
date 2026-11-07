import os
import re

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from ..models.core.crm_lead import APPROVAL_DECISIONS

SC = 'isky_18_realestate_developer_sales_crm'

# the nine approval-status fields, as (document, role) pairs
APPROVAL_FIELDS = [
    '%s_status_for_%s' % (doc, role)
    for doc in ('eoi', 'reservation', 'contract')
    for role in ('manager', 'financial', 'operations')
]


@tagged('post_install', '-at_install')
class TestLeadApprovalDefaults(TransactionCase):
    """Backlog #44: the nine approval-status fields default to 'pending', and the checks that
    guard them must read 'pending' as "nobody has decided yet", not as an approval attempt.
    A standard Odoo CRM salesperson must therefore be able to create an opportunity, while a
    real decision ('approved' / 'rejected') stays gated on the approver group.

    This suite lives in the module that owns `crm.lead`'s approval fields. The Phase 4 suite in
    `isky_18_realestate_developer_commission` covers the same rule from the commission side.
    """

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        # an email is required: mail.thread posts a tracking message on these records and
        # refuses to send one without a sender address
        self.salesperson = self.env['res.users'].create({
            'name': 'a44_sales', 'login': 'a44_sales', 'email': 'a44_sales@example.com',
            'company_id': self.company.id, 'company_ids': [(6, 0, [self.company.id])],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('sales_team.group_sale_salesman').id])]})
        # someone who really may decide, used to put a genuine decision on the record. Odoo's
        # sudo() sets only the `su` flag and keeps the uid, so `has_group()` still answers for
        # the acting user - a sudo() write cannot stand in for an approver here.
        # group_sale_manager ("all documents") is what a manager approving a salesperson's
        # record holds; group_sale_salesman would be "own documents only".
        self.approver = self.env['res.users'].create({
            'name': 'a44_approver', 'login': 'a44_approver',
            'email': 'a44_approver@example.com',
            'company_id': self.company.id, 'company_ids': [(6, 0, [self.company.id])],
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('sales_team.group_sale_manager').id,
                self.env.ref('%s.approval_manager_group' % SC).id,
                self.env.ref('%s.financial_manager_group' % SC).id,
                self.env.ref('%s.operation_manager_group' % SC).id])]})

        # crm.lead has four NOT NULL columns with no default in this build: medium_id,
        # source_id, type and user_id
        self.source = self.env['utm.source'].search([], limit=1) or \
            self.env['utm.source'].create({'name': 'A44 Source'})
        self.medium = self.env['utm.medium'].search([], limit=1) or \
            self.env['utm.medium'].create({'name': 'A44 Medium'})

    def _opportunity(self, user=None):
        """Created by the acting user and owned by them, so core CRM's own-documents record
        rule is satisfied without widening any group."""
        user = user or self.salesperson
        return self.env['crm.lead'].with_user(user).create({
            'name': 'A44 Opp', 'type': 'opportunity', 'user_id': user.id,
            'company_id': self.company.id,
            'source_id': self.source.id, 'medium_id': self.medium.id,
            'phone': '+20 100 000 0000',
            # is_personal_lead means "do not round-robin this lead"; without it create()
            # reassigns user_id to whoever the rotation picks, and the record would no longer
            # belong to the acting user
            'is_personal_lead': True})

    # -- 1 ---------------------------------------------------------------------------------
    def test_plain_salesperson_creates_opportunity_with_pending_defaults(self):
        """The back-office path: nine @api.constrains must not fire on the 'pending' default."""
        self.assertFalse(
            any(self.salesperson.has_group('%s.%s' % (SC, g)) for g in
                ('approval_manager_group', 'financial_manager_group', 'operation_manager_group')),
            "the acting user must hold no approver group")

        lead = self._opportunity()
        self.assertTrue(lead.id, "a plain salesperson must be able to create an opportunity")
        for fname in APPROVAL_FIELDS:
            self.assertEqual(lead[fname], 'pending',
                             "%s kept its default, so no approval was implied" % fname)

    # -- 2 ---------------------------------------------------------------------------------
    def test_real_decision_still_requires_the_approver_group(self):
        """The gate itself is untouched: a decision by a non-approver is still refused."""
        lead = self._opportunity()
        for fname, decision in (('eoi_status_for_manager', 'approved'),
                                ('contract_status_for_financial', 'rejected'),
                                ('reservation_status_for_operations', 'approved')):
            with self.assertRaises(UserError, msg="%s must stay gated" % fname):
                lead.with_user(self.salesperson).write({fname: decision})

    # -- 3 ---------------------------------------------------------------------------------
    def test_portal_validator_silent_on_pending_defaults(self):
        """`validate_all_constraints_for_portal()` holds a second copy of the same nine checks.
        It is called over RPC by the portal's lead-to-opportunity conversion, so the same rule
        has to hold there: 'pending' is not an approval attempt."""
        lead = self._opportunity()
        result = lead.with_user(self.salesperson).validate_all_constraints_for_portal()
        errors = (result or {}).get('errors', '')
        self.assertNotIn(
            'not allowed to approve', errors,
            "the pending defaults must not be reported as an approval attempt:\n%s" % errors)

    # -- 4 ---------------------------------------------------------------------------------
    def test_portal_validator_reports_a_real_decision_by_a_non_approver(self):
        """The portal copy still reports a genuine decision taken by someone without the
        group - the fix narrows when the check fires, it does not remove the check."""
        lead = self._opportunity()
        # written by someone entitled to decide, so the write itself is allowed and the record
        # reaches the validator carrying a real decision
        lead.with_user(self.approver).write({'eoi_status_for_manager': 'approved'})

        result = lead.with_user(self.salesperson).validate_all_constraints_for_portal()
        self.assertIn(
            'only Manager can approve', (result or {}).get('errors', ''),
            "a real decision by a non-approver must still be reported")

    # -- 5 ---------------------------------------------------------------------------------
    def test_portal_validator_check_7_raises_instead_of_reporting(self):
        """Pins backlog #55, which this run deliberately did not change: check 7
        (reservation_status_for_manager) raises a UserError while the other eight append to
        the message the method returns. Recorded as a test so the inconsistency is visible and
        a later fix has to update this expectation on purpose."""
        lead = self._opportunity()
        lead.with_user(self.approver).write({'reservation_status_for_manager': 'approved'})
        with self.assertRaises(UserError):
            lead.with_user(self.salesperson).validate_all_constraints_for_portal()

    # -- 6 ---------------------------------------------------------------------------------
    def test_no_truthiness_test_left_on_an_approval_status(self):
        """Guard against a third copy. #44 was fixed twice because the same nine checks were
        written out twice; any new `if <record>.<x>_status_for_<y>` without the
        APPROVAL_DECISIONS membership test is the same bug again."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pattern = re.compile(
            r'\bif\s+[A-Za-z_][A-Za-z0-9_]*\.((?:eoi|reservation|contract)'
            r'_status_for_(?:manager|financial|operations|sales))\b(?!\s*(?:in|==|!=|not\s+in))')
        offenders = []
        for dirpath, _dirs, files in os.walk(root):
            if '__pycache__' in dirpath or os.sep + 'tests' in dirpath:
                continue
            for fn in files:
                if not fn.endswith('.py'):
                    continue
                path = os.path.join(dirpath, fn)
                with open(path, encoding='utf-8') as fh:
                    for lineno, line in enumerate(fh, 1):
                        if pattern.search(line):
                            offenders.append('%s:%d %s' % (
                                os.path.relpath(path, root), lineno, line.strip()))
        self.assertFalse(
            offenders,
            "an approval status is being tested for truthiness, so the 'pending' default "
            "counts as an approval again (#44):\n%s" % '\n'.join(offenders))

    # -- 7 ---------------------------------------------------------------------------------
    def test_pending_is_not_a_decision(self):
        """The rule itself, stated once: only these two values are decisions."""
        self.assertEqual(set(APPROVAL_DECISIONS), {'approved', 'rejected'})
        selection = dict(self.env['crm.lead']._fields['eoi_status_for_manager'].selection)
        self.assertIn('pending', selection,
                      "'pending' must remain a selectable value, it is the default")
        self.assertFalse(
            set(APPROVAL_DECISIONS) - set(selection),
            "every value treated as a decision must exist in the field's selection")
