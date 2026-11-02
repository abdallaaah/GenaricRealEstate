# -*- coding: utf-8 -*-
##############################################################################
#
#    Globalteckz Pvt Ltd
#    Copyright (C) 2013-Today(www.globalteckz.com).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    'name' : 'Arkzayed 18 Cheque/Check Management in Odoo',
    'version' : '1.0',
    'author' : 'Globalteckz',
    'category' : 'Accounting',
    'description' : """
check management
cheque management
bank check
bank cheque
checks management
cheques management
bank checks
bank cheques
outgoing check
outgoing cheque
incoming check
incoming cheque
outgoing checks
outgoing cheques
incoming checks
incoming cheques
out check
out cheque
income check
income cheque
out checks
out cheques
income checks
income cheques
check management in odoo
cheque management in odoo
bank check in odoo
bank cheque in odoo
checks management in odoo
cheques management in odoo

""",
    'website': 'https://www.globalteckz.com',
    'summary': """This module will help to track outgoing checks and incoming checks outgoing check and incoming check outgoing cheque and incoming cheque outgoing cheques and incoming cheques Post Dated Cheque management PDC cheque management account check post dated check PDC check customer check vendor check writing account check writing account cheque writing incoming check outgoing check print cheque print check bank cheque printing check""",
    # This module is the single, self-contained cheque module (it fully absorbs the
    # former Globalteckz `gt_cheque_management`, which has been removed from the repo).
    'depends' : ['base', 'account', 'attachment_indexation', 'project', 'isky_18_realestate_developer_accounting'],
    "license" : "Other proprietary",
    'images': ['static/description/banner.png'],
    "price": "49.00",
    "currency": "EUR",
    'data': [
        'security/ir.model.access.csv',

        'data/ir_sequence.xml',

        'report/report_wizard_view.xml',
        'report/cheque_report.xml',

        'wizard/cheque_wizard.xml',

        'views/ir_sequence_data.xml',
        'views/return_reason.xml',
        'views/cheque_portfolio_views.xml',
        'views/cheque_manage.xml',
        'views/res_config.xml',
        'views/res_company_views.xml',
        'views/res_bank.xml',
        'views/account_account_views.xml',
        'views/res_partner_views.xml',
        'views/account_payment.xml',

        'report/outgoing_check_report.xml',
        'report/incoming_check_report.xml',
        'report/cheque_outgoing_report.xml',


        'wizard/under_collected_wizard.xml',
    ],
    'qweb' : [
    ],
    'test': [
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
