import secrets
from odoo import api, fields, models, _


class ApricotJobCard(models.Model):
    _name = "apricot.job.card"
    _description = "Job Card"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True, index=True)
    ticket_id = fields.Many2one("apricot.ticket", tracking=True, ondelete="set null")
    property_id = fields.Many2one("apricot.property", tracking=True, index=True)
    unit_number = fields.Char(tracking=True)
    created_by_user_id = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)
    assigned_user_id = fields.Many2one("res.users", string="Assigned To", tracking=True)
    title = fields.Char(required=True, tracking=True)
    description = fields.Text(required=True, tracking=True)
    activities = fields.Text()
    estimated_cost = fields.Monetary(currency_field="currency_id")
    actual_cost = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)
    status = fields.Selection(
        [
            ("open", "Open"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("signed_off", "Signed Off"),
            ("cancelled", "Cancelled"),
        ],
        default="open",
        tracking=True,
        index=True,
    )
    completed_at = fields.Datetime(readonly=True)
    public_token = fields.Char(copy=False, readonly=True, index=True)
    public_token_created_at = fields.Datetime(readonly=True)
    signoff_ids = fields.One2many("apricot.job.card.signoff", "job_card_id", string="Signoffs")
    attachment_count = fields.Integer(compute="_compute_attachment_count")

    _sql_constraints = [
        ("unique_ticket_job_card", "unique(ticket_id)", "A job card already exists for this ticket."),
        ("unique_public_token", "unique(public_token)", "This public token is already used."),
    ]

    @api.onchange("ticket_id")
    def _onchange_ticket_id(self):
        for record in self:
            if record.ticket_id:
                record.property_id = record.ticket_id.property_id
                record.unit_number = record.ticket_id.unit_number
                record.assigned_user_id = record.ticket_id.assigned_user_id
                record.title = record.ticket_id.name
                record.description = record.ticket_id.issue_description

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("apricot.job.card") or "New"
            if vals.get("ticket_id"):
                ticket = self.env["apricot.ticket"].browse(vals["ticket_id"])
                vals.setdefault("property_id", ticket.property_id.id or False)
                vals.setdefault("unit_number", ticket.unit_number)
                vals.setdefault("assigned_user_id", ticket.assigned_user_id.id or False)
        records = super().create(vals_list)
        for record in records:
            record.message_post(body=_("Job card created."))
        return records

    def _compute_attachment_count(self):
        Attachment = self.env["ir.attachment"].sudo()
        for record in self:
            record.attachment_count = Attachment.search_count([
                ("res_model", "=", record._name),
                ("res_id", "=", record.id),
            ])

    def action_open_form(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Job Card",
            "res_model": "apricot.job.card",
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
        }

    def action_start(self):
        self.write({"status": "in_progress"})

    def action_complete(self):
        self.write({"status": "completed", "completed_at": fields.Datetime.now()})

    def action_cancel(self):
        self.write({"status": "cancelled"})

    def action_generate_public_token(self):
        for record in self:
            if not record.public_token:
                record.write({
                    "public_token": secrets.token_urlsafe(32),
                    "public_token_created_at": fields.Datetime.now(),
                })

    def action_view_attachments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Attachments",
            "res_model": "ir.attachment",
            "view_mode": "list,form",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "context": {"default_res_model": self._name, "default_res_id": self.id},
        }


class ApricotJobCardSignoff(models.Model):
    _name = "apricot.job.card.signoff"
    _description = "Job Card Signoff"
    _order = "signed_at desc, id desc"

    job_card_id = fields.Many2one("apricot.job.card", required=True, ondelete="cascade")
    signed_by_name = fields.Char(required=True)
    signed_by_role = fields.Char()
    signoff_notes = fields.Text()
    signature = fields.Binary(attachment=True)
    signature_filename = fields.Char()
    signed_at = fields.Datetime(default=fields.Datetime.now)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record.job_card_id.write({"status": "signed_off"})
            record.job_card_id.message_post(body=_("Job card signed off by %s.") % record.signed_by_name)
        return records
