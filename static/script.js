const sendButton =
    document.getElementById("send-button");

const userInput =
    document.getElementById("user-input");

const chatBox =
    document.getElementById("chat-box");

const micButton =
    document.getElementById("mic-button");


// "student" or "staff", chosen on the home page
const userRole =
    document.body.dataset.role || "student";


// ========================================
// CHAT SESSION
// Everything the bot remembers in this sitting:
//   history: every message so far (sent to Gemini)
//   context: details like university, date, school, cGPA
// Saved in the browser tab, so a refresh keeps the chat.
// Going back to the home page starts a new chat.
// ========================================

const STORAGE_KEY = "exchangebot-chat";

let session = {
    role: userRole,
    history: [],
    context: {}
};


function saveSession() {

    try {
        sessionStorage.setItem(
            STORAGE_KEY,
            JSON.stringify(session)
        );
    }

    catch (error) {
        // storage blocked: the chat still works, it just won't survive a refresh
    }
}


function loadSession() {

    try {

        const saved = JSON.parse(
            sessionStorage.getItem(STORAGE_KEY)
        );

        // only reuse a saved chat for the same role
        if (saved && saved.role === userRole) {
            session = saved;
        }
    }

    catch (error) {
        // nothing saved, or storage blocked: start fresh
    }
}


// ========================================
// SHOW MESSAGES
// ========================================

function addMessage(text, who) {

    const bubble =
        document.createElement("div");

    bubble.classList.add(
        "message",
        who === "user" ? "user-message" : "bot-message"
    );

    bubble.textContent = text;

    chatBox.appendChild(bubble);

    chatBox.scrollTop =
        chatBox.scrollHeight;

    return bubble;
}


function addBotMessage(text) {

    return addMessage(text, "bot");
}


// Put back the earlier messages after a refresh
function restoreChat() {

    loadSession();

    for (const turn of session.history) {
        addMessage(turn.text, turn.role);
    }
}


// ========================================
// SEND MESSAGE
// ========================================

async function sendMessage() {

    const message =
        userInput.value.trim();


    if (message === "") {
        return;
    }


    // Show the user's message and clear the box
    addMessage(message, "user");

    userInput.value = "";


    // Temporary loading message
    const loadingMessage =
        addBotMessage("Thinking...");


    try {

        const response = await fetch(
            "/chat",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    message: message,
                    user_type: userRole,
                    context: session.context,
                    history: session.history
                })
            }
        );


        const data =
            await response.json();


        loadingMessage.remove();

        addBotMessage(data.reply);


        // Remember this exchange for the rest of the sitting
        session.history.push(
            { role: "user", text: message },
            { role: "bot", text: data.reply }
        );

        if (data.context) {
            session.context = data.context;
        }

        saveSession();

    }

    catch (error) {

        console.error(
            "Chat error:",
            error
        );

        loadingMessage.remove();

        addBotMessage(
            "Sorry, something went wrong."
        );

    }
}


// ========================================
// SEND BUTTON AND ENTER KEY
// ========================================

sendButton.addEventListener(
    "click",
    sendMessage
);


userInput.addEventListener(
    "keypress",
    function(event) {

        if (event.key === "Enter") {

            sendMessage();

        }

    }
);


// ========================================
// MIC BUTTON (SPEECH TO TEXT)
// Uses the browser's built-in speech recognition (Chrome / Edge)
// ========================================

const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;


if (SpeechRecognition) {

    const recognition =
        new SpeechRecognition();

    recognition.lang = "en-US";
    recognition.interimResults = false;


    micButton.addEventListener(
        "click",
        function() {

            micButton.classList.add("listening");
            recognition.start();

        }
    );


    // Put what the user said into the box, then send it
    recognition.addEventListener(
        "result",
        function(event) {

            userInput.value =
                event.results[0][0].transcript;

            sendMessage();

        }
    );


    recognition.addEventListener(
        "end",
        function() {

            micButton.classList.remove("listening");

        }
    );


    recognition.addEventListener(
        "error",
        function(event) {

            console.error("Speech error:", event.error);
            micButton.classList.remove("listening");

        }
    );

}

else {

    micButton.title =
        "Voice input works in Chrome or Edge";

    micButton.addEventListener(
        "click",
        function() {

            addBotMessage(
                "Voice input isn't supported in this browser. Try Chrome or Edge."
            );

        }
    );

}


// ========================================
// START: bring back this sitting's chat, if any
// ========================================

restoreChat();
