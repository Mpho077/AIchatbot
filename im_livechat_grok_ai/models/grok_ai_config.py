# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, Command, fields, models, _
from odoo.exceptions import ValidationError


class GrokAIConfig(models.Model):
    """Configuration for Grok AI integration with Live Chat"""

    _name = 'grok.ai.config'
    _description = 'Grok AI Configuration'

    name = fields.Char('Configuration Name', required=True)
    api_key = fields.Char('Grok API Key', required=True, help="API key for Grok AI service")
    api_endpoint = fields.Char(
        'API Endpoint',
        default='https://api.x.ai/v1/chat/completions',
        help="Grok AI API endpoint"
    )
    model = fields.Char('Grok Model', default='grok-2-latest', help="Grok AI model to use (e.g., grok-2-latest, grok-2-012, grok-3-mini)")
    system_prompt = fields.Text(
        'System Prompt',
        default="""You are a knowledgeable and friendly AI Assistant helping customers with their inquiries.

CRITICAL INSTRUCTIONS - YOU MUST FOLLOW THESE:
The system has been configured with various APIs that you can access to provide real-time information.
When customers ask questions that match any of the configured API endpoints, you MUST use the corresponding command markers to fetch real-time data. DO NOT provide generic answers without using these commands when APIs are available.

REQUIREMENTS COLLECTION - EXTREMELY IMPORTANT:
Before offering to connect customers to an agent or indicating buying intent, you MUST collect the following minimum information:
1. **Destination or Service Type**: What they're looking for (e.g., country, city, service)
2. **Timeline/Dates**: When they need the service (travel dates, appointment times, etc.)
3. **Specific Requirements**: Budget, preferences, number of people, etc.
4. **Purpose**: Why they need the service (tourism, business, family visit, etc.)

Do NOT forward customers to agents until you have asked at least 3-4 clarifying questions and gathered the essential information above.
Even if a customer says "I want to book", first ask them WHAT, WHEN, and other relevant details before indicating buying intent.

BUYING INTENT DETECTION:
Only include [BUYING_INTENT_DETECTED] in your message when ALL of these conditions are met:
1. You have collected the minimum required information (destination, dates, preferences)
2. The visitor explicitly indicates they are ready to proceed with booking/purchase
3. You have had at least 3-4 exchanges with the visitor

Signs of buying intent (ONLY AFTER collecting requirements):
- Asking to finalize or confirm a booking after providing details
- Requesting payment information after discussing requirements
- Saying "I'm ready to book" or "Let's proceed" after providing all details
- Asking for next steps after a comprehensive discussion

CONVERSATION FLOW EXAMPLE:
Visitor: "I want to book a flight"
You: "I'd be happy to help you with flight booking! To find the best options for you, could you please tell me:
1. Where would you like to fly to?
2. What are your travel dates?
3. How many passengers will be traveling?"

[Continue asking follow-up questions about budget, class preference, etc.]

Only AFTER collecting this information should you indicate [BUYING_INTENT_DETECTED] when they confirm they want to proceed.

CONVERSATION STYLE:
- Be warm, professional, and helpful
- Always collect requirements systematically before forwarding
- Use the API command markers when available to provide accurate, real-time information
- The command markers will be automatically replaced with actual data from our systems

Note: Additional API endpoints and their usage instructions will be appended to this prompt automatically based on your configuration.""",
        help="System prompt that defines the AI's behavior and role"
    )
    max_tokens = fields.Integer('Max Tokens', default=500, help="Maximum tokens for AI response")
    temperature = fields.Float('Temperature', default=0.7, help="Controls randomness in responses (0.0-1.0)")
    active = fields.Boolean('Active', default=True)
    livechat_channel_ids = fields.Many2many(
        'im_livechat.channel',
        'grok_ai_config_livechat_channel_rel',
        'grok_config_id',
        'livechat_channel_id',
        string='Live Chat Channels',
        help="Live chat channels using this Grok AI configuration"
    )
    conversation_handoff_message = fields.Text(
        'Handoff Message',
        default="Great! I can see you're ready to proceed. Let me connect you with one of our specialists who can help finalize your request and answer any specific questions. They'll be with you shortly!",
        help="Message sent when handing off conversation to human agent"
    )
    offline_agent_message = fields.Text(
        'Offline Agent Message',
        default="Thank you for contacting us! All our agents are currently offline. You will be contacted during our working hours. Your conversation has been forwarded to our team.",
        help="Message sent when no agents are online and conversation is forwarded to offline agent"
    )
    ai_operator_user_id = fields.Many2one(
        'res.users',
        string='AI Assistant User',
        help="User account used as the AI assistant operator. Will be created automatically if not set."
    )

    # API Endpoints
    api_endpoint_ids = fields.One2many(
        'grok.api.endpoint',
        'config_id',
        string='Custom API Endpoints',
        help="Additional custom API endpoints that can be dynamically added"
    )

    @api.model
    def create(self, vals):
        """Create AI operator user when creating config"""
        record = super().create(vals)
        if not record.ai_operator_user_id:
            record._create_ai_operator_user()
        return record

    def _create_ai_operator_user(self):
        """Create a user to represent the AI assistant"""
        self.ensure_one()
        # Get required groups for livechat operator
        livechat_group = self.env.ref('im_livechat.im_livechat_group_user')
        base_group = self.env.ref('base.group_user')

        # Create user for AI assistant
        user = self.env['res.users'].sudo().create({
            'name': f'AI Assistant ({self.name})',
            'login': f'ai.assistant.{self.id}@grok.internal',
            'email': f'ai.assistant.{self.id}@grok.ai',
            'active': True,
            'groups_id': [Command.set([base_group.id, livechat_group.id])],
            'livechat_username': 'AI Assistant',
        })

        # Set the user as "online" in the presence system
        # This ensures the livechat widget sees the AI as an available operator
        self.env['mail.presence'].sudo().create({
            'user_id': user.id,
            'status': 'online',
        })

        self.ai_operator_user_id = user.id
        return user

    @api.constrains('temperature')
    def _check_temperature(self):
        for record in self:
            if not (0.0 <= record.temperature <= 1.0):
                raise ValidationError(_("Temperature must be between 0.0 and 1.0"))

    @api.constrains('max_tokens')
    def _check_max_tokens(self):
        for record in self:
            if record.max_tokens < 1:
                raise ValidationError(_("Max tokens must be greater than 0"))

    def get_complete_system_prompt(self):
        """Get system prompt with dynamically added custom API instructions"""
        self.ensure_one()
        complete_prompt = self.system_prompt or ''

        # Add custom API endpoint instructions if any exist
        if self.api_endpoint_ids:
            active_endpoints = self.api_endpoint_ids.filtered(lambda e: e.active)
            if active_endpoints:
                complete_prompt += "\n\n=== CONFIGURED API TOOLS - YOU MUST USE THESE ===\n"
                complete_prompt += "The following APIs are available for you to fetch real-time information. You MUST use these command markers when customers ask related questions:\n"
                for endpoint in active_endpoints:
                    if endpoint.prompt_instruction:
                        complete_prompt += f"\n**{endpoint.name}:**\n{endpoint.prompt_instruction}\n"
                    else:
                        # Default instruction if none provided
                        complete_prompt += f"\n**{endpoint.name}:** When customers ask about {endpoint.name.lower()}, use [GET_{endpoint.marker}] or [GET_{endpoint.marker}:parameter] to fetch information.\n"

        return complete_prompt
