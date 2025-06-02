from app.controllers.auth import hash_password

async def create_user(user: User):
    user_dict = user.dict()
    user_dict["password"] = hash_password(user_dict.pop("password"))
    result = await db.users.insert_one(user_dict)
    return str(result.inserted_id)