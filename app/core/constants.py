# MongoDB collection names
CONVERSATIONS_COLLECTION = "conversations"
MESSAGES_COLLECTION = "messages"
UNREAD_MESSAGES_COLLECTION = "unread_messages"

# Redis Pub/Sub channel prefix per user
REDIS_CHAT_CHANNEL_PREFIX = "chat:"

# JWT claim keys — must match Petopia.Backend token generation
JWT_CLAIM_ID = "Id"
JWT_CLAIM_EMAIL = "Email"
JWT_CLAIM_ROLE = "Role"

# Pagination defaults
DEFAULT_CONVERSATION_LIMIT = 20
DEFAULT_MESSAGE_LIMIT = 50
MAX_PAGE_LIMIT = 100

# Denormalized reply preview truncation length
REPLY_PREVIEW_MAX_LENGTH = 100

# WebSocket close codes
WS_CLOSE_UNAUTHORIZED = 1008
