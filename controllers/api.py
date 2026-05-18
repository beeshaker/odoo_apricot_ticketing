import base64
import json
import os

from odoo import http, fields
from odoo.http import Response, request


class ApricotTicketingAPI(http.Controller):
    """Token-authenticated HTTP endpoints for the WhatsApp Flask backend.

    These routes intentionally use type='http' instead of type='json' so that a normal
    Flask requests.post(..., json=payload) call works without JSON-RPC wrapping.
    """

    def _json_response(self, payload, status=200):
        return Response(
            json.dumps(payload, default=str),
            status=status,
            content_type="application/json; charset=utf-8",
        )

    def _payload(self):
        raw = request.httprequest.get_data(as_text=True) or "{}"
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _authorized(self):
        configured = request.env["ir.config_parameter"].sudo().get_param(
            "apricot_ticketing.api_token"
        )

        configured = configured or os.environ.get("ODOO_TICKETING_API_TOKEN")

        if not configured:
            return False

        configured = str(configured).strip()

        # Option 1: Authorization: Bearer TOKEN
        auth_header = request.httprequest.headers.get("Authorization", "") or ""

        # Option 2: X-API-Key: TOKEN
        api_key_header = request.httprequest.headers.get("X-API-Key", "") or ""

        # Option 3: ?token=TOKEN
        # Use this only for local testing.
        query_token = request.httprequest.args.get("token", "") or ""

        token = ""

        if auth_header:
            auth_header = auth_header.strip()
            if auth_header.lower().startswith("bearer "):
                token = auth_header[7:].strip()
            else:
                token = auth_header.strip()

        if not token and api_key_header:
            token = api_key_header.strip()

        if not token and query_token:
            token = query_token.strip()

        return token == configured

    def _require_auth(self):
        if not self._authorized():
            return self._json_response({"ok": False, "error": "Unauthorized"}, status=401)
        return None

    def _property_from_payload(self, payload):
        Property = request.env["apricot.property"].sudo()
        property_id = payload.get("property_id")
        property_name = payload.get("property_name") or payload.get("property")
        if property_id:
            prop = Property.browse(int(property_id))
            if prop.exists():
                return prop
        if property_name:
            return Property.search([("name", "=ilike", property_name)], limit=1) or Property.create({"name": property_name})
        return Property.browse()

    def _category_from_payload(self, payload):
        Category = request.env["apricot.ticket.category"].sudo()
        category_id = payload.get("category_id")
        category_name = payload.get("category") or payload.get("category_name") or "Other"
        if category_id:
            category = Category.browse(int(category_id))
            if category.exists():
                return category
        return Category.search([("name", "=ilike", category_name)], limit=1) or Category.create({"name": category_name})

    def _requester_from_payload(self, payload, create=True):
        Requester = request.env["apricot.ticket.requester"].sudo()
        whatsapp_number = payload.get("whatsapp_number") or payload.get("wa_number") or payload.get("phone")
        if not whatsapp_number:
            return Requester.browse()
        requester = Requester.search([("whatsapp_number", "=", whatsapp_number)], limit=1)
        if requester or not create:
            return requester
        prop = self._property_from_payload(payload)
        vals = {
            "name": payload.get("name") or payload.get("user_name") or whatsapp_number,
            "whatsapp_number": whatsapp_number,
            "property_id": prop.id or False,
            "unit_number": payload.get("unit_number"),
            "terms_accepted": bool(payload.get("terms_accepted", False)),
        }
        if vals["terms_accepted"]:
            vals["terms_accepted_at"] = fields.Datetime.now()
        return Requester.create(vals)

    @http.route("/apricot_ticketing/api/health", type="http", auth="public", methods=["GET"], csrf=False)
    def health(self, **kwargs):
        return self._json_response({"ok": True, "module": "apricot_ticketing"})

    @http.route("/api/apricot_ticketing/check_user", type="http", auth="public", methods=["POST"], csrf=False)
    def check_user(self, **kwargs):
        auth_error = self._require_auth()
        if auth_error:
            return auth_error
        payload = self._payload()
        requester = self._requester_from_payload(payload, create=False)
        if not requester:
            return self._json_response({"ok": True, "exists": False})
        return self._json_response({
            "ok": True,
            "exists": True,
            "requester": {
                "id": requester.id,
                "name": requester.name,
                "whatsapp_number": requester.whatsapp_number,
                "property_id": requester.property_id.id,
                "property_name": requester.property_id.name,
                "unit_number": requester.unit_number,
                "terms_accepted": requester.terms_accepted,
                "terms_accepted_at": requester.terms_accepted_at,
            },
        })

    @http.route("/api/apricot_ticketing/register_user", type="http", auth="public", methods=["POST"], csrf=False)
    def register_user(self, **kwargs):
        auth_error = self._require_auth()
        if auth_error:
            return auth_error
        payload = self._payload()
        requester = self._requester_from_payload(payload, create=True)
        if not requester:
            return self._json_response({"ok": False, "error": "whatsapp_number is required"}, status=400)
        prop = self._property_from_payload(payload)
        vals = {}
        for field_name in ["name", "unit_number"]:
            if payload.get(field_name):
                vals[field_name] = payload[field_name]
        if prop:
            vals["property_id"] = prop.id
        if payload.get("terms_accepted"):
            vals.update({"terms_accepted": True, "terms_accepted_at": fields.Datetime.now()})
        if vals:
            requester.write(vals)
        return self._json_response({"ok": True, "requester_id": requester.id})

    @http.route("/api/apricot_ticketing/accept_terms", type="http", auth="public", methods=["POST"], csrf=False)
    def accept_terms(self, **kwargs):
        auth_error = self._require_auth()
        if auth_error:
            return auth_error
        payload = self._payload()
        requester = self._requester_from_payload(payload, create=True)
        if not requester:
            return self._json_response({"ok": False, "error": "whatsapp_number is required"}, status=400)
        requester.write({"terms_accepted": True, "terms_accepted_at": fields.Datetime.now()})
        return self._json_response({"ok": True, "requester_id": requester.id})

    @http.route("/api/apricot_ticketing/create_ticket", type="http", auth="public", methods=["POST"], csrf=False)
    def create_ticket(self, **kwargs):
        auth_error = self._require_auth()
        if auth_error:
            return auth_error
        payload = self._payload()
        requester = self._requester_from_payload(payload, create=True)
        if not requester:
            return self._json_response({"ok": False, "error": "whatsapp_number is required"}, status=400)
        category = self._category_from_payload(payload)
        prop = self._property_from_payload(payload) or requester.property_id
        description = payload.get("issue_description") or payload.get("description") or payload.get("body_text")
        if not description:
            return self._json_response({"ok": False, "error": "issue_description is required"}, status=400)
        ticket = request.env["apricot.ticket"].sudo().create({
            "requester_id": requester.id,
            "property_id": prop.id or False,
            "unit_number": payload.get("unit_number") or requester.unit_number,
            "issue_description": description,
            "category_id": category.id,
            "source": payload.get("source") or "whatsapp",
        })
        media_items = payload.get("media") or []
        for item in media_items:
            filename = item.get("filename") or "whatsapp_media"
            b64 = item.get("base64") or item.get("data")
            if b64:
                request.env["ir.attachment"].sudo().create({
                    "name": filename,
                    "res_model": "apricot.ticket",
                    "res_id": ticket.id,
                    "datas": b64,
                    "mimetype": item.get("mimetype"),
                })
        return self._json_response({"ok": True, "ticket_id": ticket.id, "ticket_ref": ticket.name})

    @http.route("/api/apricot_ticketing/update_ticket", type="http", auth="public", methods=["POST"], csrf=False)
    def update_ticket(self, **kwargs):
        auth_error = self._require_auth()
        if auth_error:
            return auth_error
        payload = self._payload()
        ticket = request.env["apricot.ticket"].sudo().browse(int(payload.get("ticket_id", 0)))
        if not ticket.exists():
            return self._json_response({"ok": False, "error": "Ticket not found"}, status=404)
        vals = {}
        stage_name = payload.get("stage") or payload.get("status")
        if stage_name:
            stage = request.env["apricot.ticket.stage"].sudo().search([("name", "=ilike", stage_name)], limit=1)
            if stage:
                vals["stage_id"] = stage.id
        if payload.get("assigned_user_id"):
            vals["assigned_user_id"] = int(payload["assigned_user_id"])
        if payload.get("due_date"):
            vals["due_date"] = payload["due_date"]
        if vals:
            ticket.write(vals)
        if payload.get("update_text"):
            request.env["apricot.ticket.update"].sudo().create({
                "ticket_id": ticket.id,
                "update_text": payload["update_text"],
            })
        return self._json_response({"ok": True, "ticket_id": ticket.id})

    @http.route("/api/apricot_ticketing/upload_ticket_media", type="http", auth="public", methods=["POST"], csrf=False)
    def upload_ticket_media(self, **kwargs):
        auth_error = self._require_auth()
        if auth_error:
            return auth_error
        payload = self._payload()
        ticket = request.env["apricot.ticket"].sudo().browse(int(payload.get("ticket_id", 0)))
        if not ticket.exists():
            return self._json_response({"ok": False, "error": "Ticket not found"}, status=404)
        b64 = payload.get("base64") or payload.get("data")
        if not b64 and payload.get("text"):
            b64 = base64.b64encode(payload["text"].encode()).decode()
        if not b64:
            return self._json_response({"ok": False, "error": "base64 data is required"}, status=400)
        attachment = request.env["ir.attachment"].sudo().create({
            "name": payload.get("filename") or "ticket_media",
            "res_model": "apricot.ticket",
            "res_id": ticket.id,
            "datas": b64,
            "mimetype": payload.get("mimetype"),
        })
        return self._json_response({"ok": True, "attachment_id": attachment.id})

    @http.route("/api/apricot_ticketing/log_message", type="http", auth="public", methods=["POST"], csrf=False)
    def log_message(self, **kwargs):
        auth_error = self._require_auth()
        if auth_error:
            return auth_error
        payload = self._payload()
        values = {
            "wa_number": payload.get("wa_number") or payload.get("whatsapp_number"),
            "direction": (payload.get("direction") or "out").lower(),
            "message_type": payload.get("message_type") or "text",
            "body_text": payload.get("body_text") or payload.get("text"),
            "message_id": payload.get("message_id") or payload.get("meta_message_id"),
            "template_name": payload.get("template_name"),
            "status": payload.get("status"),
            "error_text": payload.get("error_text"),
            "verify_url": payload.get("verify_url"),
            "meta_json": json.dumps(payload.get("meta_json"), default=str) if isinstance(payload.get("meta_json"), (dict, list)) else payload.get("meta_json"),
        }
        if payload.get("ticket_id"):
            values["ticket_id"] = int(payload["ticket_id"])
        if payload.get("job_card_id"):
            values["job_card_id"] = int(payload["job_card_id"])
        msg = request.env["apricot.whatsapp.message"].sudo().create(values)
        return self._json_response({"ok": True, "message_log_id": msg.id})

    @http.route("/api/apricot_ticketing/mark_processed_message", type="http", auth="public", methods=["POST"], csrf=False)
    def mark_processed_message(self, **kwargs):
        auth_error = self._require_auth()
        if auth_error:
            return auth_error
        payload = self._payload()
        message_id = payload.get("message_id") or payload.get("id")
        if not message_id:
            return self._json_response({"ok": False, "error": "message_id is required"}, status=400)
        Processed = request.env["apricot.whatsapp.processed.message"].sudo()
        existing = Processed.search([("message_id", "=", message_id)], limit=1)
        if existing:
            return self._json_response({"ok": True, "already_processed": True})
        rec = Processed.create({"message_id": message_id})
        return self._json_response({"ok": True, "processed_id": rec.id})

    @http.route("/api/apricot_ticketing/create_job_card", type="http", auth="public", methods=["POST"], csrf=False)
    def create_job_card(self, **kwargs):
        auth_error = self._require_auth()
        if auth_error:
            return auth_error
        payload = self._payload()
        vals = {
            "title": payload.get("title") or "Job Card",
            "description": payload.get("description") or payload.get("activities") or "Job card created from WhatsApp/API.",
            "activities": payload.get("activities"),
            "unit_number": payload.get("unit_number"),
        }
        if payload.get("ticket_id"):
            vals["ticket_id"] = int(payload["ticket_id"])
        prop = self._property_from_payload(payload)
        if prop:
            vals["property_id"] = prop.id
        if payload.get("assigned_user_id"):
            vals["assigned_user_id"] = int(payload["assigned_user_id"])
        job = request.env["apricot.job.card"].sudo().create(vals)
        if payload.get("generate_public_token"):
            job.action_generate_public_token()
        return self._json_response({
            "ok": True,
            "job_card_id": job.id,
            "job_card_ref": job.name,
            "public_token": job.public_token,
        })
    


    @http.route("/api/apricot_ticketing/get_tickets", type="http", auth="public", methods=["POST"], csrf=False)
    def get_tickets(self, **kwargs):
        auth_error = self._require_auth()
        if auth_error:
            return auth_error

        payload = self._payload()

        whatsapp_number = (
            payload.get("whatsapp_number")
            or payload.get("wa_number")
            or payload.get("phone")
        )

        active_only = bool(payload.get("active_only", True))

        if not whatsapp_number:
            return self._json_response(
                {"ok": False, "error": "whatsapp_number is required"},
                status=400,
            )

        requester = request.env["apricot.ticket.requester"].sudo().search(
            [("whatsapp_number", "=", whatsapp_number)],
            limit=1,
        )

        if not requester:
            return self._json_response({
                "ok": True,
                "tickets": [],
            })

        domain = [("requester_id", "=", requester.id)]

        if active_only:
            domain += [
                ("stage_id.is_closed", "=", False),
                ("stage_id.name", "!=", "Cancelled"),
            ]

        tickets = request.env["apricot.ticket"].sudo().search(
            domain,
            order="write_date desc, create_date desc",
            limit=int(payload.get("limit", 20)),
        )

        result = []

        for ticket in tickets:
            description = ticket.issue_description or ""

            result.append({
                "id": ticket.id,
                "ticket_id": ticket.id,
                "name": ticket.name,
                "ticket_ref": ticket.name,
                "status": ticket.stage_id.name or "",
                "stage": ticket.stage_id.name or "",
                "category": ticket.category_id.name or "",
                "description": description,
                "short_description": description[:80],
                "property": ticket.property_id.name or "",
                "property_id": ticket.property_id.id or False,
                "unit_number": ticket.unit_number or "",
                "last_update": ticket.write_date or ticket.create_date,
                "created_at": ticket.create_date,
            })

        return self._json_response({
            "ok": True,
            "tickets": result,
        })
