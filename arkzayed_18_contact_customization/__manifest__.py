# -*- coding: utf-8 -*-
{
    'name': "Arkzayed Contact Customization",
    'summary': "Contact Customization",
    'description': """Contact Customization""",
    'author': "iSkyDev",
    'website': "https://www.iskydev.com",
    'category': 'Uncategorized',
    'version': '0.2',
    # any module necessary for this one to work correctly
    'depends': ['base','contacts', 'account', 'sale', 'purchase'],

    # always loaded
    'data': [
        'views/res_partner_views.xml',
        'views/res_company_views.xml',
        'views/portal.xml',
        'views/res_config_settings_views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [],

    'application': True,
    'installable': True,
}