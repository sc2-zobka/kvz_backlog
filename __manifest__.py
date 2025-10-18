{
    'name': "kvz_backlog",
    'summary': """
        Allows to manage each confirmed sales order invoiceable line in a backlog manager""",

    'description': """
        Allows to manage each confirmed sales order invoiceable line in a backlog manager
    """,
    'author': "",
    'website': "",
    'installable' : True,
    'application': True,
    'category': 'Sales/Sales',
    'version': "17.0.1.0.2",
    'depends': [
        'sale',
        'sale_timesheet',
        'project',
        'sale_project',
        'mail',
        'planning',
    ],
    'data': [
        'demo/data.xml',
        # 'demo/cron.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/sale_project_security.xml',
        'wizard/forecast_view.xml',
        'wizard/replan_view.xml',
        'wizard/forecast_status_update.xml',
        'views/backlog_view.xml',
        'views/backlog_stages.xml',
        'views/group_access.xml',
        'views/sale_project.xml',
        'views/backlog_menus.xml',
        
    ],
    'license': 'LGPL-3',
}
