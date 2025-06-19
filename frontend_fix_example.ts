// Exemple de modification pour votre frontend
export async function chatBot(msg: MessageCreate): Promise<{ bot_response?: string }> {
  try {
    // 1. D'abord créer le message utilisateur (cela déclenchera la mise à jour du titre)
    await sendMessage({
      discussion_id: msg.discussion_id,
      content: msg.content,
      role: "user",
      attachments: msg.attachments
    });

    // 2. Puis appeler le chatbot pour obtenir la réponse
    const message: MessageBot = {
      content: msg.content,
      attachments: msg.attachments,
    }
    
    const response = await fetch(`${API_URL}/messages/${msg.discussion_id}/chatbot`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({query: message.content}),
      credentials: "include"
    })
    
    if (!response.ok) {
      throw new Error("Erreur lors du chatbot")
    }
    
    const data = await response.json()
    return data
  } catch(err) {
    console.log(err)
    throw new Error("Erreur lors de la récupération de la réponse du chatbot")
  }
}
