/*
=========================================================
CONVERSATIONS
Server is the source of truth for logged-in users.
=========================================================
*/

let conversations = [];

const historyContainer =
    document.getElementById("chatHistory");

const conversationSaveInFlight = new Set();
let conversationSyncInFlight = false;
let conversationSyncTimer = null;


/* =====================================================
   LOAD INITIAL CONVERSATIONS
   ===================================================== */

async function loadConversations() {

    if (!isLoggedIn) {
        conversations = [];
        currentConversation = null;
        return;
    }

    try {

        const response = await fetch(
            "/api/conversations",
            {
                method: "GET",
                credentials: "include",
                cache: "no-store",
                headers: {
                    "Accept": "application/json",
                    "Cache-Control": "no-cache"
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

        const loaded =
            await response.json();

        if (!Array.isArray(loaded)) {
            conversations = [];
            currentConversation = null;
            return;
        }

        /*
         * IMPORTANT:
         * Do NOT use getTrash() here.
         *
         * The server owns the conversation list.
         */
        conversations = loaded;

        currentConversation = null;

        renderHistory();

    } catch (error) {

        console.error(
            "Load conversations error:",
            error
        );
    }
}


/* =====================================================
   SAVE CONVERSATION
   ===================================================== */

async function saveConversation(conversation) {

    if (!conversation?.id) {
        return false;
    }

    const conversationId =
        String(conversation.id);

    conversationSaveInFlight.add(
        conversationId
    );

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

    } finally {

        conversationSaveInFlight.delete(
            conversationId
        );
    }
}


/* =====================================================
   COMPARE
   ===================================================== */

function conversationsHaveSameData(
    localConversation,
    serverConversation
) {

    if (
        !localConversation ||
        !serverConversation
    ) {
        return false;
    }

    return (
        (localConversation.title || "New Chat") ===
        (serverConversation.title || "New Chat")
    ) &&
    JSON.stringify(
        localConversation.messages || []
    ) ===
    JSON.stringify(
        serverConversation.messages || []
    );
}


/* =====================================================
   FIND BY ID
   ===================================================== */

function getConversationById(id) {

    if (
        id === null ||
        id === undefined
    ) {
        return null;
    }

    const key = String(id);

    return (
        conversations.find(
            conversation =>
                conversation &&
                conversation.id !== null &&
                conversation.id !== undefined &&
                String(conversation.id) === key
        )
        || null
    );
}


/* =====================================================
   SERVER SYNC
   ===================================================== */

async function syncConversationsFromServer(
    options = {}
) {

    if (
        !isLoggedIn ||
        conversationSyncInFlight
    ) {
        return;
    }

    conversationSyncInFlight = true;

    try {

        const response = await fetch(
            "/api/conversations",
            {
                method: "GET",
                credentials: "include",
                cache: "no-store",
                headers: {
                    "Accept":
                        "application/json",
                    "Cache-Control":
                        "no-cache"
                }
            }
        );

        if (!response.ok) {

            console.debug(
                "Conversation sync failed:",
                response.status
            );

            return;
        }

        const loaded =
            await response.json();

        if (!Array.isArray(loaded)) {
            return;
        }

        /*
         * The server is authoritative.
         *
         * DO NOT:
         *   getTrash()
         *   filter localStorage
         *   merge device-specific Bin state
         */

        const serverConversations =
            loaded;

        /*
         * Remember currently open chat by ID.
         * Never rely on its array index because
         * server ordering can change.
         */

        const currentId =
            currentConversation !== null &&
            conversations[currentConversation]?.id !== null &&
            conversations[currentConversation]?.id !== undefined
                ? String(
                    conversations[
                        currentConversation
                    ].id
                )
                : null;


        const localById =
            new Map(
                conversations
                    .filter(
                        conversation =>
                            conversation?.id !== null &&
                            conversation?.id !== undefined
                    )
                    .map(
                        conversation => [
                            String(
                                conversation.id
                            ),
                            conversation
                        ]
                    )
            );


        let listChanged = false;
        let openConversationChanged = false;


        /*
         * ADD / UPDATE SERVER CONVERSATIONS
         */

        serverConversations.forEach(
            serverConversation => {

                if (
                    serverConversation?.id === null ||
                    serverConversation?.id === undefined
                ) {
                    return;
                }

                const id =
                    String(
                        serverConversation.id
                    );

                const localConversation =
                    localById.get(id);


                /*
                 * New conversation from another device
                 */

                if (!localConversation) {

                    conversations.push({
                        ...serverConversation
                    });

                    listChanged = true;

                    return;
                }


                /*
                 * Current device is saving it.
                 * Don't overwrite the local state.
                 */

                if (
                    conversationSaveInFlight
                        .has(id)
                ) {
                    return;
                }


                if (
                    !conversationsHaveSameData(
                        localConversation,
                        serverConversation
                    )
                ) {

                    const isOpen =
                        currentId === id;


                    /*
                     * Don't replace the currently
                     * generating conversation.
                     */

                    if (
                        isOpen &&
                        generationActive
                    ) {
                        return;
                    }


                    localConversation.title =
                        serverConversation.title ||
                        "New Chat";

                    localConversation.messages =
                        Array.isArray(
                            serverConversation.messages
                        )
                            ? serverConversation.messages
                            : [];

                    localConversation.created_at =
                        serverConversation.created_at;

                    if (
                        serverConversation.updated_at !==
                        undefined
                    ) {

                        localConversation.updated_at =
                            serverConversation.updated_at;
                    }

                    listChanged = true;

                    if (isOpen) {
                        openConversationChanged = true;
                    }
                }
            }
        );


        /*
         * REMOVE LOCAL SERVER-BASED CHATS
         * THAT NO LONGER EXIST ON SERVER
         */

        const serverIds =
            new Set(
                serverConversations
                    .filter(
                        conversation =>
                            conversation?.id !== null &&
                            conversation?.id !== undefined
                    )
                    .map(
                        conversation =>
                            String(
                                conversation.id
                            )
                    )
            );


        const beforeLength =
            conversations.length;


        conversations =
            conversations.filter(
                conversation => {

                    if (!conversation?.id) {
                        return true;
                    }

                    const id =
                        String(
                            conversation.id
                        );

                    return (
                        serverIds.has(id) ||
                        conversationSaveInFlight.has(id)
                    );
                }
            );


        if (
            conversations.length !==
            beforeLength
        ) {
            listChanged = true;
        }


        /*
         * RESTORE CURRENT CONVERSATION
         * USING ITS ID
         */

        if (currentId !== null) {

            const restoredIndex =
                conversations.findIndex(
                    conversation =>
                        conversation?.id !== null &&
                        conversation?.id !== undefined &&
                        String(
                            conversation.id
                        ) === currentId
                );

            currentConversation =
                restoredIndex >= 0
                    ? restoredIndex
                    : null;
        }


        if (listChanged) {
            renderHistory();
        }


        /*
         * If another device changed the currently
         * open conversation, redraw it.
         */

        if (
            openConversationChanged &&
            options.refreshOpen !== false &&
            !generationActive &&
            currentConversation !== null
        ) {

            renderCurrentConversationFromState();
        }

    } catch (error) {

        console.debug(
            "Conversation sync skipped:",
            error
        );

    } finally {

        conversationSyncInFlight =
            false;
    }
}


/* =====================================================
   START AUTO SYNC
   ===================================================== */

function startConversationSync() {

    if (!isLoggedIn) {
        return;
    }

    if (conversationSyncTimer) {
        clearInterval(
            conversationSyncTimer
        );
    }


    /*
     * Every 4 seconds.
     */

    conversationSyncTimer =
        setInterval(
            () => {
                syncConversationsFromServer();
            },
            4000
        );


    /*
     * Sync immediately when tab/app becomes active.
     */

    document.addEventListener(
        "visibilitychange",
        () => {

            if (
                document.visibilityState ===
                "visible"
            ) {

                syncConversationsFromServer();
            }
        }
    );


    window.addEventListener(
        "focus",
        () => {
            syncConversationsFromServer();
        }
    );
}


/* =====================================================
   CREATE SERVER CONVERSATION
   ===================================================== */

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


/* =====================================================
   STARTUP
   ===================================================== */

loadConversations().then(() => {
    startConversationSync();
});