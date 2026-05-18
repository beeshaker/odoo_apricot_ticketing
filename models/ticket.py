from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ApricotTicketStage(models.Model):
    _name = "apricot.ticket.stage"
    _description = "Ticket Stage"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    fold = fields.Boolean(help="Fold this stage in the kanban view.")
    is_resolved = fields.Boolean(help="Tickets moved here are considered resolved.")
    is_closed = fields.Boolean(help="Tickets moved here are considered closed.")
    active = fields.Boolean(default=True)


class ApricotTicketCategory(models.Model):
    _name = "apricot.ticket.category"
    _description = "Ticket Category"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    default_assigned_user_id = fields.Many2one("res.users", string="Default Assignee")
    description = fields.Text()

    _sql_constraints = [
        ("category_name_unique", "unique(name)", "A category with this name already exists."),
    ]


class ApricotTicket(models.Model):
    _name = "apricot.ticket"
    _description = "Ticket"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    @api.model
    def _default_stage_id(self):
        stage = self.env.ref("apricot_ticketing.stage_open", raise_if_not_found=False)
        if stage:
            return stage.id
        return self.env["apricot.ticket.stage"].search([], order="sequence, id", limit=1).id

    name = fields.Char(default="New", readonly=True, copy=False, tracking=True, index=True)

    requester_id = fields.Many2one(
        "apricot.ticket.requester",
        required=True,
        tracking=True,
        ondelete="restrict",
    )

    requester_whatsapp_number = fields.Char(
        related="requester_id.whatsapp_number",
        store=True,
        readonly=True,
    )

    property_id = fields.Many2one(
        "apricot.property",
        tracking=True,
        index=True,
    )

    unit_number = fields.Char(tracking=True)

    issue_description = fields.Text(required=True, tracking=True)

    category_id = fields.Many2one(
        "apricot.ticket.category",
        required=True,
        tracking=True,
    )

    stage_id = fields.Many2one(
        "apricot.ticket.stage",
        default=_default_stage_id,
        required=True,
        tracking=True,
        group_expand="_read_group_stage_ids",
    )

    assigned_user_id = fields.Many2one(
        "res.users",
        string="Assigned To",
        tracking=True,
    )

    due_date = fields.Date(tracking=True)

    source = fields.Selection(
        [
            ("odoo", "Odoo"),
            ("whatsapp", "WhatsApp"),
            ("email", "Email"),
            ("manual", "Manual"),
        ],
        default="odoo",
        tracking=True,
    )

    is_read = fields.Boolean(default=False, tracking=True)
    reassign_count = fields.Integer(default=0, readonly=True)
    resolved_at = fields.Datetime(readonly=True, tracking=True)

    update_ids = fields.One2many(
        "apricot.ticket.update",
        "ticket_id",
        string="Updates",
    )

    assignment_log_ids = fields.One2many(
        "apricot.ticket.assignment.log",
        "ticket_id",
        string="Assignment Logs",
    )

    category_log_ids = fields.One2many(
        "apricot.ticket.category.log",
        "ticket_id",
        string="Category Logs",
    )

    job_card_id = fields.Many2one(
        "apricot.job.card",
        compute="_compute_job_card",
        string="Job Card",
    )

    job_card_count = fields.Integer(compute="_compute_job_card")
    attachment_count = fields.Integer(compute="_compute_attachment_count")
    status_label = fields.Char(compute="_compute_status_label", store=True)

    @api.depends("stage_id")
    def _compute_status_label(self):
        for record in self:
            record.status_label = record.stage_id.name or ""

    @api.depends("name")
    def _compute_job_card(self):
        JobCard = self.env["apricot.job.card"].sudo()
        for record in self:
            job_card = JobCard.search([("ticket_id", "=", record.id)], limit=1)
            record.job_card_id = job_card
            record.job_card_count = 1 if job_card else 0

    def _compute_attachment_count(self):
        Attachment = self.env["ir.attachment"].sudo()
        for record in self:
            record.attachment_count = Attachment.search_count([
                ("res_model", "=", record._name),
                ("res_id", "=", record.id),
            ])

    @api.model
    def _read_group_stage_ids(self, stages, domain, *args):
        """
        Odoo 19 calls group_expand with fewer arguments than older versions.
        Using *args keeps this compatible whether Odoo passes order or not.
        """
        return stages.search([], order="sequence, id")

    @api.onchange("requester_id")
    def _onchange_requester_id(self):
        for record in self:
            if record.requester_id:
                record.property_id = record.requester_id.property_id
                record.unit_number = record.requester_id.unit_number

    @api.onchange("category_id")
    def _onchange_category_id(self):
        for record in self:
            if (
                record.category_id
                and record.category_id.default_assigned_user_id
                and not record.assigned_user_id
            ):
                record.assigned_user_id = record.category_id.default_assigned_user_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("apricot.ticket") or "New"

            if vals.get("requester_id") and not vals.get("property_id"):
                requester = self.env["apricot.ticket.requester"].browse(vals["requester_id"])
                vals["property_id"] = requester.property_id.id or False
                vals["unit_number"] = vals.get("unit_number") or requester.unit_number

            if vals.get("category_id") and not vals.get("assigned_user_id"):
                category = self.env["apricot.ticket.category"].browse(vals["category_id"])
                if category.default_assigned_user_id:
                    vals["assigned_user_id"] = category.default_assigned_user_id.id

        records = super().create(vals_list)

        for record in records:
            record.message_post(body=_("Ticket created."))

        return records

    def write(self, vals):
        old_values = {
            rec.id: {
                "assigned_user_id": rec.assigned_user_id,
                "category_id": rec.category_id,
                "stage_id": rec.stage_id,
            }
            for rec in self
        }

        result = super().write(vals)

        for rec in self:
            old = old_values.get(rec.id, {})

            if "assigned_user_id" in vals and old.get("assigned_user_id") != rec.assigned_user_id:
                rec.reassign_count += 1

                self.env["apricot.ticket.assignment.log"].create({
                    "ticket_id": rec.id,
                    "old_user_id": old.get("assigned_user_id").id if old.get("assigned_user_id") else False,
                    "new_user_id": rec.assigned_user_id.id if rec.assigned_user_id else False,
                    "changed_by_id": self.env.user.id,
                    "reassign_count": rec.reassign_count,
                })

                rec.message_post(
                    body=_("Assigned user changed to %s.")
                    % (rec.assigned_user_id.name or "Unassigned")
                )

            if "category_id" in vals and old.get("category_id") != rec.category_id:
                self.env["apricot.ticket.category.log"].create({
                    "ticket_id": rec.id,
                    "old_category_id": old.get("category_id").id if old.get("category_id") else False,
                    "new_category_id": rec.category_id.id if rec.category_id else False,
                    "changed_by_id": self.env.user.id,
                })

            if "stage_id" in vals and old.get("stage_id") != rec.stage_id:
                if rec.stage_id.is_resolved or rec.stage_id.is_closed:
                    if not rec.resolved_at:
                        rec.sudo().write({"resolved_at": fields.Datetime.now()})

                rec.message_post(body=_("Stage changed to %s.") % rec.stage_id.name)

        return result

    def action_mark_read(self):
        self.write({"is_read": True})

    def action_set_in_progress(self):
        stage = self.env.ref("apricot_ticketing.stage_in_progress", raise_if_not_found=False)
        if stage:
            self.write({"stage_id": stage.id})

    def action_resolve(self):
        stage = self.env.ref("apricot_ticketing.stage_resolved", raise_if_not_found=False)
        if stage:
            self.write({
                "stage_id": stage.id,
                "resolved_at": fields.Datetime.now(),
            })

    def action_close(self):
        stage = self.env.ref("apricot_ticketing.stage_closed", raise_if_not_found=False)
        if stage:
            for record in self:
                record.write({
                    "stage_id": stage.id,
                    "resolved_at": record.resolved_at or fields.Datetime.now(),
                })

    def action_create_job_card(self):
        self.ensure_one()

        if self.job_card_id:
            return self.action_view_job_card()

        job_card = self.env["apricot.job.card"].create({
            "ticket_id": self.id,
            "property_id": self.property_id.id,
            "unit_number": self.unit_number,
            "assigned_user_id": self.assigned_user_id.id,
            "title": self.name,
            "description": self.issue_description,
        })

        return job_card.action_open_form()

    def action_view_job_card(self):
        self.ensure_one()

        if not self.job_card_id:
            raise UserError(_("No job card has been created for this ticket."))

        return self.job_card_id.action_open_form()

    def action_view_attachments(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Attachments",
            "res_model": "ir.attachment",
            "view_mode": "list,form",
            "domain": [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
            ],
            "context": {
                "default_res_model": self._name,
                "default_res_id": self.id,
            },
        }


