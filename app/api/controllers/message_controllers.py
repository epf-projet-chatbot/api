from api.models.message_models import Message

class MessageController:
    async def get_all_messages(self):
        return await Message.find_all().to_list()

message_controller = MessageController()