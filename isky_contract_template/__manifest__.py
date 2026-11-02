# -*- coding: utf-8 -*-
{
    'name': "Contract Template",
    'summary': "",
    'description': """

    """,
    'author': "iSkyDev",
    'website': "https://www.iskydev.com",
    'category': 'Uncategorized',
    'version': '0.1',
    'depends': ['base', 'sale', 'arkzayed_18_realestate_development'],
    'data': [
        'security/ir.model.access.csv',
        'views/dynamic_template_views.xml',
        'views/sale_proposal_dynamic_contract_template.xml',
        'data/action_server.xml',
        'views/sale_proposal_views.xml',
    ],
}

