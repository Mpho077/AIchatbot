# Live Chat Travel AI Assistant

AI-powered Travel Assistant for Odoo 16 with dynamic API configuration and real-time travel data integration.

## Features

- **AI-Powered Conversations**: Intelligent responses using Grok AI
- **Real-time Travel Data**: Visa, Flight, and Hotel information
- **Dynamic API Endpoints**: Add unlimited custom APIs from the frontend (NEW in v1.3!)
- **Buying Intent Detection**: Automatic handoff to human agents
- **Typing Indicators**: Visual feedback while AI is processing
- **Conversation History**: Context-aware responses
- **Configurable AI Behavior**: Customize AI responses through system prompts

## Installation

1. **Install Dependencies**:
   ```bash
   pip install requests
   ```

2. **Add Module Path**:
   Add the `custom_addons` folder to your Odoo configuration:
   ```
   addons_path = /path/to/odoo/addons,/path/to/custom_addons
   ```

3. **Update App List**:
   - Go to Apps menu
   - Click "Update Apps List"
   - Search for "Live Chat Grok AI Integration"
   - Click Install

## Configuration

### 1. Setup Grok AI Configuration

1. Navigate to **Live Chat > Grok AI** menu
2. Click **Create** to add a new configuration
3. Fill in the required fields:
   - **Configuration Name**: A descriptive name (e.g., "Main Travel Assistant")
   - **Grok API Key**: Your Grok AI API key from X.AI
   - **API Endpoint**: Default is `https://api.x.ai/v1/chat/completions`
   - **Model**: The Grok model to use (default: `grok-2-latest`)
   - **System Prompt**: Define how the AI should behave
   - **Temperature**: Controls response randomness (0.0-1.0)
   - **Max Tokens**: Maximum response length (default: 500)

### 2. Configure Travel APIs

In the **Travel API Configuration** tab:

- **Visa API URL**: API endpoint for visa information
- **Flight/Ticket API URL**: API endpoint for flight data
- **Hotel API URL**: API endpoint for hotel information

### 3. Add Custom API Endpoints (NEW!)

In the **Custom API Endpoints** tab, you can add unlimited custom APIs:

**Example: Adding a Car Hire API**

1. Click "Add a line"
2. Fill in the fields:
   - **Name**: Car Hire
   - **Marker**: CAR_HIRE (must be uppercase with underscores)
   - **API URL**: http://your-api.com/car-hire
   - **Response Format**: List Format (if API returns a list)
   - **List Item Template**: `{car_model} - {price_per_day} {currency}/day`
   - **Prompt Instruction**:
     ```
     When customers ask about car rental, car hire, or vehicle rental,
     you MUST use [GET_CAR_HIRE:destination] to fetch available cars.
     Example: "Let me check available car rentals for you. [GET_CAR_HIRE:Dubai]"
     ```
   - **Active**: Check to enable

**How It Works:**

The AI will automatically include the custom API instruction in its system prompt. When a visitor asks about car hire, the AI will use the marker `[GET_CAR_HIRE:Dubai]` in its response, which will be replaced with actual data from your API.

**Template Variables:**

Use `{field_name}` in your list item template. The system will replace these with actual values from your API response. For example, if your API returns:

```json
[
  {
    "car_model": "Toyota Camry",
    "price_per_day": 150,
    "currency": "AED"
  }
]
```

The template `{car_model} - {price_per_day} {currency}/day` becomes:
`Toyota Camry - 150 AED/day`

### 4. Enable on Live Chat Channel

1. Navigate to **Live Chat > Channels**
2. Open or create a Live Chat channel
3. Go to the **Options** tab
4. In the **Grok AI Integration** section:
   - Enable the **Enable Grok AI** checkbox
   - Select your Grok AI configuration from the dropdown

## How It Works

1. **Visitor starts chat**: A new conversation is initiated with the Travel Assistant
2. **AI responds**: The AI handles the conversation and shows "typing..." indicator
3. **API Integration**: When asked about visas, flights, or hotels, the AI fetches real-time data
4. **Custom APIs**: Dynamic endpoints are called automatically based on visitor questions
5. **Buying intent detected**: When visitor shows interest in booking, AI detects this
6. **Handoff to agent**: Conversation is automatically transferred to a human travel specialist
7. **Agent takes over**: Human agent continues the conversation and closes the booking

## API Marker Format

The AI uses special markers to trigger API calls:

