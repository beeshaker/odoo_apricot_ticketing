from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    apricot_whatsapp_number = fields.Char(string="WhatsApp Number")
    apricot_default_property_id = fields.Many2one(
        "apricot.property",
        string="Default Property",
        help="Primary property used for supervisors/caretakers in Apricot Ticketing.",
    )
