# -*- coding: utf-8 -*-
import logging
import threading
import time

import odoo
from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.tools import html2plaintext, plaintext2html

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    """Extend discuss.channel with Grok AI functionality"""

    _inherit = 'discuss.channel'

    # Grok AI Integration fields
    grok_ai_active = fields.Boolean(
        "Grok AI Active",
        default=False,
        help="Whether this conversation is being handled by Grok AI"
    )
    grok_ai_config_id = fields.Many2one(
        'grok.ai.config',
        string="Grok AI Configuration",
        help="Grok AI configuration used for this conversation"
    )
    grok_conversation_history = fields.Text(
        "Grok Conversation History",
        help="JSON-formatted conversation history for Grok AI context"
    )
    grok_buying_intent_detected = fields.Boolean(
        "Buying Intent Detected",
        default=False,
        help="Whether Grok AI has detected buying intent from the visitor"
    )
    grok_requirements_collected = fields.Boolean(
        "Requirements Collected",
        default=False,
        help="Whether minimum requirements have been collected from the visitor"
    )
    grok_message_count = fields.Integer(
        "Grok Message Count",
        default=0,
        help="Number of messages exchanged in this conversation"
    )

    def _message_post_after_hook(self, message, msg_vals):
        """Override to add Grok AI message handling"""
        res = super()._message_post_after_hook(message, msg_vals)

        # Only process livechat channels
        if self.channel_type != 'livechat':
            return res

        # Determine if message is from visitor (not from operator)
        is_visitor_message = False
        if message.author_id:
            # Check if author is not the operator
            is_visitor_message = message.author_id != self.livechat_operator_id
        elif hasattr(message, 'author_guest_id') and message.author_guest_id:
            # Guest messages are from visitors
            is_visitor_message = True
        elif not message.author_id and not (hasattr(message, 'author_guest_id') and message.author_guest_id):
            # No author at all - likely a visitor message (anonymous)
            is_visitor_message = True

        # Debug logging
        _logger.info("=== GROK AI DEBUG ===")
        _logger.info("Channel ID: %s, Type: %s", self.id, self.channel_type)
        _logger.info("Grok AI Active: %s", self.grok_ai_active)
        _logger.info("Grok AI Config: %s", self.grok_ai_config_id)
        _logger.info("Message Author: %s", message.author_id)
        _logger.info("Operator: %s", self.livechat_operator_id)
        _logger.info("Is Visitor Message: %s", is_visitor_message)
        _logger.info("Buying Intent Detected: %s", self.grok_buying_intent_detected)
        _logger.info("Message Type: %s", message.message_type)

        # Grok AI integration: Handle visitor messages when AI is active
        if (
            self.grok_ai_active
            and is_visitor_message
            and not self.grok_buying_intent_detected
            and message.message_type not in ("notification", "user_notification")
        ):
            _logger.info("=== TRIGGERING GROK AI RESPONSE ===")
            # Process AI response asynchronously to ensure proper message ordering
            self._handle_grok_ai_response_async(message.id)
        else:
            _logger.info("=== GROK AI NOT TRIGGERED ===")

        return res

    # ===========================
    # Grok AI Integration Methods
    # ===========================

    def _handle_grok_ai_response(self, user_message):
        """
        Handle visitor message and generate Grok AI response

        :param user_message: mail.message record from the visitor
        """
        self.ensure_one()

        if not self.grok_ai_config_id:
            return

        # Extract text from the message
        user_text = html2plaintext(user_message.body or '')

        if not user_text.strip():
            return

        try:
            # Show typing indicator
            self.sudo()._broadcast_typing_status(is_typing=True)

            # Get AI response
            grok_service = self.env['grok.ai.service']
            response_text, buying_intent = grok_service.get_ai_response(self, user_text)

            # Stop typing indicator
            self.sudo()._broadcast_typing_status(is_typing=False)

            # Handle buying intent detection FIRST (before posting response)
            if buying_intent and not self.grok_buying_intent_detected:
                self._handle_buying_intent_detected()
                # If buying intent detected, skip posting AI response
                return

            # Post AI response only if no buying intent
            if response_text:
                # sudo: mail.message - AI is allowed to post a message
                self.sudo().message_post(
                    author_id=self.livechat_operator_id.id,
                    body=plaintext2html(response_text),
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )

        except Exception as e:
            # Stop typing indicator on error
            self.sudo()._broadcast_typing_status(is_typing=False)
            _logger.error("Error handling Grok AI response for channel %s: %s", self.id, str(e))

    def _handle_grok_ai_response_async(self, message_id):
        """
        Handle Grok AI response asynchronously to ensure proper message ordering.

        :param message_id: ID of the visitor message to respond to
        """
        channel_id = self.id
        db_name = self.env.cr.dbname

        def process_response():
            # Small delay to ensure visitor message is fully committed and visible
            time.sleep(0.5)

            try:
                registry = odoo.registry(db_name)
                with registry.cursor() as new_cr:
                    # Create new environment with SUPERUSER to ensure permissions
                    new_env = api.Environment(new_cr, SUPERUSER_ID, {})

                    # Get channel and message in new environment
                    channel = new_env['discuss.channel'].browse(channel_id)
                    message = new_env['mail.message'].browse(message_id)

                    # Process AI response
                    channel._handle_grok_ai_response(message)

                    # Commit the AI response
                    new_cr.commit()
                    _logger.info("AI response committed successfully for channel %s", channel_id)
            except Exception as e:
                _logger.error("Error in async Grok AI response for channel %s: %s", channel_id, str(e), exc_info=True)

        # Start processing in a separate thread
        thread = threading.Thread(target=process_response)
        thread.daemon = True
        thread.start()

    def _broadcast_typing_status(self, is_typing=True):
        """
        Broadcast typing status to channel members

        :param is_typing: Boolean indicating if operator is typing
        """
        self.ensure_one()
        if not self.livechat_operator_id:
            return

        # Notify channel members about typing status
        notifications = []
        for member in self.channel_member_ids:
            if member.partner_id != self.livechat_operator_id:
                notifications.append([
                    member.partner_id,
                    'discuss.channel/typing_status',
                    {
                        'channel_id': self.id,
                        'partner_id': self.livechat_operator_id.id,
                        'partner_name': self.livechat_operator_id.name,
                        'is_typing': is_typing,
                    }
                ])

        if notifications:
            self.env['bus.bus']._sendmany(notifications)

    def _handle_buying_intent_detected(self):
        """
        Handle the detection of buying intent - transfer conversation to human agent
        """
        self.ensure_one()

        # Mark buying intent as detected
        self.sudo().write({
            'grok_buying_intent_detected': True,
        })

        # Post handoff message
        if self.grok_ai_config_id.conversation_handoff_message:
            # sudo: mail.message - AI handoff notification is allowed
            self.sudo().message_post(
                author_id=self.livechat_operator_id.id,
                body=plaintext2html(self.grok_ai_config_id.conversation_handoff_message),
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
            )

        # Find and assign a human operator
        self._assign_human_operator_from_grok()

    def _assign_human_operator_from_grok(self):
        """
        Assign a human operator to take over from Grok AI
        """
        self.ensure_one()

        _logger.info("=== ATTEMPTING TO ASSIGN HUMAN OPERATOR ===")
        _logger.info("Channel ID: %s, Livechat Channel: %s", self.id, self.livechat_channel_id)

        if not self.livechat_channel_id:
            _logger.warning("No livechat channel found for handover")
            return

        # Get available human operator (excluding AI operator)
        # sudo: res.users - visitor can access operator of their channel
        ai_operator_id = (
            self.grok_ai_config_id.ai_operator_user_id.id
            if self.grok_ai_config_id and self.grok_ai_config_id.ai_operator_user_id
            else False
        )

        # Get all available operators
        available_operators = self.livechat_channel_id.sudo().user_ids.filtered(
            lambda u: u.im_status == 'online'
        )

        # Exclude AI operator from human operators
        human_operators = (
            available_operators.filtered(lambda u: u.id != ai_operator_id)
            if ai_operator_id
            else available_operators
        )

        # ROUND-ROBIN ASSIGNMENT: Select next available operator
        human_operator = None
        if human_operators:
            # Get last assigned operator
            last_assigned = self.livechat_channel_id.last_assigned_operator_id

            # Filter out operators who are already handling conversations
            busy_operators = self.env['discuss.channel'].sudo().search([
                ('channel_type', '=', 'livechat'),
                ('livechat_channel_id', '=', self.livechat_channel_id.id),
                ('livechat_operator_id', 'in', [op.partner_id.id for op in human_operators]),
                ('grok_ai_active', '=', False),
                ('id', '!=', self.id),
            ]).mapped('livechat_operator_id')

            busy_operator_ids = [
                self.env['res.users'].sudo().search([('partner_id', '=', p.id)], limit=1).id
                for p in busy_operators
            ]

            # Get free operators (not currently handling any conversation)
            free_operators = human_operators.filtered(lambda u: u.id not in busy_operator_ids)

            _logger.info("Total human operators: %s", [u.name for u in human_operators])
            _logger.info("Busy operators: %s", busy_operator_ids)
            _logger.info("Free operators: %s", [u.name for u in free_operators])
            _logger.info("Last assigned operator: %s", last_assigned.name if last_assigned else 'None')

            if free_operators:
                if last_assigned:
                    all_operators_list = list(human_operators)
                    try:
                        last_index = all_operators_list.index(last_assigned)
                    except ValueError:
                        last_index = -1

                    search_start = (last_index + 1) % len(all_operators_list)

                    found = False
                    for i in range(len(all_operators_list)):
                        current_index = (search_start + i) % len(all_operators_list)
                        candidate = all_operators_list[current_index]
                        if candidate in free_operators:
                            human_operator = candidate
                            found = True
                            _logger.info(
                                "Round-robin: Last assigned was %s (index %d), selecting next free: %s (index %d)",
                                last_assigned.name, last_index, human_operator.name, current_index,
                            )
                            break

                    if not found:
                        human_operator = free_operators[0]
                        _logger.warning("Could not find next in rotation, using first free: %s", human_operator.name)
                else:
                    human_operator = free_operators[0]
                    _logger.info("No previous assignment, selecting first free: %s", human_operator.name)
            else:
                _logger.warning("All operators are busy, assigning to first available anyway")
                human_operator = human_operators[0]

        _logger.info("Available operators: %s", [u.name for u in available_operators])
        _logger.info("AI operator ID: %s", ai_operator_id)
        _logger.info("Human operators: %s", [u.name for u in human_operators])
        _logger.info("Selected human operator: %s", human_operator.name if human_operator else 'None')

        if human_operator:
            self._handoff_to_human_operator(human_operator)
        else:
            self._handoff_to_offline_operator(ai_operator_id)

    def _handoff_to_human_operator(self, human_operator):
        """Hand off the conversation to an online human operator."""
        channel_sudo = self.sudo()

        _logger.info("Adding human operator %s to channel %s", human_operator.name, self.id)

        # Add human operator to the channel (Odoo 19 API)
        channel_sudo._add_members(partners=human_operator.partner_id)

        # Update channel operator and deactivate AI
        channel_sudo.write({
            'livechat_operator_id': human_operator.partner_id.id,
            'grok_ai_active': False,
            'name': " ".join(filter(None, [
                self.name and self.name.split(' ')[0] or 'Visitor',
                human_operator.livechat_username or human_operator.name,
            ])),
        })

        # Update last assigned operator for round-robin
        self.livechat_channel_id.sudo().write({
            'last_assigned_operator_id': human_operator.id
        })

        _logger.info("Successfully assigned human operator %s to channel %s", human_operator.name, self.id)

        # Notify the channel members
        notification_message = _('An agent (%s) has joined the conversation.') % human_operator.name
        channel_sudo.message_post(
            body=notification_message,
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
        )

    def _handoff_to_offline_operator(self, ai_operator_id):
        """Hand off the conversation to an offline operator when no online agents are available."""
        _logger.warning("No human operators available for channel %s", self.id)

        # Get all operators (including offline ones)
        all_operators = self.livechat_channel_id.sudo().user_ids
        if ai_operator_id:
            all_operators = all_operators.filtered(lambda u: u.id != ai_operator_id)

        if not all_operators:
            # No operators configured at all
            self.sudo().message_post(
                author_id=self.env.ref('base.partner_root').id,
                body='<div class="o_mail_notification">%s</div>' % _(
                    'No agents are currently available. We will respond as soon as possible.'
                ),
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
            )
            return

        # Assign to any offline agent using round-robin
        last_assigned = self.livechat_channel_id.last_assigned_operator_id

        offline_operator = None
        if last_assigned and last_assigned in all_operators:
            all_operators_list = list(all_operators)
            try:
                last_index = all_operators_list.index(last_assigned)
            except ValueError:
                last_index = -1
            next_index = (last_index + 1) % len(all_operators_list)
            offline_operator = all_operators_list[next_index]
            _logger.info("No online agents - assigning to offline agent (round-robin): %s", offline_operator.name)
        else:
            offline_operator = all_operators[0]
            _logger.info("No online agents - assigning to first offline agent: %s", offline_operator.name)

        channel_sudo = self.sudo()

        _logger.info("Adding offline operator %s to channel %s", offline_operator.name, self.id)

        # Add offline operator to the channel (Odoo 19 API)
        channel_sudo._add_members(partners=offline_operator.partner_id)

        # Update channel operator and deactivate AI
        channel_sudo.write({
            'livechat_operator_id': offline_operator.partner_id.id,
            'grok_ai_active': False,
            'name': " ".join(filter(None, [
                self.name and self.name.split(' ')[0] or 'Visitor',
                offline_operator.livechat_username or offline_operator.name,
            ])),
        })

        # Update last assigned operator for round-robin
        self.livechat_channel_id.sudo().write({
            'last_assigned_operator_id': offline_operator.id
        })

        # Post offline message to the visitor
        offline_message = (
            self.grok_ai_config_id.offline_agent_message
            or _('No agents are currently available. We will respond as soon as possible.')
        )
        channel_sudo.message_post(
            author_id=self.livechat_operator_id.id,
            body=plaintext2html(offline_message),
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )

        _logger.info("Successfully assigned offline operator %s to channel %s", offline_operator.name, self.id)