- **Without parameters**: `[GET_MARKER_NAME]`
- **With parameters**: `[GET_MARKER_NAME:parameter]`

**Built-in Examples:**
- `[GET_VISA_INFO]` - Fetch all visa information
- `[GET_FLIGHT_INFO:Paris]` - Fetch flights to Paris
- `[GET_HOTEL_INFO:Tokyo]` - Fetch hotels in Tokyo

**Custom Examples:**
- `[GET_CAR_HIRE:Dubai]` - Fetch car rentals in Dubai
- `[GET_TRAIN_TICKET:London]` - Fetch train tickets to London

## Buying Intent Detection

When the AI detects buying intent, it will:

1. Include `[BUYING_INTENT_DETECTED]` marker in its response
2. Send a handoff message to the customer
3. Transfer the conversation to a human agent
4. Mark the conversation to prevent further AI responses

## API Response Format

Your custom APIs should return JSON in one of these formats:

**List Format** (recommended):
```json
[
  {"field1": "value1", "field2": "value2"},
  {"field1": "value3", "field2": "value4"}
]
```

**Dictionary Format**:
```json
{
  "key1": "value1",
  "key2": "value2"
}
```

## Technical Details

### Module Structure

```
im_livechat_grok_ai/
├── __init__.py
├── __manifest__.py
├── README.md
├── test_apis.py                   # API testing script
├── models/
│   ├── __init__.py
│   ├── grok_ai_config.py          # Grok AI configuration model
│   ├── grok_ai_service.py         # API service class with dynamic endpoints
│   ├── grok_api_endpoint.py       # Dynamic API endpoint model (NEW)
│   ├── mail_channel.py            # Extends mail.channel (Odoo 16)
│   └── im_livechat_channel.py     # Extends im_livechat.channel
├── views/
│   ├── grok_ai_config_views.xml
│   ├── grok_api_endpoint_views.xml   # Custom API endpoint views (NEW)
│   └── im_livechat_channel_views.xml
└── security/
    └── ir.model.access.csv
```

### Dependencies

- `im_livechat`: Odoo Live Chat module
- `requests`: Python library for HTTP requests

## Getting Your Grok API Key

1. Visit [X.AI Platform](https://x.ai/)
2. Create an account or log in
3. Navigate to API settings
4. Generate a new API key
5. Copy the key and paste it into your Grok AI configuration in Odoo

## Testing

A test script is included to verify your APIs are working:

```bash
cd C:\Program Files\Odoo 16.0.20251110\server\odoo\custom_addons\im_livechat_grok_ai
python test_apis.py
```

This will test all three built-in travel APIs and show you the response format.

## Troubleshooting

### AI Not Responding

- Check that Grok AI is enabled for the channel
- Verify API key is correct in the configuration
- Check network connectivity to X.AI servers
- Review Odoo logs for error messages (look for "=== GROK AI DEBUG ===")

### APIs Not Being Called

- Ensure markers are in UPPERCASE with underscores (e.g., CAR_HIRE, not car_hire)
- Check that the system prompt includes instructions for using the markers
- Verify the AI is including markers in its responses (check Odoo logs for "=== PROCESSING AI RESPONSE ===")
- Make sure the API URL is accessible from your Odoo server

### Custom API Not Working

- Verify the API URL returns valid JSON
- Check the marker format (must be uppercase alphanumeric with underscores only)
- Ensure the endpoint is marked as Active in the configuration
- Test the API endpoint directly using the test_apis.py script or a tool like Postman
- Review the list_item_template to ensure field names match your API response

### Typing Indicator Not Showing

- This is normal behavior in Odoo 16 - the typing indicator uses the bus.bus system
- Ensure your browser supports real-time notifications
- Check that the livechat_operator_id is set correctly

### Conversations Not Transferring

- Ensure human agents are available and online
- Check that buying intent detection is working (look for `[BUYING_INTENT_DETECTED]` in logs)
- Verify agents have proper access rights (im_livechat.im_livechat_group_user)

## Version History

- **1.3** (Current): Added dynamic custom API endpoints that can be configured from the frontend
- **1.2**: Added typing indicators for better user experience
- **1.1**: Made travel APIs configurable from the frontend
- **1.0**: Initial release with Grok AI integration and travel APIs

## Support

For issues or questions, check the Odoo server logs for detailed error messages. Logs are very verbose and will show you exactly what's happening with the AI and API calls.

## License

LGPL-3

## Author

Your Company
