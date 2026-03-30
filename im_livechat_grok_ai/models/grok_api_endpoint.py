# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class GrokApiEndpoint(models.Model):
    """Dynamic API endpoint configuration for Grok AI"""

    _name = 'grok.api.endpoint'
    _description = 'Grok API Endpoint'
    _order = 'sequence, id'

    name = fields.Char('API Name', required=True, help="Name of the API (e.g., Car Hire, Train Tickets)")
    marker = fields.Char('Marker Code', required=True, help="Marker code for AI to use (e.g., CAR_HIRE, TRAIN_TICKET)")
    api_url = fields.Char('API URL', required=True, help="Full URL of the API endpoint")
    description = fields.Text('Description', help="Description of what this API provides")
    prompt_instruction = fields.Text(
        'AI Prompt Instruction',
        help="Instructions for the AI on when and how to use this API",
        default="Use [GET_{MARKER}:destination] when customers ask about {name}"
    )
    sequence = fields.Integer('Sequence', default=10, help="Order of display")
    active = fields.Boolean('Active', default=True)
    config_id = fields.Many2one('grok.ai.config', string='Configuration', required=True, ondelete='cascade')

    # Response formatting
    response_format = fields.Selection([
        ('list', 'List Format'),
        ('dict', 'Dictionary Format'),
        ('raw', 'Raw JSON'),
    ], string='Response Format', default='list', help="Expected format of API response")

    list_item_template = fields.Char(
        'List Item Template',
        help="Template for formatting list items. Use {field_name} for dynamic values",
        default="{name} - {price} {currency}"
    )

    # API Request Configuration
    request_method = fields.Selection([
        ('GET', 'GET'),
        ('POST', 'POST'),
    ], string='HTTP Method', default='GET', help="HTTP method to use for API calls")

    param_name = fields.Char(
        'Parameter Name',
        default='destination',
        help="Name of the URL parameter when using [GET_MARKER:value]. Example: 'destination', 'location', 'query', 'city'"
    )

    param_location = fields.Selection([
        ('query', 'Query String (?param=value)'),
        ('path', 'URL Path (/endpoint/value)'),
        ('body', 'Request Body (JSON)'),
    ], string='Parameter Location', default='query', help="Where to place the parameter in the request")

    @api.constrains('marker')
    def _check_marker(self):
        """Validate marker format"""
        for record in self:
            if record.marker:
                # Check for valid marker format (uppercase, underscores only)
                if not record.marker.replace('_', '').isalnum() or not record.marker.isupper():
                    raise ValidationError(_("Marker must be uppercase alphanumeric with underscores only (e.g., CAR_HIRE)"))

    @api.depends('name', 'marker')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.name} ({record.marker})"