class ApricotTicketUpdate(models.Model):
    _name = "apricot.ticket.update"
    _description = "Ticket Update"
    _order = "created_at desc, id desc"

    ticket_id = fields.Many2one(
        "apricot.ticket",
        required=True,
        ondelete="cascade",
    )

    update_text = fields.Text(required=True)

    updated_by_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        required=True,
    )

    created_at = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for record in records:
            record.ticket_id.message_post(body=record.update_text)

        return records


class ApricotTicketAssignmentLog(models.Model):
    _name = "apricot.ticket.assignment.log"
    _description = "Ticket Assignment Log"
    _order = "changed_at desc, id desc"

    ticket_id = fields.Many2one(
        "apricot.ticket",
        required=True,
        ondelete="cascade",
    )

    old_user_id = fields.Many2one(
        "res.users",
        string="Old Assignee",
    )

    new_user_id = fields.Many2one(
        "res.users",
        string="New Assignee",
    )

    changed_by_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
    )

    reason = fields.Text()
    reassign_count = fields.Integer()
    override_by_super_admin = fields.Boolean(default=False)

    changed_at = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
    )


class ApricotTicketCategoryLog(models.Model):
    _name = "apricot.ticket.category.log"
    _description = "Ticket Category Change Log"
    _order = "changed_at desc, id desc"

    ticket_id = fields.Many2one(
        "apricot.ticket",
        required=True,
        ondelete="cascade",
    )

    old_category_id = fields.Many2one(
        "apricot.ticket.category",
        string="Old Category",
    )

    new_category_id = fields.Many2one(
        "apricot.ticket.category",
        string="New Category",
    )

    changed_by_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
    )

    changed_at = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
    )