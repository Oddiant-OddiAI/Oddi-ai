/* 
CONVERSATIONS
*/

let conversations = [];

const historyContainer =
    document.getElementById(
        "chatHistory"
    );

async function loadConversations() {

    if (!isLoggedIn) {

        conversations = [];
        currentConversation = null;

        return;
    }

    try {

        const response =
            await fetch(
                "/api/conversations"
            );

        if (!response.ok) {
            return;
        }

        const loadedConversations =
            await response.json();

        // Conversations moved to the local Bin stay hidden from the
        // active history even after a page refresh. They are only
        // removed from the server when permanently deleted from Bin.
        const trashedIds = new Set(
            getTrash()
                .map(item => item && item.id)
                .filter(Boolean)
                .map(String)
        );

        conversations = Array.isArray(loadedConversations)
            ? loadedConversations.filter(conversation =>
                !conversation.id || !trashedIds.has(String(conversation.id))
            )
            : [];

        renderHistory();

        currentConversation = null;

    } catch (error) {

        console.error(
            "Load conversations error:",
            error
        );
    }
}

async function saveConversation(
    conversation
) {

    if (!conversation.id) return;

    try {

        await fetch(
            `/api/conversations/${conversation.id}`,
            {
                method: "PUT",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    title:
                        conversation.title,
                    messages:
                        conversation.messages
                })
            }
        );

    } catch (error) {

        console.error(
            "Save conversation error:",
            error
        );
    }
}

async function createServerConversation(
    title = "New Chat"
) {

    try {

        const response =
            await fetch(
                "/api/conversations",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        title
                    })
                }
            );

        if (!response.ok) {
            return null;
        }

        return await response.json();

    } catch (error) {

        console.error(
            "Create conversation error:",
            error
        );

        return null;
    }
}

