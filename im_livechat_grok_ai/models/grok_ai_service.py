# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging
import requests
from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class GrokAIService(models.AbstractModel):
    """Service class for Grok AI API integration"""

    _name = 'grok.ai.service'
    _description = 'Grok AI Service'

    BUYING_INTENT_MARKER = '[BUYING_INTENT_DETECTED]'

    def _fetch_dynamic_api(self, endpoint, param=None):
        """Fetch data from a dynamic API endpoint with flexible configuration"""
        try:
            if not endpoint.api_url:
                _logger.warning(f"API URL not configured for {endpoint.name}")
                return None

            url = endpoint.api_url
            params = {}
            json_body = None

            # Handle parameter based on location
            if param:
                param_name = endpoint.param_name or 'destination'

                if endpoint.param_location == 'query':
                    # Query string: ?param=value
                    params = {param_name: param}
                elif endpoint.param_location == 'path':
                    # URL path: /endpoint/value
                    url = f"{endpoint.api_url.rstrip('/')}/{param}"
                elif endpoint.param_location == 'body':
                    # JSON body
                    json_body = {param_name: param}

            # Make request based on method
            _logger.info(f"=== FETCHING {endpoint.name} INFO ===")
            _logger.info(f"URL: {url}")
            _logger.info(f"Method: {endpoint.request_method}")
            _logger.info(f"Query Params: {params}")
            _logger.info(f"JSON Body: {json_body}")

            if endpoint.request_method == 'POST':
                response = requests.post(url, params=params, json=json_body, timeout=10)
            else:
                response = requests.get(url, params=params, timeout=10)

            response.raise_for_status()
            data = response.json()
            _logger.info(f"=== {endpoint.name} API Response: {data} ===")
            return data
        except Exception as e:
            _logger.error(f"Error fetching {endpoint.name} info: {str(e)}")
            return None

    def _format_dynamic_api_data(self, endpoint, data, param=None):
        """Format dynamic API data based on endpoint configuration"""
        if isinstance(data, list):
            # Use list_item_template if configured
            formatted = ""
            for item in data[:5]:  # Limit to 5 items
                if endpoint.list_item_template:
                    try:
                        # Replace template variables with actual values
                        line = endpoint.list_item_template
                        for key, value in item.items():
                            line = line.replace(f'{{{key}}}', str(value))
                        formatted += f"• {line}\n"
                    except Exception as e:
                        _logger.error(f"Error formatting with template: {str(e)}")
                        formatted += f"\n• {json.dumps(item)}"
                else:
                    # Default formatting
                    formatted += f"\n• {json.dumps(item)}"
            return formatted
        elif isinstance(data, dict):
            return json.dumps(data, indent=2)
        return str(data)

    def _process_travel_api_calls(self, config, response_text):
        """
        Process and replace API markers in the AI response with actual data

        :param config: grok.ai.config record
        :param response_text: AI response containing API markers
        :return: response_text with API data inserted
        """
        _logger.info(f"=== PROCESSING AI RESPONSE ===")
        _logger.info(f"Original AI Response: {response_text}")
        processed_text = response_text

        # Process dynamic API endpoints
        import re
        if config.api_endpoint_ids:
            for endpoint in config.api_endpoint_ids.filtered(lambda e: e.active):
                # Pattern for endpoints with parameters: [GET_MARKER:param]
                pattern_with_param = rf'\[GET_{endpoint.marker}:([^\]]+)\]'
                matches = re.findall(pattern_with_param, processed_text)
                for param in matches:
                    api_data = self._fetch_dynamic_api(endpoint, param.strip())
                    if api_data:
                        formatted_data = self._format_dynamic_api_data(endpoint, api_data, param.strip())
                        processed_text = processed_text.replace(f'[GET_{endpoint.marker}:{param}]', f"\n\n{formatted_data}")
                    else:
                        processed_text = processed_text.replace(f'[GET_{endpoint.marker}:{param}]', f"\n\n({endpoint.name} information temporarily unavailable)")

                # Pattern for endpoints without parameters: [GET_MARKER]
                marker_without_param = f'[GET_{endpoint.marker}]'
                if marker_without_param in processed_text:
                    api_data = self._fetch_dynamic_api(endpoint)
                    if api_data:
                        formatted_data = self._format_dynamic_api_data(endpoint, api_data)
                        processed_text = processed_text.replace(marker_without_param, f"\n\n{formatted_data}")
                    else:
                        processed_text = processed_text.replace(marker_without_param, f"\n\n({endpoint.name} information temporarily unavailable)")

        return processed_text

    def _call_grok_api(self, config, messages):
        """
        Call Grok AI API with the given messages

        :param config: grok.ai.config record
        :param messages: list of message dictionaries with 'role' and 'content'
        :return: tuple (response_text, buying_intent_detected)
        """
        if not config or not config.api_key:
            raise UserError(_("Grok AI configuration is missing or invalid"))

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {config.api_key}'
        }

        payload = {
            'model': config.model,
            'messages': messages,
            'max_tokens': config.max_tokens,
            'temperature': config.temperature,
            'stream': False,  # Explicitly disable streaming for simpler handling
        }

        try:
            # Sanitize API key for logging (show only first/last 4 chars)
            api_key_display = f"{config.api_key[:4]}...{config.api_key[-4:]}" if len(config.api_key) > 8 else "***"
            _logger.info(f"Calling Grok API")
            _logger.info(f"  Endpoint: {config.api_endpoint}")
            _logger.info(f"  Model: {config.model}")
            _logger.info(f"  API Key: {api_key_display}")
            _logger.info(f"  Messages count: {len(messages)}")

            response = requests.post(
                config.api_endpoint,
                headers=headers,
                json=payload,
                timeout=30
            )

            # Log response details before raising for status
            _logger.info(f"Grok API Response Status: {response.status_code}")

            if response.status_code != 200:
                _logger.error(f"Grok API Error Response Body: {response.text}")

            response.raise_for_status()

            data = response.json()

            if 'choices' not in data or not data['choices']:
                raise UserError(_("Invalid response from Grok AI"))

            response_text = data['choices'][0]['message']['content']

            # Check for buying intent marker
            buying_intent = self.BUYING_INTENT_MARKER in response_text

            # Remove the buying intent marker from the response
            if buying_intent:
                response_text = response_text.replace(self.BUYING_INTENT_MARKER, '').strip()

            # Process travel API calls in the response
            response_text = self._process_travel_api_calls(config, response_text)

            return response_text, buying_intent

        except requests.exceptions.Timeout:
            _logger.error("Grok AI API request timed out")
            raise UserError(_("The AI service is taking too long to respond. Please try again."))
        except requests.exceptions.RequestException as e:
            _logger.error("Grok AI API error: %s", str(e))
            _logger.error(f"Response text if available: {e.response.text if hasattr(e, 'response') and e.response else 'No response'}")
            raise UserError(_("Failed to communicate with Grok AI: %s") % str(e))
        except Exception as e:
            _logger.error("Unexpected error in Grok AI service: %s", str(e))
            raise UserError(_("An unexpected error occurred: %s") % str(e))

    def _check_buying_intent_fast(self, config, user_message):
        """
        Quick check for buying intent without full conversation context

        :param config: grok.ai.config record
        :param user_message: string, the user's message
        :return: boolean, True if buying intent detected
        """
        # Create a minimal prompt to quickly check buying intent
        intent_check_prompt = """You are a buying intent detector. Analyze if the user message shows buying intent.
Buying intent includes: wanting to buy, book, purchase, pay, order, reserve, get pricing, asking "how much", or ready to proceed.
Respond ONLY with [BUYING_INTENT_DETECTED] if buying intent is present, otherwise respond with "NO"."""

        messages = [
            {
                'role': 'system',
                'content': intent_check_prompt
            },
            {
                'role': 'user',
                'content': user_message
            }
        ]

        try:
            _, buying_intent = self._call_grok_api(config, messages)
            _logger.info(f"=== FAST BUYING INTENT CHECK ===")
            _logger.info(f"User message: {user_message}")
            _logger.info(f"Buying intent detected: {buying_intent}")
            return buying_intent
        except Exception as e:
            _logger.error(f"Error in fast buying intent check: {str(e)}")
            # Fallback to keyword detection
            buying_keywords = ['buy', 'book', 'purchase', 'pay', 'order', 'reserve', 'how much', 'price', 'cost', 'payment']
            return any(keyword in user_message.lower() for keyword in buying_keywords)

    def _check_requirements_collected(self, channel):
        """
        Check if minimum requirements have been collected from visitor

        Requirements are considered collected if:
        1. At least 3 message exchanges have occurred (6+ total messages)
        2. OR the requirements_collected flag is manually set to True

        :param channel: mail.channel record
        :return: boolean, True if requirements collected
        """
        # Check if already marked as collected
        if channel.grok_requirements_collected:
            return True

        # Check message count (need at least 3 exchanges = 6 messages minimum)
        # This gives AI time to ask: destination, dates, type of service, etc.
        if channel.grok_message_count >= 6:
            _logger.info("=== REQUIREMENTS COLLECTED: Minimum message count reached (%d messages) ===", channel.grok_message_count)
            channel.sudo().write({'grok_requirements_collected': True})
            return True

        _logger.info("=== REQUIREMENTS NOT YET COLLECTED: Only %d messages (need 6+) ===", channel.grok_message_count)
        return False

    def get_ai_response(self, channel, user_message):
        """
        Get AI response for a user message in a livechat channel

        :param channel: discuss.channel record
        :param user_message: string, the user's message
        :return: tuple (response_text, buying_intent_detected)
        """
        if not channel.grok_ai_config_id:
            raise UserError(_("No Grok AI configuration found for this channel"))

        config = channel.grok_ai_config_id

        # Increment message count for tracking conversation progress
        channel.sudo().write({'grok_message_count': channel.grok_message_count + 1})

        # Check for buying intent
        buying_intent_detected = self._check_buying_intent_fast(config, user_message)

        # IMPORTANT: Only forward if BOTH conditions are met:
        # 1. Buying intent detected AND
        # 2. Minimum requirements have been collected
        if buying_intent_detected:
            requirements_collected = self._check_requirements_collected(channel)

            if requirements_collected:
                _logger.info("=== BUYING INTENT + REQUIREMENTS COLLECTED - FORWARDING TO AGENT ===")
                # Return empty response but with buying_intent flag set
                return "", True
            else:
                _logger.info("=== BUYING INTENT DETECTED BUT REQUIREMENTS NOT COLLECTED - CONTINUING CONVERSATION ===")
                # Continue conversation to collect more information
                # Don't set buying_intent to True yet
                buying_intent_detected = False

        # Build conversation history
        messages = []

        # Add system prompt (with dynamic API instructions)
        complete_prompt = config.get_complete_system_prompt()
        if complete_prompt:
            messages.append({
                'role': 'system',
                'content': complete_prompt
            })

        # Load previous conversation history
        if channel.grok_conversation_history:
            try:
                history = json.loads(channel.grok_conversation_history)
                messages.extend(history)
            except json.JSONDecodeError:
                _logger.warning("Failed to parse conversation history for channel %s", channel.id)

        # Add current user message
        messages.append({
            'role': 'user',
            'content': user_message
        })

        # Call Grok API
        response_text, buying_intent = self._call_grok_api(config, messages)

        # Update conversation history
        messages.append({
            'role': 'assistant',
            'content': response_text
        })

        # Store only the conversation (without system prompt) to save space
        conversation_only = [msg for msg in messages if msg['role'] != 'system']

        # Limit history to last 20 messages to prevent it from growing too large
        if len(conversation_only) > 20:
            conversation_only = conversation_only[-20:]

        channel.sudo().write({
            'grok_conversation_history': json.dumps(conversation_only)
        })

        return response_text, buying_intent
