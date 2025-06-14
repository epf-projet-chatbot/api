# Corrections à appliquer au front-end

## 1. Correction dans `chat.ts` - fonction `createChat`

```typescript
// Créer un nouveau chat
export async function createChat(userId: string): Promise<Chat> {
    try {
        const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ user_id: userId }),
        credentials: "include", // Pour inclure les cookies httpOnly
        })
    
        if (!response.ok) {
        throw new Error("Erreur lors de la création du chat")
        }
    
        const data = await response.json()
        // ✅ CORRECTION : Retourner l'objet Chat complet, pas seulement l'ID
        return data // data contient déjà l'objet Chat complet avec id, user_id, topic, etc.
    } catch (error) {
        console.error("Erreur lors de la création du chat:", error)
        throw error
    }
}
```

## 2. Correction dans `chat.ts` - fonction `getChats`

```typescript
// Récupérer les chats d'un utilisateur
export async function getChats(): Promise<Chat[]> {
  try {
    // ✅ CORRECTION : Utiliser l'endpoint correct qui ne nécessite pas d'userId dans l'URL
    const response = await fetch(`${API_URL}/chat/`, {
      method: "GET",
      credentials: "include", // Pour inclure les cookies httpOnly
    })

    if (!response.ok) {
      throw new Error("Erreur lors de la récupération des chats")
    }

    const data = await response.json()
    return data // Retourne directement la liste des chats
  } catch (error) {
    console.error("Erreur lors de la récupération des chats:", error)
    throw error
  }
}
```

## 3. Correction dans `chat.ts` - fonction `getUserFiles`

```typescript
// Récupérer les fichiers de l'utilisateur depuis GridFS (seulement les fichiers actifs)
export async function getUserFiles(): Promise<Attachment[]> {
  try {
    // ✅ CORRECTION : Utiliser la nouvelle route qui ne retourne que les fichiers actifs
    const response = await fetch(`${API_URL}/upload/gridfs/list/active-files`, {
      method: "GET",
      credentials: "include",
    })

    if (!response.ok) {
      console.error("Erreur lors de la récupération des fichiers GridFS:", response.status)
      throw new Error("Erreur lors de la récupération des fichiers")
    }

    const files = await response.json()
    console.log("Fichiers GridFS actifs récupérés:", files)
    
    return files.map((file: FileInfo) => ({
      filename: file.filename,
      url: `${API_URL}/upload/gridfs/${file.id}`
    }))
  } catch (error) {
    console.error("Erreur lors de la récupération des fichiers:", error)
    throw error
  }
}
```

## 4. Correction dans `page.tsx` - fonction `createNewConversation`

```typescript
const createNewConversation = useCallback(async () => {
    if (!user?.email) return
    
    try {
      console.log("Nouvelle conversation créée:", user.email)
      // ✅ CORRECTION : createChat retourne maintenant l'objet Chat complet
      const newChat = await createChat(user.email)
      
      // Transformer les dates en objet Date si nécessaire
      const newConversation: Chat = {
        ...newChat,
        created_at: new Date(newChat.created_at),
        updated_at: new Date(newChat.updated_at)
      }
      
      setConversations((prev) => [newConversation, ...prev])
      setCurrentConversation(newConversation)
    } catch (error) {
      console.error("Erreur lors de la création de la conversation:", error)
    }
  }, [user?.email])
```

## 5. Correction dans `page.tsx` - fonction `fetchChats`

```typescript
useEffect(() => {
    const fetchChats = async () => {
      try {
        // ✅ CORRECTION : Ne plus passer d'argument à getChats()
        const data = await getChats()
        const parsedConversations: Chat[] = data.map((chat: Chat) => ({
          ...chat,
          created_at: new Date(chat.created_at),
          updated_at: new Date(chat.updated_at)
        })).filter(chat => chat.id)
        
        console.log("Conversations récupérées:", parsedConversations)
    
        const uniqueConversations = parsedConversations.filter((conversation, index, self) => 
          index === self.findIndex(c => c.id === conversation.id)
        )
        
        setConversations(uniqueConversations)
        if (uniqueConversations.length > 0 && !currentConversationRef.current) {
          setCurrentConversation(uniqueConversations[0])
        }
        else if (currentConversationRef.current && !uniqueConversations.find(c => c.id === currentConversationRef.current!.id)) {
          setCurrentConversation(uniqueConversations.length > 0 ? uniqueConversations[0] : null)
        }
      } catch (error) {
        console.error("Erreur lors du chargement des conversations:", error)
        if (user) {
          const newChat = async () => {
            try {
              const newConversation = await createChat(user.email)
              // ✅ CORRECTION : Traiter l'objet Chat complet
              const chatWithDates: Chat = {
                ...newConversation,
                created_at: new Date(newConversation.created_at),
                updated_at: new Date(newConversation.updated_at)
              }
              setCurrentConversation(chatWithDates)
              setConversations([chatWithDates])
            } catch (createError) {
              console.error("Erreur lors de la création d'une nouvelle conversation:", createError)
            }
          }
          newChat()
        }
      }
    }
    if (user) {
      fetchChats()
    }
  }, [user])
```

## 6. Nouvelle fonction utilitaire pour nettoyer les fichiers orphelins

```typescript
// Fonction pour nettoyer manuellement les fichiers orphelins
export async function cleanupOrphanedFiles(): Promise<{ deleted_count: number; message: string }> {
  try {
    const response = await fetch(`${API_URL}/upload/gridfs/cleanup/orphaned`, {
      method: "DELETE",
      credentials: "include",
    })

    if (!response.ok) {
      throw new Error("Erreur lors du nettoyage des fichiers orphelins")
    }

    return await response.json()
  } catch (error) {
    console.error("Erreur lors du nettoyage des fichiers orphelins:", error)
    throw error
  }
}
```

## 7. Amélioration : Rafraîchir la liste des fichiers après suppression d'un chat

Dans `page.tsx`, vous pouvez ajouter une fonction pour rafraîchir la liste des fichiers après la suppression d'un chat :

```typescript
const handleDeleteConversation = useCallback(async (chatId: string) => {
    try {
      await deleteChat(chatId)
      const updatedConversations = conversations.filter((conv) => conv.id !== chatId)
      setConversations(updatedConversations)
      if (currentConversation?.id === chatId) {
        if (updatedConversations.length > 0) {
          setCurrentConversation(updatedConversations[0])
        } else {
          await createNewConversation()
        }
      }
      
      // ✅ AMÉLIORATION : Rafraîchir la liste des fichiers pour supprimer les fichiers orphelins de l'affichage
      // Si vous affichez une liste de fichiers quelque part, rechargez-la ici
      console.log("Chat supprimé, les fichiers orphelins ne s'afficheront plus dans la liste des fichiers actifs")
      
    } catch (error) {
      console.error("Erreur lors de la suppression de la conversation:", error)
    }
  }, [conversations, currentConversation, createNewConversation])
```

## Résumé des corrections principales :

1. **`createChat` retourne maintenant l'objet Chat complet** au lieu de juste l'ID
2. **`getChats` utilise le bon endpoint** sans userId dans l'URL  
3. **`getUserFiles` utilise la nouvelle route `/active-files`** qui ne retourne que les fichiers liés à des messages existants
4. **Gestion correcte des objets Chat** dans le front-end
5. **Nouvelle fonction de nettoyage** des fichiers orphelins disponible

Ces corrections éliminent les problèmes identifiés et assurent une meilleure cohérence entre le front-end et l'API.
