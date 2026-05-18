# Apricot Ticketing - Odoo Module

This module is the first clean Odoo replacement for the old Streamlit + MySQL ticketing portal.
It is designed as a fresh install: old MySQL data is not imported.

## Included in this first build

- Properties
- Requesters / WhatsApp users
- Tickets with stages, categories, assignment, updates and logs
- Job cards with signoff, PDF report and public verification token
- WhatsApp message log / inbox
- Processed message tracking
- Bulk message audit
- Token-authenticated API endpoints for the Flask WhatsApp backend

## Install

Copy the module to your custom addons folder:

```bash
sudo cp -r apricot_ticketing /opt/odoo/custom_addons/
sudo chown -R odoo:odoo /opt/odoo/custom_addons/apricot_ticketing
sudo systemctl restart odoo
```

Then in Odoo:

1. Activate Developer Mode.
2. Apps → Update Apps List.
3. Search `Apricot Ticketing`.
4. Install.
5. Add your Odoo user to one of these groups:
   - Ticketing User
   - Ticketing Admin
   - Ticketing Super Admin

## API token setup

Set the token in Odoo shell or System Parameters:

```python
env['ir.config_parameter'].sudo().set_param('apricot_ticketing.api_token', 'CHANGE_ME_LONG_RANDOM_TOKEN')
```

Flask should send:

```http
Authorization: Bearer CHANGE_ME_LONG_RANDOM_TOKEN
Content-Type: application/json
```

## Core endpoints

- `GET /apricot_ticketing/api/health`
- `POST /api/apricot_ticketing/check_user`
- `POST /api/apricot_ticketing/register_user`
- `POST /api/apricot_ticketing/accept_terms`
- `POST /api/apricot_ticketing/create_ticket`
- `POST /api/apricot_ticketing/update_ticket`
- `POST /api/apricot_ticketing/upload_ticket_media`
- `POST /api/apricot_ticketing/log_message`
- `POST /api/apricot_ticketing/mark_processed_message`
- `POST /api/apricot_ticketing/create_job_card`

If your Odoo instance is multi-db or dbfilter is not selecting the database automatically, add `?db=odoo1` to API URLs.

## First manual setup after install

1. Create properties.
2. Create ticket users/admins in Odoo and assign groups.
3. Add requesters manually or let WhatsApp registration create them through API.
4. Confirm categories and stages.
5. Test ticket creation from Odoo UI.
6. Test ticket creation from Flask using the API.
