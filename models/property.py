from odoo import api, fields, models


class ApricotProperty(models.Model):
    _name = "apricot.property"
    _description = "Property"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, tracking=True, index=True)
    supervisor_id = fields.Many2one(
        "res.users",
        string="Supervisor",
        tracking=True,
        help="Main supervisor responsible for this property.",
    )
    active = fields.Boolean(default=True)
    notes = fields.Text()
    ticket_count = fields.Integer(compute="_compute_counts")
    job_card_count = fields.Integer(compute="_compute_counts")
    requester_count = fields.Integer(compute="_compute_counts")

    _sql_constraints = [
        ("property_name_unique", "unique(name)", "A property with this name already exists."),
    ]

    @api.depends()
    def _compute_counts(self):
        Ticket = self.env["apricot.ticket"].sudo()
        JobCard = self.env["apricot.job.card"].sudo()
        Requester = self.env["apricot.ticket.requester"].sudo()
        for record in self:
            record.ticket_count = Ticket.search_count([("property_id", "=", record.id)])
            record.job_card_count = JobCard.search_count([("property_id", "=", record.id)])
            record.requester_count = Requester.search_count([("property_id", "=", record.id)])

    def action_view_tickets(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Tickets",
            "res_model": "apricot.ticket",
            "view_mode": "kanban,list,form,pivot,graph",
            "domain": [("property_id", "=", self.id)],
            "context": {"default_property_id": self.id},
        }

    def action_view_job_cards(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Job Cards",
            "res_model": "apricot.job.card",
            "view_mode": "kanban,list,form,pivot,graph",
            "domain": [("property_id", "=", self.id)],
            "context": {"default_property_id": self.id},
        }
