let currentConversation = null;
let selectedFiles = [];
const chat = document.getElementById("chatbox");
const input = document.getElementById("userInput");
const button = document.getElementById("send-btn");
const voiceBtn = document.getElementById("voice-btn");

const isLoggedIn =
    document.body.dataset.loggedIn === "true";
/* 
   UTILITIES
 */

function escapeUserText(text) {

    return String(text)
        .replace(
            /&/g,
            "&amp;"
        )
        .replace(
            /</g,
            "&lt;"
        )
        .replace(
            />/g,
            "&gt;"
        );
}

function getFileIcon(
    filename
) {

    if (
        /\.(png|jpg|jpeg|webp)$/i
            .test(filename)
    ) {
        return "🖼️";
    }

    if (/\.pdf$/i.test(filename)) {
        return "📕";
    }

    if (/\.xlsx$/i.test(filename)) {
        return "📊";
    }

    if (/\.docx$/i.test(filename)) {
        return "📝";
    }

    return "📄";
}

