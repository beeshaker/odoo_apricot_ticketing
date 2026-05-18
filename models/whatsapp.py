from odoo import fields, models


class ApricotWhatsappMessage(models.Model):
    _name = "apricot.whatsapp.message"
    _description = "WhatsApp Message"
    _order = "created_at desc, id desc"

    wa_number = fields.Char(index=True)
    direction = fields.Selection([("in", "In"), ("out", "Out")], required=True, default="out", index=True)
    message_type = fields.Char(default="text")
    body_text = fields.Text()
    message_id = fields.Char(index=True, copy=False)
    template_name = fields.Char()
    status = fields.Char()
    error_text = fields.Text()
    meta_json = fields.Text(help="Raw JSON payload from Meta/WhatsApp, stored as text for portability.")
    ticket_id = fields.Many2one("apricot.ticket", ondelete="set null")
    job_card_id = fields.Many2one("apricot.job.card", ondelete="set null")
    verify_url = fields.Text()
    created_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)

    _sql_constraints = [
        ("message_id_unique", "unique(message_id)", "This WhatsApp message has already been logged."),
    ]


class ApricotWhatsappProcessedMessage(models.Model):
    _name = "apricot.whatsapp.processed.message"
    _description = "Processed WhatsApp Message"
    _order = "created_at desc"

    message_id = fields.Char(required=True, index=True)
    created_at = fields.Datetime(default=fields.Datetime.now, required=True)

    _sql_constraints = [
        ("processed_message_unique", "unique(message_id)", "This message has already been processed."),
    ]


class ApricotWhatsappBulkAudit(models.Model):
    _name = "apricot.whatsapp.bulk.audit"
    _description = "Bulk WhatsApp Message Audit"
    _order = "sent_at desc, id desc"

    sent_at = fields.Datetime(default=fields.Datetime.now, required=True)
    property_id = fields.Many2one("apricot.property")
    property_name = fields.Char()
    user_name = fields.Char()
    whatsapp_number = fields.Char()
    status = fields.Char()
    template_name = fields.Char()
    notice_text = fields.Text()


class ApricotWhatsappSession(models.Model):
    _name = "apricot.whatsapp.session"
    _description = "WhatsApp Session / Temporary Registration"
    _order = "updated_at desc, id desc"

    whatsapp_number = fields.Char(required=True, index=True)
    name = fields.Char()
    property_id = fields.Many2one("apricot.property")
    unit_number = fields.Char()
    current_step = fields.Char()
    temp_category_id = fields.Many2one("apricot.ticket.category")
    caption_buffer = fields.Text()
    updated_at = fields.Datetime(default=fields.Datetime.now)
    created_at = fields.Datetime(default=fields.Datetime.now)

    _sql_constraints = [
        ("session_whatsapp_unique", "unique(whatsapp_number)", "A session already exists for this WhatsApp number."),
    ]
