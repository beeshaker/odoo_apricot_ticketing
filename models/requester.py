from odoo import api, fields, models


class ApricotTicketRequester(models.Model):
    _name = "apricot.ticket.requester"
    _description = "Ticket Requester / WhatsApp User"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    whatsapp_number = fields.Char(required=True, tracking=True, index=True)
    partner_id = fields.Many2one("res.partner", string="Linked Contact")
    property_id = fields.Many2one("apricot.property", tracking=True)
    unit_number = fields.Char(tracking=True)
    terms_accepted = fields.Boolean(default=False, tracking=True)
    terms_accepted_at = fields.Datetime(tracking=True)
    last_action = fields.Char()
    last_action_timestamp = fields.Datetime()
    temp_category_id = fields.Many2one("apricot.ticket.category", string="Temporary Category")
    active = fields.Boolean(default=True)
    ticket_count = fields.Integer(compute="_compute_ticket_count")

    _sql_constraints = [
        (
            "requester_whatsapp_unique",
            "unique(whatsapp_number)",
            "A requester with this WhatsApp number already exists.",
        ),
    ]

    def _compute_ticket_count(self):
        Ticket = self.env["apricot.ticket"].sudo()
        for record in self:
            record.ticket_count = Ticket.search_count([("requester_id", "=", record.id)])

    def action_accept_terms(self):
        for record in self:
            record.write({
                "terms_accepted": True,
                "terms_accepted_at": fields.Datetime.now(),
            })

    def action_view_tickets(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Tickets",
            "res_model": "apricot.ticket",
            "view_mode": "kanban,list,form,pivot,graph",
            "domain": [("requester_id", "=", self.id)],
            "context": {
                "default_requester_id": self.id,
                "default_property_id": self.property_id.id,
                "default_unit_number": self.unit_number,
            },
        }
