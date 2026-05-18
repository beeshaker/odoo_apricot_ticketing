{
    "name": "Apricot Ticketing",
    "summary": "Internal ticketing, job cards, WhatsApp logs, and requester management",
    "description": """
Apricot Ticketing replaces the Streamlit/MySQL ticketing portal with native Odoo models.
It provides properties, requesters, tickets, job cards, WhatsApp message logs, API endpoints,
and configuration records for stages and categories.
    """,
    "version": "19.0.1.0.0",
    "category": "Services/Helpdesk",
    "author": "Apricot Property Solutions",
    "website": "https://www.apricotproperty.co.ke",
    "license": "LGPL-3",
    "depends": ["base", "mail", "contacts"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/sequences.xml",
        "data/stages_categories.xml",
        "views/property_views.xml",
        "views/requester_views.xml",
        "views/ticket_views.xml",
        "views/job_card_views.xml",
        "views/whatsapp_views.xml",
        "views/menu_views.xml",
        "report/job_card_report.xml",
    ],
    "installable": True,
    "application": True,
}
