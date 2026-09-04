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

        /*
         * Remember which conversation is currently open.
         * This prevents the 10-second sync from losing the
         * active conversation.
         */
        const currentConversationId =
            currentConversation !== null &&
            conversations[currentConversation]
                ? conversations[currentConversation].id
                : null;

        const response = await fetch(
            "/api/conversations",
            {
                method: "GET",
                credentials: "include",
                cache: "no-store",
                headers: {
                    "Accept": "application/json"
                }
            }
        );

        if (!response.ok) {

            console.error(
                "Could not load conversations:",
                response.status
            );

            return;
        }

        const loadedConversations =
            await response.json();

        /*
         * IMPORTANT:
         *
         * The SERVER is the source of truth.
         *
         * Do NOT filter conversations using localStorage.
         *
         * localStorage is device-specific and caused
         * laptop and phone to show different histories.
         */
        const newConversations =
            Array.isArray(loadedConversations)
                ? loadedConversations
                : [];

        conversations = newConversations;

        /*
         * Restore the currently open conversation
         * using its SERVER ID.
         */
        if (currentConversationId !== null) {

            const restoredIndex =
                conversations.findIndex(
                    conversation =>
                        String(conversation.id) ===
                        String(currentConversationId)
                );

            currentConversation =
                restoredIndex !== -1
                    ? restoredIndex
                    : null;

        } else {

            currentConversation = null;

        }

        renderHistory();

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

    if (!conversation?.id) {
        return false;
    }

    try {

        const response = await fetch(
            `/api/conversations/${conversation.id}`,
            {
                method: "PUT",
                credentials: "include",

                headers: {
                    "Content-Type":
                        "application/json",

                    "Accept":
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

        if (!response.ok) {

            console.error(
                "Save conversation failed:",
                response.status,
                await response.text()
            );

            return false;
        }

        return true;

    } catch (error) {

        console.error(
            "Save conversation error:",
            error
        );

        return false;
    }
}


async function createServerConversation(
    title = "New Chat"
) {

    try {

        const response = await fetch(
            "/api/conversations",
            {
                method: "POST",
                credentials: "include",

                headers: {
                    "Content-Type":
                        "application/json",

                    "Accept":
                        "application/json"
                },

                body: JSON.stringify({
                    title
                })
            }
        );

        if (!response.ok) {

            console.error(
                "Create conversation failed:",
                response.status,
                await response.text()
            );

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


/* =========================================================
   CROSS-DEVICE CONVERSATION SYNC
   ========================================================= */

let conversationSyncTimer = null;


function startConversationSync() {

    if (conversationSyncTimer) {

        clearInterval(
            conversationSyncTimer
        );
    }

    conversationSyncTimer =
        setInterval(
            async () => {

                if (!isLoggedIn) {
                    return;
                }

                /*
                 * Never replace conversation data while
                 * a response is actively being generated.
                 */
                if (generationActive) {
                    return;
                }

                await loadConversations();

            },
            10000
        );
}


/* =========================================================
   INITIAL LOAD
   ========================================================= */

loadConversations().then(() => {

    startConversationSync();

});