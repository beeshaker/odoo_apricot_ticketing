from odoo import http
from odoo.http import request


class ApricotTicketingPublic(http.Controller):

    @http.route("/apricot/job-card/<string:token>", type="http", auth="public", website=False, csrf=False)
    def verify_job_card(self, token, **kwargs):
        job = request.env["apricot.job.card"].sudo().search([("public_token", "=", token)], limit=1)
        if not job:
            return request.not_found()
        return request.render("apricot_ticketing.job_card_public_verify_template", {"job": job})
